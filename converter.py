# -*- coding: utf-8 -*-
"""
Motor Universal de Conversión PDF a EPUB + Cargador USB para Kindle
===================================================================
1. Convierte archivos PDF (individuales o carpetas) a formato EPUB universal.
2. Prepara y transfiere libros convertidos a un Kindle conectado por cable USB
   generando el archivo compatible con lectura directa USB (.azw / .mobi) junto
   con su carpeta auxiliar (.sdr), tal como lo maneja el sistema del Kindle.
"""

import os
import re
import time
import html
import uuid
import struct
import shutil
import hashlib
import zipfile
import tempfile
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Callable

try:
    import pymupdf as fitz
    PYMUPDF_AVAILABLE = True
except ImportError:
    try:
        import fitz
        PYMUPDF_AVAILABLE = True
    except ImportError:
        PYMUPDF_AVAILABLE = False


# ==============================================================================
# 1. PROCESADOR DE TEXTO FLUIDO (REFLOW)
# ==============================================================================

class TextReflowProcessor:
    """
    Limpia el texto extraído de cada página del PDF y reconstruye párrafos
    fluidos eliminando renglones cortados y números de página sueltos.
    """

    PAGE_NUM_REGEX = re.compile(
        r"^\s*(?:[-–—•]?\s*\d{1,4}\s*[-–—•]?|p[áa]g(?:ina)?\.?\s*\d+(?:\s*(?:de|/)\s*\d+)?)\s*$",
        re.IGNORECASE,
    )

    HEADING_HINT_REGEX = re.compile(
        r"^(?:cap[íi]tulo|parte|secci[óo]n|pr[óo]logo|ep[íi]logo|introducci[óo]n|anexo)\b",
        re.IGNORECASE,
    )

    BULLET_LINE_REGEX = re.compile(r"^(?:[-•*▪◦]|\d+[.)])\s+")
    MULTI_SPACE_REGEX = re.compile(r"[ \t]+")
    CLEAN_TRANS = str.maketrans({
        "\ufb00": "ff",
        "\ufb01": "fi",
        "\ufb02": "fl",
        "\ufb03": "ffi",
        "\ufb04": "ffl",
        "\xad": None,
        **{chr(c): None for c in list(range(0x00, 0x09)) + [0x0B, 0x0C] + list(range(0x0E, 0x20))},
    })

    @classmethod
    def clean_line(cls, line: str) -> str:
        return cls.MULTI_SPACE_REGEX.sub(" ", line.translate(cls.CLEAN_TRANS)).strip()

    @classmethod
    def is_standalone_page_number(cls, text: str) -> bool:
        return bool(cls.PAGE_NUM_REGEX.match(text))

    @classmethod
    def is_probable_subhead(cls, text: str) -> bool:
        if not text or len(text) > 85:
            return False
        if cls.HEADING_HINT_REGEX.match(text):
            return True
        if text.isupper() and 4 <= len(text) <= 60 and not text.endswith("."):
            return True
        return False

    @classmethod
    def reconstruct_paragraphs(cls, raw_blocks: List[str], merge_lines: bool = True) -> List[str]:
        cleaned_paragraphs: List[str] = []

        for block in raw_blocks:
            lines = []
            for raw_l in block.splitlines():
                cl = cls.clean_line(raw_l)
                if cl:
                    lines.append(cl)
            if not lines:
                continue

            if len(lines) == 1 and cls.is_standalone_page_number(lines[0]):
                continue

            if not merge_lines:
                cleaned_paragraphs.append(" ".join(lines))
                continue

            current_para = ""
            for line in lines:
                if cls.is_standalone_page_number(line):
                    continue
                if not current_para:
                    current_para = line
                    continue

                if current_para.endswith("-") and len(current_para) > 2 and line[0].islower():
                    current_para = current_para[:-1] + line
                elif cls.BULLET_LINE_REGEX.match(line):
                    cleaned_paragraphs.append(current_para)
                    current_para = line
                elif current_para.endswith((".", "!", "?", ":", "»", '"', "”")) and len(line) < 48:
                    cleaned_paragraphs.append(current_para)
                    current_para = line
                else:
                    current_para += " " + line

            if current_para:
                cleaned_paragraphs.append(current_para)

        final_paragraphs: List[str] = []
        for para in cleaned_paragraphs:
            if (
                merge_lines
                and final_paragraphs
                and not final_paragraphs[-1].endswith((".", "!", "?", ":", "»", '"', "”", ";"))
                and not cls.is_probable_subhead(final_paragraphs[-1])
                and para
                and para[0].islower()
            ):
                if final_paragraphs[-1].endswith("-"):
                    final_paragraphs[-1] = final_paragraphs[-1][:-1] + para
                else:
                    final_paragraphs[-1] += " " + para
            else:
                final_paragraphs.append(para)

        return final_paragraphs


# ==============================================================================
# 2. CONSTRUCTOR UNIVERSAL DE EPUB
# ==============================================================================

class KindleEpubBuilder:
    """
    Construye un archivo .epub universal compatible con todos los tamaños
    y generaciones de Amazon Kindle.
    """

    UNIVERSAL_KINDLE_CSS = """@charset "utf-8";
@namespace epub "http://www.idpf.org/2007/ops";

html, body {
    margin: 0;
    padding: 0;
}

body {
    font-family: "Bookerly", "Charis SIL", Georgia, serif;
    line-height: 1.52;
    padding: 0 2.5%;
    text-align: justify;
    widows: 2;
    orphans: 2;
    overflow-wrap: break-word;
}

h1, h2, h3 {
    font-family: "Amazon Ember", "Helvetica Neue", Arial, sans-serif;
    text-align: left;
    line-height: 1.25;
    margin-top: 1.4em;
    margin-bottom: 0.75em;
    page-break-after: avoid;
    break-after: avoid;
}

h1 {
    font-size: 1.45em;
    border-bottom: 1px solid #888;
    padding-bottom: 0.3em;
}

h2 {
    font-size: 1.18em;
    margin-top: 1.2em;
    margin-bottom: 0.5em;
}

p {
    margin-top: 0;
    margin-bottom: 0.45em;
    text-indent: 1.2em;
}

p.first-para, h1 + p, h2 + p, .figure-block + p {
    text-indent: 0;
}

p.list-item {
    text-indent: 0;
    padding-left: 1.2em;
    margin-bottom: 0.35em;
}

.cover-container {
    text-align: center;
    padding: 0;
    margin: 0;
    page-break-after: always;
}

.cover-container img {
    max-width: 100%;
    max-height: 96vh;
    width: auto;
    height: auto;
    object-fit: contain;
}

.figure-block {
    text-align: center;
    margin: 1.1em auto;
    page-break-inside: avoid;
    break-inside: avoid;
}

.figure-block img {
    max-width: 96%;
    max-height: 82vh;
    width: auto;
    height: auto;
}

@media screen and (max-width: 600px) {
    body { padding: 0 1.4%; line-height: 1.45; }
    p { text-indent: 1.0em; }
    h1 { font-size: 1.32em; }
}

@media screen and (min-width: 1100px) {
    body { padding: 0 4.5%; line-height: 1.6; }
    h1 { font-size: 1.6em; }
}
"""

    def __init__(self, title: str, author: str = "Documento Personal", language: str = "es"):
        self.title = title or "Libro sin título"
        self.author = author or "Autor Desconocido"
        self.language = language
        self.book_uuid = str(uuid.uuid4())
        self.cover_bytes: Optional[bytes] = None
        self.chapters: List[Dict[str, str]] = []
        self.images: List[Dict[str, object]] = []

    def set_cover(self, image_bytes: bytes) -> None:
        self.cover_bytes = image_bytes

    def register_image(self, image_bytes: bytes, ext: str = "jpg") -> str:
        img_index = len(self.images) + 1
        img_id = f"img_{img_index:04d}"
        filename = f"images/{img_id}.{ext}"
        media_type = "image/png" if ext.lower() == "png" else "image/jpeg"
        self.images.append({
            "id": img_id,
            "filename": filename,
            "media_type": media_type,
            "bytes": image_bytes,
        })
        return filename

    def add_chapter(self, title: str, items: List[Dict[str, str]]) -> None:
        chap_id = f"chapter_{len(self.chapters) + 1:03d}"
        filename = f"{chap_id}.xhtml"

        body_lines = [f"<h1>{html.escape(title)}</h1>"]
        first_para_pending = True

        for item in items:
            itype = item.get("type", "paragraph")
            if itype == "image":
                src = html.escape(item.get("src", ""))
                alt = html.escape(item.get("alt", "Ilustración"))
                body_lines.append(f'<div class="figure-block"><img src="{src}" alt="{alt}"/></div>')
                first_para_pending = True
            elif itype == "subhead":
                body_lines.append(f"<h2>{html.escape(item.get('text', ''))}</h2>")
                first_para_pending = True
            else:
                text = item.get("text", "")
                escaped = html.escape(text)
                if re.match(r"^(?:[-•*▪◦]|\d+[.)])\s+", text):
                    body_lines.append(f'<p class="list-item">{escaped}</p>')
                elif first_para_pending:
                    body_lines.append(f'<p class="first-para">{escaped}</p>')
                    first_para_pending = False
                else:
                    body_lines.append(f"<p>{escaped}</p>")

        xhtml_content = f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="{self.language}">
<head>
    <title>{html.escape(title)}</title>
    <link rel="stylesheet" type="text/css" href="style.css"/>
</head>
<body>
    {chr(10).join("    " + line for line in body_lines)}
</body>
</html>"""

        self.chapters.append({
            "id": chap_id,
            "filename": filename,
            "title": title,
            "xhtml": xhtml_content,
        })

    def save(self, output_path: Path) -> None:
        with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as epub_zip:
            epub_zip.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)

            container_xml = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
    <rootfiles>
        <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
    </rootfiles>
</container>"""
            epub_zip.writestr("META-INF/container.xml", container_xml)
            epub_zip.writestr("OEBPS/style.css", self.UNIVERSAL_KINDLE_CSS.strip())

            manifest_items = [
                '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>',
                '<item id="css" href="style.css" media-type="text/css"/>',
            ]
            spine_items = []

            if self.cover_bytes:
                epub_zip.writestr("OEBPS/cover.jpg", self.cover_bytes)
                cover_xhtml = """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
    <title>Portada</title>
    <link rel="stylesheet" type="text/css" href="style.css"/>
</head>
<body>
    <div class="cover-container">
        <img src="cover.jpg" alt="Portada"/>
    </div>
</body>
</html>"""
                epub_zip.writestr("OEBPS/cover.xhtml", cover_xhtml)
                manifest_items.append('<item id="cover-image" href="cover.jpg" media-type="image/jpeg"/>')
                manifest_items.append('<item id="cover-page" href="cover.xhtml" media-type="application/xhtml+xml"/>')
                spine_items.append('<itemref idref="cover-page"/>')

            for img in self.images:
                epub_zip.writestr(f"OEBPS/{img['filename']}", img["bytes"])
                manifest_items.append(
                    f'<item id="{img["id"]}" href="{img["filename"]}" media-type="{img["media_type"]}"/>'
                )

            nav_points = []
            for idx, chap in enumerate(self.chapters, start=1):
                epub_zip.writestr(f"OEBPS/{chap['filename']}", chap["xhtml"])
                manifest_items.append(
                    f'<item id="{chap["id"]}" href="{chap["filename"]}" media-type="application/xhtml+xml"/>'
                )
                spine_items.append(f'<itemref idref="{chap["id"]}"/>')
                nav_points.append(f"""
        <navPoint id="navPoint-{idx}" playOrder="{idx}">
            <navLabel>
                <text>{html.escape(chap["title"])}</text>
            </navLabel>
            <content src="{chap["filename"]}"/>
        </navPoint>""")

            cover_meta = '<meta name="cover" content="cover-image"/>' if self.cover_bytes else ""
            date_str = datetime.now().strftime("%Y-%m-%d")
            content_opf = f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="BookId" version="2.0">
    <metadata xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf">
        <dc:title>{html.escape(self.title)}</dc:title>
        <dc:creator opf:role="aut">{html.escape(self.author)}</dc:creator>
        <dc:language>{self.language}</dc:language>
        <dc:date>{date_str}</dc:date>
        <dc:identifier id="BookId" opf:scheme="UUID">{self.book_uuid}</dc:identifier>
        {cover_meta}
    </metadata>
    <manifest>
        {chr(10).join("        " + item for item in manifest_items)}
    </manifest>
    <spine toc="ncx">
        {chr(10).join("        " + item for item in spine_items)}
    </spine>
</package>"""
            epub_zip.writestr("OEBPS/content.opf", content_opf)

            toc_ncx = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE ncx PUBLIC "-//NLM//DTD ncx 2005-1//EN" "http://www.daisy.org/z3986/2005/ncx-2005-1.dtd">
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
    <head>
        <meta name="dtb:uid" content="{self.book_uuid}"/>
        <meta name="dtb:depth" content="1"/>
        <meta name="dtb:totalPageCount" content="0"/>
        <meta name="dtb:maxPageNumber" content="0"/>
    </head>
    <docTitle>
        <text>{html.escape(self.title)}</text>
    </docTitle>
    <navMap>
        {"".join(nav_points)}
    </navMap>
</ncx>"""
            epub_zip.writestr("OEBPS/toc.ncx", toc_ncx)


class PdfToEpubConverter:
    """Motor universal de conversión PDF a EPUB."""

    def __init__(
        self,
        extract_cover: bool = True,
        extract_images: bool = True,
        strip_headers_footers: bool = True,
        merge_broken_lines: bool = True,
        pages_per_chapter: int = 20,
    ):
        self.extract_cover = extract_cover
        self.extract_images = extract_images
        self.strip_headers_footers = strip_headers_footers
        self.merge_broken_lines = merge_broken_lines
        self.pages_per_chapter = max(5, pages_per_chapter)

    def convert_file(
        self,
        pdf_path: Path | str,
        epub_path: Path | str,
        page_callback: Optional[Callable[[int, int], None]] = None,
    ) -> Tuple[bool, str, Dict[str, int]]:
        pdf_path = Path(pdf_path)
        epub_path = Path(epub_path)
        stats = {"pages": 0, "chapters": 0, "images": 0}

        if not PYMUPDF_AVAILABLE:
            return False, "Falta instalar PyMuPDF", stats

        try:
            doc = fitz.open(pdf_path)
        except Exception as exc:
            return False, f"No se pudo abrir el PDF: {exc}", stats

        if doc.is_encrypted:
            doc.close()
            return False, "Saltado: PDF con contraseña", stats

        total_pages = len(doc)
        stats["pages"] = total_pages
        if total_pages == 0:
            doc.close()
            return False, "Saltado: PDF vacío", stats

        meta = doc.metadata or {}
        title = (meta.get("title") or "").strip()
        if not title or title.lower().startswith("untitled") or ".pdf" in title.lower():
            title = pdf_path.stem.replace("_", " ").replace("-", " ").strip()
        author = (meta.get("author") or "Biblioteca Personal").strip()

        builder = KindleEpubBuilder(title=title, author=author)

        if self.extract_cover:
            try:
                first_page = doc[0]
                pix = first_page.get_pixmap(matrix=fitz.Matrix(1.2, 1.2), alpha=False)
                builder.set_cover(pix.tobytes("jpeg", jpg_quality=80))
            except Exception:
                pass

        pages_items: List[List[Dict[str, str]]] = []
        total_extracted_chars = 0
        seen_xrefs = set()
        text_flags = getattr(fitz, "TEXT_DEHYPHENATE", 0)
        cb_step = max(1, total_pages // 25)

        for page_index in range(total_pages):
            page = doc[page_index]
            rect = page.rect
            page_content: List[Dict[str, str]] = []

            if self.strip_headers_footers and rect.height > 200:
                margin_y = rect.height * 0.06
                clip_rect = fitz.Rect(rect.x0, rect.y0 + margin_y, rect.x1, rect.y1 - margin_y)
            else:
                clip_rect = rect

            # TEXT_DEHYPHENATE evita TEXT_PRESERVE_IMAGES (que decodificaba imágenes en cada página en vano)
            blocks = page.get_text("blocks", clip=clip_rect, sort=True, flags=text_flags)
            raw_text_blocks = [
                b[4] for b in blocks if len(b) >= 7 and b[6] == 0 and b[4].strip()
            ]

            paragraphs = TextReflowProcessor.reconstruct_paragraphs(
                raw_text_blocks, merge_lines=self.merge_broken_lines
            )

            for p in paragraphs:
                total_extracted_chars += len(p)
                if TextReflowProcessor.is_probable_subhead(p):
                    page_content.append({"type": "subhead", "text": p})
                else:
                    page_content.append({"type": "paragraph", "text": p})

            if self.extract_images and page_index > 0 and stats["images"] < 60:
                try:
                    for img_info in page.get_images(full=True):
                        xref = img_info[0]
                        if xref in seen_xrefs:
                            continue
                        seen_xrefs.add(xref)
                        w = img_info[2] if len(img_info) > 2 else 0
                        h = img_info[3] if len(img_info) > 3 else 0
                        if w < 120 or h < 120:
                            continue
                        # Extraer stream original comprimido sin decodificar/recodificar píxeles cuando ya es JPEG/PNG
                        raw_img = doc.extract_image(xref)
                        if raw_img and raw_img.get("image"):
                            img_ext = (raw_img.get("ext") or "").lower()
                            if img_ext in ("jpg", "jpeg", "png"):
                                norm_ext = "png" if img_ext == "png" else "jpg"
                                rel_src = builder.register_image(raw_img["image"], ext=norm_ext)
                            else:
                                pix = fitz.Pixmap(doc, xref)
                                if pix.n - pix.alpha > 3:
                                    pix = fitz.Pixmap(fitz.csRGB, pix)
                                elif pix.alpha:
                                    pix = fitz.Pixmap(pix, 0)
                                rel_src = builder.register_image(pix.tobytes("jpeg", jpg_quality=80), ext="jpg")
                            page_content.append({
                                "type": "image",
                                "src": rel_src,
                                "alt": f"Ilustración pág. {page_index + 1}",
                            })
                            stats["images"] += 1
                            if stats["images"] >= 60:
                                break
                except Exception:
                    pass

            pages_items.append(page_content)
            if page_callback and ((page_index + 1) % cb_step == 0 or (page_index + 1) == total_pages):
                try:
                    page_callback(page_index + 1, total_pages)
                except Exception:
                    pass

        if total_extracted_chars < 40 and stats["images"] == 0:
            doc.close()
            return False, "Saltado: PDF escaneado sin texto (requiere OCR)", stats

        toc = doc.get_toc()
        doc.close()

        chapter_ranges: List[Tuple[str, int, int]] = []
        if toc:
            valid_toc = [(t[1].strip(), max(1, t[2]) - 1) for t in toc if t[0] <= 2 and t[1].strip()]
            for i, (chap_title, start_page) in enumerate(valid_toc):
                end_page = valid_toc[i + 1][1] if i + 1 < len(valid_toc) else total_pages
                if start_page < end_page and start_page < total_pages:
                    chapter_ranges.append((chap_title, start_page, min(end_page, total_pages)))

        if not chapter_ranges:
            step = self.pages_per_chapter
            for start_p in range(0, total_pages, step):
                end_p = min(start_p + step, total_pages)
                chap_title = (
                    title if total_pages <= step
                    else f"Capítulo {start_p // step + 1} (Págs. {start_p + 1}-{end_p})"
                )
                chapter_ranges.append((chap_title, start_p, end_p))

        chapters_added = 0
        for chap_title, start_idx, end_idx in chapter_ranges:
            combined_items: List[Dict[str, str]] = []
            for p_idx in range(start_idx, end_idx):
                combined_items.extend(pages_items[p_idx])

            if combined_items:
                builder.add_chapter(chap_title, combined_items)
                chapters_added += 1

        stats["chapters"] = chapters_added
        if chapters_added == 0:
            return False, "Sin contenido válido para exportar", stats

        try:
            epub_path.parent.mkdir(parents=True, exist_ok=True)
            builder.save(epub_path)
            size_kb = epub_path.stat().st_size / 1024
            return True, f"Listo ({chapters_added} cap., {size_kb:.0f} KB)", stats
        except Exception as exc:
            return False, f"Error al guardar EPUB: {exc}", stats


# ==============================================================================
# 3. EMPAQUETADOR NATIVO KINDLE USB (.AZW / .MOBI + CARPETA .SDR)
# ==============================================================================

class KindleUsbPacker:
    """
    Convierte un archivo .epub en un paquete nativo para carga directa por cable USB
    al Kindle:
    - Genera el contenedor binario PalmDB/MOBI (`BOOKMOBI`) con extensión `.azw` o `.mobi`
      (con metadatos EXTH `EBOK`, ASIN tipo `B0XXXXXXXX` y portada integrada).
    - Crea la carpeta compañera `<NombreLibro>_<ASIN>.sdr` que utiliza el Kindle
      en su carpeta `documents/` para guardar marcadores y progreso de lectura.
    """

    @staticmethod
    def generate_kindle_asin(seed_text: str) -> str:
        digest = hashlib.sha1(seed_text.encode("utf-8", errors="ignore")).hexdigest().upper()
        return f"B0{digest[:8]}"

    @staticmethod
    def _get_shell_com():
        """Obtiene la instancia en-proceso de Shell.Application vía pythonnet (clr) sin lanzar subprocesos."""
        import clr  # type: ignore
        from System import Type, Activator  # type: ignore
        from System.Reflection import BindingFlags  # type: ignore

        flags = BindingFlags.InvokeMethod | BindingFlags.GetProperty

        def com_call(obj, name: str, *args):
            return obj.GetType().InvokeMember(name, flags, None, obj, list(args))

        def com_iter(items):
            if items is None:
                return
            en = com_call(items, "_NewEnum")
            while en.MoveNext():
                yield en.Current

        sh = Activator.CreateInstance(Type.GetTypeFromProgID("Shell.Application"))
        return sh, com_call, com_iter

    @staticmethod
    def _run_ps_hidden(ps_script: str, timeout: int = 30, sta: bool = False) -> str:
        """Ejecuta un script de PowerShell ocultando la ventana de consola y retorna stdout en UTF-8."""
        if os.name != "nt":
            return ""
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass"]
        if sta:
            cmd.append("-Sta")
        full_script = "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8\n" + ps_script
        cmd.extend(["-Command", full_script])
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=flags,
        )
        return (res.stdout or "").strip()

    @classmethod
    def detect_connected_kindle_Folders(cls) -> List[Dict[str, str]]:
        """
        Detecta en milisegundos tanto Kindles modernos conectados como Dispositivo Portátil MTP
        (ej. Kindle Paperwhite / Scribe / Colorsoft) como Kindles clásicos con letra USB (D: a Z:).
        """
        detected: List[Dict[str, str]] = []
        if os.name != "nt":
            return detected

        # 1. Detección ultrarrápida en-proceso (~60 ms) vía COM Shell.Application
        try:
            sh, com_call, com_iter = cls._get_shell_com()
            pc = com_call(sh, "NameSpace", 17)
            if pc is not None:
                for dev in com_iter(com_call(pc, "Items")):
                    dname = str(com_call(dev, "Name") or "")
                    dtype = str(com_call(dev, "Type") or "")
                    if "kindle" in dname.lower() or any(k in dtype.lower() for k in ("portable", "dispositivo", "mtp")):
                        dev_folder = com_call(dev, "GetFolder")
                        for st in com_iter(com_call(dev_folder, "Items")):
                            st_name = str(com_call(st, "Name") or "")
                            st_folder = com_call(st, "GetFolder")
                            for sub in com_iter(com_call(st_folder, "Items")):
                                sub_name = str(com_call(sub, "Name") or "")
                                if sub_name.lower() == "documents":
                                    doc_url = f"mtp://{dname}/{st_name}/{sub_name}"
                                    # Poner siempre primero la raíz 'Internal Storage/documents' (donde el indexador USB del Kindle lee los libros)
                                    detected.append({
                                        "path": doc_url,
                                        "label": f"{dname} ({st_name}/{sub_name} - Recomendado)",
                                    })
                                    sub_folder = com_call(sub, "GetFolder")
                                    for dsub in com_iter(com_call(sub_folder, "Items")):
                                        dsub_name = str(com_call(dsub, "Name") or "")
                                        if dsub_name.lower() == "downloads":
                                            dl_folder = com_call(dsub, "GetFolder")
                                            for isub in com_iter(com_call(dl_folder, "Items")):
                                                isub_name = str(com_call(isub, "Name") or "")
                                                if bool(com_call(isub, "IsFolder")) and isub_name.lower().startswith("items"):
                                                    items_url = f"{doc_url}/{dsub_name}/{isub_name}"
                                                    detected.append({
                                                        "path": items_url,
                                                        "label": f"{dname} ({sub_name}/{dsub_name}/{isub_name})",
                                                    })
        except Exception:
            pass

        # 2. Detectar unidades USB tradicionales con letra (D: a Z:)
        for letter in "DEFGHIJKLMNOPQRSTUVWXYZ":
            drive = Path(f"{letter}:\\")
            if not drive.exists():
                continue
            docs_dir = drive / "documents"
            sys_dir = drive / "system"
            if docs_dir.is_dir():
                has_kindle_markers = (
                    sys_dir.is_dir()
                    or any(docs_dir.glob("*.sdr"))
                    or any(docs_dir.glob("*.kfx"))
                    or any(docs_dir.glob("*.azw*"))
                )
                label = (
                    f"Kindle USB ({letter}:\\documents)"
                    if has_kindle_markers
                    else f"Unidad USB ({letter}:\\documents)"
                )
                detected.append({"path": str(docs_dir), "label": label})

        return detected

    @classmethod
    def pick_kindle_folder_dialog(cls, title: str = "Selecciona tu Kindle o carpeta documents") -> str:
        """
        Abre instantáneamente en-proceso el selector de carpetas del Shell enraizado en 'Este Equipo' (17),
        mostrando dispositivos MTP como 'Kindle Paperwhite' además de unidades locales.
        """
        if os.name != "nt":
            return ""
        try:
            sh, com_call, com_iter = cls._get_shell_com()
            pc = com_call(sh, "NameSpace", 17)
            pc_title = str(com_call(pc, "Title") or "")
            folder = com_call(sh, "BrowseForFolder", 0, title, 0x0040, 17)
            if folder is None:
                return ""
            self_item = com_call(folder, "Self")
            is_fs = bool(com_call(self_item, "IsFileSystem"))
            raw_path = str(com_call(self_item, "Path") or "")
            if is_fs and len(raw_path) >= 3 and raw_path[1:3] == ":\\":
                fs_p = Path(raw_path)
                if (fs_p / "documents").is_dir() and fs_p.name.lower() != "documents":
                    fs_p = fs_p / "documents"
                return str(fs_p)

            parts: List[str] = []
            cur = folder
            while cur is not None:
                cur_title = str(com_call(cur, "Title") or "")
                if not cur_title or cur_title == pc_title:
                    break
                parts.insert(0, cur_title)
                cur = com_call(cur, "ParentFolder")

            if len(parts) == 1:
                for st in com_iter(com_call(folder, "Items")):
                    if bool(com_call(st, "IsFolder")):
                        parts.append(str(com_call(st, "Name") or ""))
                        st_f = com_call(st, "GetFolder")
                        for sub in com_iter(com_call(st_f, "Items")):
                            if str(com_call(sub, "Name") or "").lower() == "documents":
                                parts.append(str(com_call(sub, "Name") or "documents"))
                                break
                        break
            elif len(parts) == 2:
                for sub in com_iter(com_call(folder, "Items")):
                    if str(com_call(sub, "Name") or "").lower() == "documents":
                        parts.append(str(com_call(sub, "Name") or "documents"))
                        break

            return f"mtp://{'/'.join(parts)}" if parts else ""
        except Exception:
            return ""

    @classmethod
    def copy_package_to_mtp(cls, mtp_url: str, local_book_file: Path, sdr_folder_name: str) -> Tuple[bool, str]:
        """
        Copia de forma segura y verificada el archivo de libro (.mobi/.azw/.epub) y su carpeta .sdr
        a una ruta MTP usando `ParseName` (sin enumerar cientos de elementos por libro) y esperando
        a que el archivo esté físicamente confirmado en el Kindle antes de borrar el archivo temporal.
        Incluye reintentos automáticos si el bus MTP está ocupado.
        """
        rel_path = re.sub(r"^mtp://", "", mtp_url, flags=re.IGNORECASE).strip("/\\")
        segs = [s for s in re.split(r"[\\/]+", rel_path) if s]
        book_abs = str(local_book_file.resolve())
        book_name = local_book_file.name

        last_err = "Dispositivo MTP no disponible"
        for attempt in range(1, 4):
            try:
                sh, com_call, com_iter = cls._get_shell_com()
                cur_folder = com_call(sh, "NameSpace", 17)
                if cur_folder is None:
                    last_err = "No se pudo abrir 'Este equipo' (Shell.Application)"
                    time.sleep(0.8 * attempt)
                    continue

                missing_seg = ""
                for seg in segs:
                    found = None
                    for item in com_iter(com_call(cur_folder, "Items")):
                        if str(com_call(item, "Name") or "").lower() == seg.lower():
                            found = com_call(item, "GetFolder")
                            break
                    if found is None:
                        missing_seg = seg
                        break
                    cur_folder = found

                if missing_seg:
                    last_err = f"Kindle desconectado o ruta MTP '{missing_seg}' no disponible"
                    time.sleep(1.0 * attempt)
                    continue

                # Verificar con ParseName (O(1), sin enumerar cientos de archivos) si ya existe el libro
                existing_book = com_call(cur_folder, "ParseName", book_name)
                if existing_book is not None:
                    try:
                        com_call(existing_book, "InvokeVerb", "delete")
                        time.sleep(0.15)
                    except Exception:
                        pass

                # Iniciar transferencia MTP (20 = 16 YesToAll + 4 NoProgressDialog)
                com_call(cur_folder, "CopyHere", book_abs, 20)

                # IMPORTANTE: CopyHere en Windows Shell es asíncrono; debemos esperar a que ParseName
                # confirme que el archivo ya se escribió en el Kindle ANTES de que finally borre staging_dir
                confirmed = False
                for _ in range(120):
                    time.sleep(0.12)
                    chk = com_call(cur_folder, "ParseName", book_name)
                    if chk is not None:
                        confirmed = True
                        break

                if not confirmed:
                    last_err = f"Tiempo de espera agotado al escribir '{book_name}' en Kindle MTP"
                    time.sleep(0.8 * attempt)
                    continue

                # Crear carpeta compañera .sdr solo si no existe (verificado con ParseName)
                existing_sdr = com_call(cur_folder, "ParseName", sdr_folder_name)
                if existing_sdr is None:
                    try:
                        com_call(cur_folder, "NewFolder", sdr_folder_name)
                        time.sleep(0.08)
                    except Exception:
                        pass

                # Breve respiro de 40ms para no saturar el demonio MTP del Kindle en lotes de +500 libros
                time.sleep(0.04)
                return True, "OK"
            except Exception as exc:
                last_err = str(exc)
                time.sleep(0.8 * attempt)

        return False, last_err

    @classmethod
    def open_mtp_folder_in_explorer(cls, mtp_url: str) -> bool:
        """Abre en-proceso una carpeta MTP del Kindle directamente en el Explorador de Windows."""
        rel_path = re.sub(r"^mtp://", "", mtp_url, flags=re.IGNORECASE).strip("/\\")
        segs = [s for s in re.split(r"[\\/]+", rel_path) if s]
        try:
            sh, com_call, com_iter = cls._get_shell_com()
            cur_folder = com_call(sh, "NameSpace", 17)
            last_item = None
            for seg in segs:
                found_item = None
                for item in com_iter(com_call(cur_folder, "Items")):
                    if str(com_call(item, "Name") or "").lower() == seg.lower():
                        found_item = item
                        break
                if found_item is None:
                    return False
                last_item = found_item
                cur_folder = com_call(found_item, "GetFolder")
            if last_item is not None:
                com_call(last_item, "InvokeVerb", "open")
                return True
        except Exception:
            pass
        return False

    @classmethod
    def extract_epub_data(cls, epub_path: Path) -> Tuple[str, str, Optional[bytes], List[str]]:
        """Extrae título, autor, bytes de portada y lista de cuerpos HTML desde un archivo .epub."""
        title = epub_path.stem
        author = "Biblioteca Personal"
        cover_bytes: Optional[bytes] = None
        chapters_html: List[str] = []

        with zipfile.ZipFile(epub_path, "r") as zf:
            names = set(zf.namelist())
            opf_path = "OEBPS/content.opf"
            if opf_path not in names:
                opf_candidates = [n for n in names if n.lower().endswith(".opf")]
                opf_path = opf_candidates[0] if opf_candidates else ""

            opf_dir = str(Path(opf_path).parent).replace("\\", "/")
            if opf_dir == ".":
                opf_dir = ""

            spine_files: List[str] = []
            if opf_path and opf_path in names:
                try:
                    root = ET.fromstring(zf.read(opf_path))
                    ns = {
                        "opf": "http://www.idpf.org/2007/opf",
                        "dc": "http://purl.org/dc/elements/1.1/",
                    }
                    t_el = root.find(".//dc:title", ns)
                    if t_el is not None and t_el.text:
                        title = t_el.text.strip()
                    a_el = root.find(".//dc:creator", ns)
                    if a_el is not None and a_el.text:
                        author = a_el.text.strip()

                    manifest_map: Dict[str, str] = {}
                    for item in root.findall(".//opf:manifest/opf:item", ns):
                        iid = item.attrib.get("id", "")
                        href = item.attrib.get("href", "")
                        if iid and href:
                            full_href = f"{opf_dir}/{href}" if opf_dir else href
                            manifest_map[iid] = full_href

                    for itemref in root.findall(".//opf:spine/opf:itemref", ns):
                        idref = itemref.attrib.get("idref", "")
                        if idref in manifest_map and idref != "cover-page":
                            spine_files.append(manifest_map[idref])
                except Exception:
                    pass

            for cov_candidate in ("OEBPS/cover.jpg", "OEBPS/cover.jpeg", "cover.jpg", "cover.jpeg"):
                if cov_candidate in names:
                    cover_bytes = zf.read(cov_candidate)
                    break

            if not spine_files:
                spine_files = sorted(
                    n for n in names
                    if n.lower().endswith((".xhtml", ".html", ".htm")) and "cover" not in n.lower()
                )

            body_regex = re.compile(r"<body[^>]*>(.*?)</body>", re.IGNORECASE | re.DOTALL)
            img_tag_regex = re.compile(r"<img[^>]+>", re.IGNORECASE)

            for sf in spine_files:
                if sf not in names:
                    continue
                raw_xhtml = zf.read(sf).decode("utf-8", errors="ignore")
                m = body_regex.search(raw_xhtml)
                body_inner = m.group(1) if m else raw_xhtml
                # Limpiar etiquetas <img> relativas dentro del flujo de texto básico MOBI
                body_inner = img_tag_regex.sub("", body_inner)
                if body_inner.strip():
                    chapters_html.append(body_inner.strip())

        if not chapters_html:
            chapters_html.append(f"<h1>{html.escape(title)}</h1><p>Documento convertido con Reflowia.</p>")

        return title, author, cover_bytes, chapters_html

    @staticmethod
    def _chunk_utf8_records(html_bytes: bytes, max_size: int = 4096) -> List[bytes]:
        """
        Divide el flujo UTF-8 en registros de hasta 4096 bytes sin partir nunca
        un carácter multibyte UTF-8 entre dos registros.
        """
        records: List[bytes] = []
        pos = 0
        total = len(html_bytes)
        while pos < total:
            end = min(pos + max_size, total)
            if end < total:
                # Retroceder si caímos en medio de una secuencia multibyte UTF-8 (10xxxxxx)
                while end > pos and (html_bytes[end] & 0xC0) == 0x80:
                    end -= 1
            chunk = html_bytes[pos:end]
            # Rellenar con espacios hasta 4096 bytes salvo el último bloque para mantener offsets exactos
            if end < total and len(chunk) < max_size:
                chunk = chunk + (b" " * (max_size - len(chunk)))
            records.append(chunk)
            pos = end
        return records

    @classmethod
    def build_mobi_azw_bytes(
        cls,
        title: str,
        author: str,
        asin: str,
        chapters_html: List[str],
        cover_bytes: Optional[bytes] = None,
    ) -> bytes:
        """
        Construye un contenedor binario MOBI6/AZW (`BOOKMOBI`) 100% compatible con el
        indexador nativo de Kindle Paperwhite / Scribe / Basic por cable USB, incluyendo
        cabeceras EXTH completas (`524=es`, `204=201`, `113/504=ASIN`, `501=EBOK`) y
        registros obligatorios `FLIS`, `FCIS` y `EOF`.
        """
        joined_body = "<mbp:pagebreak/>".join(chapters_html)
        safe_title_html = html.escape(title)
        mobi_html = (
            "<html><head>"
            "<meta http-equiv=\"Content-Type\" content=\"text/html; charset=utf-8\"/>"
            f"<title>{safe_title_html}</title>"
            "</head><body>"
            f"{joined_body}"
            "</body></html>"
        )
        html_bytes = mobi_html.encode("utf-8")
        text_records = cls._chunk_utf8_records(html_bytes, 4096)
        num_text_records = len(text_records)
        total_text_len = sum(len(r) for r in text_records)

        has_cover = bool(cover_bytes and len(cover_bytes) > 0)
        first_non_book_idx = num_text_records + 1
        first_image_idx = (num_text_records + 1) if has_cover else 0xFFFFFFFF
        last_content_idx = num_text_records + (1 if has_cover else 0)
        flis_record_idx = last_content_idx + 1
        fcis_record_idx = last_content_idx + 2

        date_str = datetime.now().strftime("%Y-%m-%d").encode("ascii")
        asin_bytes = asin.encode("ascii", errors="ignore")

        # Registros EXTH idénticos a kindlegen para indexación inmediata en Kindle Paperwhite
        exth_items: List[Tuple[int, bytes]] = [
            (100, author.encode("utf-8")),
            (503, title.encode("utf-8")),
            (524, b"es"),
            (106, date_str),
            (501, b"EBOK"),
            (113, asin_bytes),
            (504, asin_bytes),
            (204, struct.pack(">I", 201)),  # Creator Software = kindlegen (201)
            (205, struct.pack(">I", 2)),
            (206, struct.pack(">I", 9)),
            (207, struct.pack(">I", 0)),
            (116, struct.pack(">I", 0)),    # StartReading offset = 0
        ]
        if has_cover:
            exth_items.append((201, struct.pack(">I", 0)))  # CoverOffset = 0 relativo a first_image_idx
            exth_items.append((203, struct.pack(">I", 0)))  # HasFakeCover = 0

        exth_body = b"".join(
            struct.pack(">II", rtype, len(rdata) + 8) + rdata for rtype, rdata in exth_items
        )
        exth_raw_len = 12 + len(exth_body)
        exth_pad = (4 - (exth_raw_len % 4)) % 4
        exth_total_len = exth_raw_len + exth_pad
        exth_header = (
            b"EXTH"
            + struct.pack(">II", exth_total_len, len(exth_items))
            + exth_body
            + (b"\x00" * exth_pad)
        )

        title_utf8 = title.encode("utf-8")
        full_name_offset = 16 + 232 + len(exth_header)
        full_name_len = len(title_utf8)
        title_padded = title_utf8 + (b"\x00" * ((4 - ((full_name_len + 2) % 4)) % 4 + 2))

        # 1. PalmDOC Header (16 bytes)
        palmdoc_header = struct.pack(
            ">HHIHHHH",
            1,                  # compression = 1 (sin compresión, lectura directa UTF-8)
            0,                  # unused
            total_text_len,     # text_length
            num_text_records,   # record_count
            4096,               # record_size
            0,                  # encryption_type = 0
            0,                  # unknown
        )

        # 2. MOBI Header (232 bytes, offsets exactos verificados contra Kindle Paperwhite)
        unique_id = struct.unpack(">I", hashlib.md5(asin_bytes).digest()[:4])[0]
        mobi_header = bytearray(232)
        mobi_header[0:4] = b"MOBI"
        struct.pack_into(">I", mobi_header, 4, 232)                  # header_length = 232
        struct.pack_into(">I", mobi_header, 8, 2)                    # mobi_type = 2 (Book)
        struct.pack_into(">I", mobi_header, 12, 65001)               # text_encoding = UTF-8
        struct.pack_into(">I", mobi_header, 16, unique_id)           # unique_id
        struct.pack_into(">I", mobi_header, 20, 6)                   # file_version = 6
        for off in range(24, 64, 4):
            struct.pack_into(">I", mobi_header, off, 0xFFFFFFFF)     # unused index pointers
        struct.pack_into(">I", mobi_header, 64, first_non_book_idx)  # first_non_book_index
        struct.pack_into(">I", mobi_header, 68, full_name_offset)    # full_name_offset
        struct.pack_into(">I", mobi_header, 72, full_name_len)       # full_name_length
        struct.pack_into(">I", mobi_header, 76, 1034)                # locale = Spanish (0x040A)
        struct.pack_into(">I", mobi_header, 88, 6)                   # min_version = 6
        struct.pack_into(">I", mobi_header, 92, first_image_idx)     # first_image_index
        struct.pack_into(">I", mobi_header, 112, 0x50)               # exth_flags = 0x50 (EXTH present)
        struct.pack_into(">I", mobi_header, 148, 0xFFFFFFFF)         # unknown (-1)
        struct.pack_into(">I", mobi_header, 152, 0xFFFFFFFF)         # drm_offset = 0xFFFFFFFF (SIN DRM)
        struct.pack_into(">I", mobi_header, 156, 0xFFFFFFFF)         # drm_count = 0xFFFFFFFF
        struct.pack_into(">I", mobi_header, 160, 0)                  # drm_size = 0
        struct.pack_into(">I", mobi_header, 164, 0)                  # drm_flags = 0
        struct.pack_into(">H", mobi_header, 176, 1)                  # first_content_record = 1
        struct.pack_into(">H", mobi_header, 178, last_content_idx)   # last_content_record
        struct.pack_into(">I", mobi_header, 180, 1)                  # unknown = 1
        struct.pack_into(">I", mobi_header, 184, fcis_record_idx)    # fcis_record_number
        struct.pack_into(">I", mobi_header, 188, 1)                  # fcis_record_count = 1
        struct.pack_into(">I", mobi_header, 192, flis_record_idx)    # flis_record_number
        struct.pack_into(">I", mobi_header, 196, 1)                  # flis_record_count = 1
        struct.pack_into(">I", mobi_header, 200, 0)                  # unknown = 0
        struct.pack_into(">I", mobi_header, 204, 0)                  # unknown = 0
        struct.pack_into(">I", mobi_header, 208, 0xFFFFFFFF)         # srcs_record = 0xFFFFFFFF
        struct.pack_into(">I", mobi_header, 212, 0)                  # srcs_count = 0
        struct.pack_into(">I", mobi_header, 216, 0xFFFFFFFF)         # unknown = -1
        struct.pack_into(">I", mobi_header, 220, 0xFFFFFFFF)         # unknown = -1
        struct.pack_into(">I", mobi_header, 224, 0)                  # extra_record_data_flags = 0
        struct.pack_into(">I", mobi_header, 228, 0xFFFFFFFF)         # indx_record_offset = -1

        record0 = bytes(palmdoc_header) + bytes(mobi_header) + exth_header + title_padded

        # Registro FLIS (36 bytes) y FCIS (44 bytes) estándar de Kindle
        flis_record = b"FLIS" + struct.pack(">IHHIIHHIII", 8, 65, 0, 0, 0xFFFFFFFF, 1, 3, 3, 1, 0xFFFFFFFF)
        fcis_record = b"FCIS" + struct.pack(">IIIIIIIIII", 20, 16, 1, 0, total_text_len, 0, 32, 8, 0x00010001, 0)

        all_records: List[bytes] = [record0]
        all_records.extend(text_records)
        if has_cover and cover_bytes:
            all_records.append(cover_bytes)
        all_records.append(flis_record)
        all_records.append(fcis_record)
        all_records.append(b"\xe9\x8e\r\n")  # EOF record

        num_records = len(all_records)
        now_ts = int(time.time())
        pdb_name_clean = re.sub(r"[^A-Za-z0-9_-]", "_", title)[:31].encode("ascii", errors="ignore")
        pdb_name = pdb_name_clean.ljust(32, b"\x00")

        pdb_header = struct.pack(
            ">32sHHIIIIII4s4sIIH",
            pdb_name,
            0,
            0,
            now_ts,
            now_ts,
            0,
            0,
            0,
            0,
            b"BOOK",
            b"MOBI",
            2 * num_records + 1,
            0,
            num_records,
        )

        record_list_offset = 78 + (num_records * 8) + 2
        cur_offset = record_list_offset
        rec_entries = []
        for idx, rec in enumerate(all_records):
            rec_entries.append(struct.pack(">II", cur_offset, idx * 2))
            cur_offset += len(rec)

        return pdb_header + b"".join(rec_entries) + b"\x00\x00" + b"".join(all_records)

    @classmethod
    def transfer_book_to_kindle_usb(
        cls,
        source_path: Path | str,
        kindle_docs_dir: Path | str,
        usb_format: str = "azw",  # "azw" | "mobi" | "epub"
    ) -> Tuple[bool, str, str]:
        """
        Prepara y transfiere un archivo (.epub, .pdf, .azw3, .mobi) a la carpeta `documents`
        del Kindle conectado por USB (tanto dispositivos MTP como unidades con letra D:..Z:),
        creando su archivo de lectura directa y su carpeta `.sdr`.
        Retorna (éxito, mensaje, ruta_destino).
        """
        source_path = Path(source_path)
        if not source_path.is_file():
            return False, "El archivo origen no existe", ""

        raw_dest = str(kindle_docs_dir).strip()
        is_mtp = raw_dest.lower().startswith("mtp://")

        staging_dir: Optional[Path] = None
        if is_mtp:
            staging_dir = Path(tempfile.mkdtemp(prefix="reflowia_mtp_"))
            work_dir = staging_dir
        else:
            work_dir = Path(raw_dest)
            work_dir.mkdir(parents=True, exist_ok=True)

        clean_stem = re.sub(r'[<>:"/\\|?*]', "", source_path.stem).strip() or "Libro_Kindle"
        asin = cls.generate_kindle_asin(clean_stem)
        ext_lower = source_path.suffix.lower()

        temp_epub: Optional[Path] = None
        try:
            # 1. Si el usuario eligió copiar el archivo directo o ya es .azw/.mobi/.kfx
            if usb_format == "epub" or ext_lower in (".azw", ".azw3", ".mobi", ".kfx"):
                dest_file = work_dir / source_path.name
                if source_path.resolve() != dest_file.resolve():
                    shutil.copy2(source_path, dest_file)
                sdr_name = f"{source_path.stem}.sdr"
                size_kb = dest_file.stat().st_size / 1024
                if is_mtp:
                    ok_mtp, msg_mtp = cls.copy_package_to_mtp(raw_dest, dest_file, sdr_name)
                    if not ok_mtp:
                        return False, f"Error MTP: {msg_mtp}", ""
                    return True, f"En Kindle MTP ({size_kb:.0f} KB + .sdr)", f"{raw_dest}/{dest_file.name}"
                else:
                    (work_dir / sdr_name).mkdir(parents=True, exist_ok=True)
                    return True, f"Copiado a Kindle ({size_kb:.0f} KB + .sdr)", str(dest_file)

            # 2. Si el origen es .pdf y aún no es .epub, convertir primero a .epub temporal
            epub_to_pack = source_path
            if ext_lower == ".pdf":
                temp_epub = work_dir / f"_temp_{asin}.epub"
                conv = PdfToEpubConverter()
                ok, msg, _ = conv.convert_file(source_path, temp_epub)
                if not ok:
                    return False, msg, ""
                epub_to_pack = temp_epub

            target_ext = ".azw" if usb_format == "azw" else ".mobi"
            base_kindle_name = f"{clean_stem}_{asin}"
            dest_book = work_dir / f"{base_kindle_name}{target_ext}"
            sdr_name = f"{base_kindle_name}.sdr"

            # Empaquetado nativo en memoria (~15ms por libro) sin lanzar procesos externos pesados
            title, author, cover_bytes, chapters_html = cls.extract_epub_data(epub_to_pack)
            mobi_bytes = cls.build_mobi_azw_bytes(title, author, asin, chapters_html, cover_bytes)
            dest_book.write_bytes(mobi_bytes)

            size_kb = dest_book.stat().st_size / 1024

            if is_mtp:
                ok_mtp, msg_mtp = cls.copy_package_to_mtp(raw_dest, dest_book, sdr_name)
                if not ok_mtp:
                    return False, f"Error MTP: {msg_mtp}", ""
                return True, f"En Kindle MTP ({target_ext.upper()} + .sdr, {size_kb:.0f} KB)", f"{raw_dest}/{dest_book.name}"
            else:
                (work_dir / sdr_name).mkdir(parents=True, exist_ok=True)
                return True, f"En Kindle ({target_ext.upper()} + .sdr, {size_kb:.0f} KB)", str(dest_book)
        except Exception as exc:
            return False, f"Error al enviar al Kindle: {exc}", ""
        finally:
            if temp_epub and temp_epub.exists():
                try:
                    temp_epub.unlink()
                except Exception:
                    pass
            if staging_dir and staging_dir.exists():
                try:
                    shutil.rmtree(staging_dir, ignore_errors=True)
                except Exception:
                    pass
