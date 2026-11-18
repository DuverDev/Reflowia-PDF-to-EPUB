# -*- coding: utf-8 -*-
import os
import sys
import time
import threading
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

from flask import Flask, render_template, jsonify, request

from converter import PYMUPDF_AVAILABLE, PdfToEpubConverter, KindleUsbPacker

try:
    import pymupdf as fitz
except ImportError:
    try:
        import fitz
    except ImportError:
        fitz = None

_BASE = Path(os.environ.get("APP_BASE", str(Path(__file__).resolve().parent)))
_BUNDLE = Path(os.environ.get("APP_BUNDLE", str(Path(__file__).resolve().parent)))

app = Flask(
    __name__,
    template_folder=str(_BUNDLE / "templates"),
    static_folder=str(_BUNDLE),
    static_url_path="/static",
)
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024

_state_lock = threading.Lock()
_next_item_id = 1
_next_usb_id = 1
_next_log_id = 1
_LOG_FILE = _BASE / "reflowia.log"
_app_logs: List[Dict[str, object]] = []


def _add_log(level: str, module: str, message: str) -> None:
    """Registra un evento con marca de tiempo tanto en memoria como en reflowia.log."""
    global _next_log_id
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    short_ts = ts.split(" ")[1]
    entry = {
        "id": _next_log_id,
        "ts": short_ts,
        "full_ts": ts,
        "level": level.upper(),   # INFO | OK | WARN | ERROR
        "module": module.upper(), # USB | EPUB | SYS
        "msg": message,
    }
    _next_log_id += 1
    _app_logs.append(entry)
    if len(_app_logs) > 2500:
        del _app_logs[:500]
    try:
        with open(_LOG_FILE, "a", encoding="utf-8", errors="ignore") as f:
            f.write(f"[{ts}] [{entry['level']}] [{entry['module']}] {message}\n")
    except Exception:
        pass


_config: Dict[str, object] = {
    "recursive_scan": True,
    "output_dir": str(_BASE / "EPUBs_Kindle"),
    "last_browse_dir": str(Path.home() / "Downloads"),
    "kindle_usb_dir": "",
    "usb_format": "mobi",  # "mobi" (Recomendado Kindle USB) | "azw" | "epub"
}

# ==============================================================================
# ESTADO FUNCIÓN 1: CONVERTIR PDF A EPUB
# ==============================================================================
_pending_selection: Dict[str, object] = {
    "has_selection": False,
    "mode": "",
    "display_path": "",
    "paths": [],
    "base_folder": "",
}

_load_status: Dict[str, object] = {
    "is_loading": False,
    "progress_pct": 0,
    "current": 0,
    "total": 0,
    "status_text": "",
}

_queue: List[Dict[str, object]] = []

_conversion_status: Dict[str, object] = {
    "is_converting": False,
    "stop_requested": False,
    "progress_pct": 0,
    "current_idx": 0,
    "total": 0,
    "ok_count": 0,
    "fail_count": 0,
    "status_text": "Listo",
    "eta_seconds": 0,
    "eta_text": "",
}

# ==============================================================================
# ESTADO FUNCIÓN 2: CARGAR LIBROS AL KINDLE POR CABLE USB
# ==============================================================================
_usb_pending: Dict[str, object] = {
    "has_selection": False,
    "mode": "",
    "display_path": "",
    "paths": [],
}

_usb_load_status: Dict[str, object] = {
    "is_loading": False,
    "progress_pct": 0,
    "current": 0,
    "total": 0,
    "status_text": "",
}

_usb_queue: List[Dict[str, object]] = []

_usb_transfer_status: Dict[str, object] = {
    "is_transferring": False,
    "stop_requested": False,
    "progress_pct": 0,
    "current_idx": 0,
    "total": 0,
    "ok_count": 0,
    "fail_count": 0,
    "status_text": "Listo",
    "eta_seconds": 0,
    "eta_text": "",
}


# Auto-detectar Kindle USB en segundo plano al iniciar sin bloquear el arranque
def _bg_init_kindle() -> None:
    try:
        found = KindleUsbPacker.detect_connected_kindle_Folders()
        if found:
            with _state_lock:
                if not _config.get("kindle_usb_dir"):
                    _config["kindle_usb_dir"] = found[0]["path"]
    except Exception:
        pass


threading.Thread(target=_bg_init_kindle, daemon=True).start()


@app.after_request
def no_cache(response):
    response.headers["Cache-Control"] = "no-store"
    return response


# ==============================================================================
# DIÁLOGOS NATIVOS DE WINDOWS
# ==============================================================================

def _native_pick_files(initial_dir: str, filter_str: str = "Archivos PDF (*.pdf)|*.pdf|Todos (*.*)|*.*") -> List[str]:
    try:
        import webview
        if webview.windows:
            win = webview.windows[0]
            dialog_type = getattr(webview, "FileDialog", None)
            open_mode = dialog_type.OPEN if dialog_type else webview.OPEN_DIALOG
            if "epub" in filter_str.lower():
                ft = ("Libros (*.epub;*.azw;*.azw3;*.mobi;*.pdf)", "Todos los archivos (*.*)")
            else:
                ft = ("Archivos PDF (*.pdf)", "Todos los archivos (*.*)")
            res = win.create_file_dialog(
                open_mode,
                directory=initial_dir if os.path.isdir(initial_dir) else "",
                allow_multiple=True,
                file_types=ft,
            )
            return list(res) if res else []
    except Exception:
        pass

    ps_script = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "$f = New-Object System.Windows.Forms.OpenFileDialog; "
        f"$f.Filter = '{filter_str}'; "
        "$f.Multiselect = $true; "
        f"if (Test-Path '{initial_dir}') {{ $f.InitialDirectory = '{initial_dir}' }}; "
        "if ($f.ShowDialog() -eq 'OK') { $f.FileNames -join '|' }"
    )
    try:
        out = subprocess.check_output(
            ["powershell", "-NoProfile", "-STA", "-Command", ps_script],
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        ).strip()
        return [p for p in out.split("|") if p.strip()] if out else []
    except Exception:
        return []


def _native_pick_folder(initial_dir: str, title: str) -> Optional[str]:
    try:
        import webview
        if webview.windows:
            win = webview.windows[0]
            dialog_type = getattr(webview, "FileDialog", None)
            folder_mode = dialog_type.FOLDER if dialog_type else webview.FOLDER_DIALOG
            res = win.create_file_dialog(
                folder_mode,
                directory=initial_dir if os.path.isdir(initial_dir) else "",
            )
            if res:
                return res[0] if isinstance(res, (list, tuple)) else str(res)
            return None
    except Exception:
        pass

    ps_script = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "$d = New-Object System.Windows.Forms.FolderBrowserDialog; "
        f"$d.Description = '{title}'; "
        f"if (Test-Path '{initial_dir}') {{ $d.SelectedPath = '{initial_dir}' }}; "
        "if ($d.ShowDialog() -eq 'OK') { $d.SelectedPath }"
    )
    try:
        out = subprocess.check_output(
            ["powershell", "-NoProfile", "-STA", "-Command", ps_script],
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        ).strip()
        return out if out else None
    except Exception:
        return None


def _format_eta(seconds: float) -> str:
    sec = max(0, int(round(seconds)))
    if sec <= 0:
        return "0 s"
    if sec < 60:
        return f"~{sec} s"
    mins = sec // 60
    rem = sec % 60
    return f"~{mins} min {rem:02d} s"


# ==============================================================================
# ESTADO GENERAL Y CONFIGURACIÓN
# ==============================================================================

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/state")
def get_state():
    ok_items = sum(1 for i in _queue if i["status"] == "ok")
    err_items = sum(1 for i in _queue if i["status"] == "error")
    pend_items = sum(1 for i in _queue if i["status"] == "pending")

    usb_ok_items = sum(1 for i in _usb_queue if i["status"] == "ok")
    usb_err_items = sum(1 for i in _usb_queue if i["status"] == "error")
    usb_pend_items = sum(1 for i in _usb_queue if i["status"] == "pending")

    err_logs = sum(1 for l in _app_logs if l["level"] == "ERROR")
    return jsonify({
        "config": _config,
        "pending": {
            "has_selection": _pending_selection["has_selection"],
            "mode": _pending_selection["mode"],
            "display_path": _pending_selection["display_path"],
        },
        "load": _load_status,
        "conversion": _conversion_status,
        "queue": _queue,
        "summary": {
            "total": len(_queue),
            "ok": ok_items,
            "error": err_items,
            "pending": pend_items,
        },
        "usb": {
            "pending": {
                "has_selection": _usb_pending["has_selection"],
                "mode": _usb_pending["mode"],
                "display_path": _usb_pending["display_path"],
            },
            "load": _usb_load_status,
            "transfer": _usb_transfer_status,
            "queue": _usb_queue,
            "summary": {
                "total": len(_usb_queue),
                "ok": usb_ok_items,
                "error": usb_err_items,
                "pending": usb_pend_items,
            },
        },
        "logs_summary": {
            "total": len(_app_logs),
            "errors": err_logs,
        },
    })


@app.route("/api/logs", methods=["GET"])
def get_logs():
    return jsonify({"logs": list(reversed(_app_logs[-600:])), "log_file": str(_LOG_FILE)})


@app.route("/api/logs/clear", methods=["POST"])
def clear_logs():
    with _state_lock:
        _app_logs.clear()
    try:
        if _LOG_FILE.exists():
            _LOG_FILE.write_text("", encoding="utf-8")
    except Exception:
        pass
    _add_log("INFO", "SYS", "Historial de log limpiado por el usuario.")
    return jsonify({"logs": [], "log_file": str(_LOG_FILE)})


@app.route("/api/config", methods=["POST"])
def update_config():
    data = request.get_json(silent=True) or {}
    with _state_lock:
        if "recursive_scan" in data:
            _config["recursive_scan"] = bool(data["recursive_scan"])
        if "output_dir" in data and data["output_dir"]:
            _config["output_dir"] = str(data["output_dir"])
        if "usb_format" in data and data["usb_format"] in ("azw", "mobi", "epub"):
            _config["usb_format"] = str(data["usb_format"])
        if "kindle_usb_dir" in data and data["kindle_usb_dir"]:
            _config["kindle_usb_dir"] = str(data["kindle_usb_dir"])
    return get_state()


# ==============================================================================
# FUNCIÓN 1: CONVERTIR PDF A EPUB
# ==============================================================================

@app.route("/api/select-folder", methods=["POST"])
def select_folder():
    if _load_status["is_loading"] or _conversion_status["is_converting"]:
        return jsonify({"error": "Proceso en curso"}), 400

    chosen_dir = _native_pick_folder(
        str(_config["last_browse_dir"]),
        "Selecciona la carpeta con archivos PDF",
    )
    if not chosen_dir:
        return get_state()

    folder = Path(chosen_dir).resolve()
    with _state_lock:
        _config["last_browse_dir"] = str(folder)
        _pending_selection["has_selection"] = True
        _pending_selection["mode"] = "Carpeta"
        _pending_selection["display_path"] = str(folder)
        _pending_selection["paths"] = [str(folder)]
        _pending_selection["base_folder"] = str(folder)
        _load_status["progress_pct"] = 0
        _load_status["status_text"] = "Carpeta seleccionada. Pulsa 'Cargar' para escanear."

    return get_state()


@app.route("/api/select-files", methods=["POST"])
def select_files():
    if _load_status["is_loading"] or _conversion_status["is_converting"]:
        return jsonify({"error": "Proceso en curso"}), 400

    chosen = _native_pick_files(str(_config["last_browse_dir"]))
    if not chosen:
        return get_state()

    resolved_list = [str(Path(p).resolve()) for p in chosen if Path(p).exists()]
    if not resolved_list:
        return get_state()

    first_p = Path(resolved_list[0])
    display = first_p.name if len(resolved_list) == 1 else f"{len(resolved_list)} archivos PDF ({first_p.parent.name})"

    with _state_lock:
        _config["last_browse_dir"] = str(first_p.parent)
        _pending_selection["has_selection"] = True
        _pending_selection["mode"] = "Individual"
        _pending_selection["display_path"] = display
        _pending_selection["paths"] = resolved_list
        _pending_selection["base_folder"] = str(first_p.parent)
        _load_status["progress_pct"] = 0
        _load_status["status_text"] = "Archivo(s) seleccionado(s). Pulsa 'Cargar'."

    return get_state()


def _load_worker(mode: str, raw_paths: List[str], base_folder_str: str, recursive: bool) -> None:
    global _next_item_id
    try:
        pdf_candidates: List[Path] = []
        if mode == "Carpeta" and raw_paths:
            folder = Path(raw_paths[0])
            pattern = "**/*.pdf" if recursive else "*.pdf"
            pdf_candidates = sorted(
                [p.resolve() for p in folder.glob(pattern) if p.is_file()],
                key=lambda x: x.name.lower(),
            )
        else:
            for rp in raw_paths:
                p = Path(rp).resolve()
                if p.is_file() and p.suffix.lower() == ".pdf":
                    pdf_candidates.append(p)

        total = len(pdf_candidates)
        _load_status["total"] = total
        _load_status["current"] = 0

        if total == 0:
            _load_status["progress_pct"] = 100
            _load_status["status_text"] = "No se encontraron archivos PDF."
            _load_status["is_loading"] = False
            return

        existing_paths = {Path(str(item["path"])).resolve() for item in _queue}
        added_count = 0

        for idx, pdf_path in enumerate(pdf_candidates, start=1):
            _load_status["current"] = idx
            _load_status["progress_pct"] = round((idx / total) * 100)
            _load_status["status_text"] = f"Cargando {idx} de {total}: {pdf_path.name}"

            if pdf_path in existing_paths:
                continue

            size_kb = pdf_path.stat().st_size / 1024.0
            pages_count = max(1, int(size_kb / 45))
            if fitz is not None and total <= 12:
                try:
                    doc = fitz.open(pdf_path)
                    pages_count = max(1, len(doc))
                    doc.close()
                except Exception:
                    pass

            with _state_lock:
                item_id = _next_item_id
                _next_item_id += 1
                _queue.append({
                    "id": item_id,
                    "name": pdf_path.name,
                    "path": str(pdf_path),
                    "folder": str(pdf_path.parent),
                    "base_folder": base_folder_str,
                    "origin_mode": mode,
                    "size_kb": round(size_kb, 1),
                    "size_mb": round(size_kb / 1024.0, 2),
                    "pages": pages_count,
                    "status": "pending",
                    "message": "Pendiente",
                    "epub_path": "",
                })
                existing_paths.add(pdf_path)
                added_count += 1

        _load_status["progress_pct"] = 100
        _load_status["status_text"] = f"Carga completada: {added_count} archivo(s) listos."
        _pending_selection["has_selection"] = False
    finally:
        _load_status["is_loading"] = False


@app.route("/api/load/start", methods=["POST"])
def start_loading():
    if _load_status["is_loading"] or _conversion_status["is_converting"]:
        return jsonify({"error": "Proceso en curso"}), 400
    if not _pending_selection["has_selection"]:
        return jsonify({"error": "Primero selecciona una carpeta o archivo PDF"}), 400

    with _state_lock:
        _load_status["is_loading"] = True
        _load_status["progress_pct"] = 0
        _load_status["current"] = 0
        _load_status["total"] = 0
        _load_status["status_text"] = "Escaneando selección..."

        mode = str(_pending_selection["mode"])
        paths = list(_pending_selection["paths"])
        base_f = str(_pending_selection["base_folder"])
        rec = bool(_config["recursive_scan"])

    t = threading.Thread(target=_load_worker, args=(mode, paths, base_f, rec), daemon=True)
    t.start()
    return get_state()


@app.route("/api/pick-output", methods=["POST"])
def pick_output_folder():
    chosen_dir = _native_pick_folder(
        str(_config["output_dir"]),
        "Selecciona la carpeta de salida para los EPUBs",
    )
    if chosen_dir:
        with _state_lock:
            _config["output_dir"] = str(Path(chosen_dir).resolve())
    return get_state()


@app.route("/api/queue/remove", methods=["POST"])
def remove_queue_item():
    if _conversion_status["is_converting"]:
        return jsonify({"error": "Conversión en curso"}), 400
    data = request.get_json(silent=True) or {}
    item_id = data.get("id")
    with _state_lock:
        _queue[:] = [i for i in _queue if i["id"] != item_id]
    return get_state()


@app.route("/api/queue/clear", methods=["POST"])
def clear_queue():
    if _conversion_status["is_converting"]:
        return jsonify({"error": "Conversión en curso"}), 400
    with _state_lock:
        _queue.clear()
        _conversion_status["progress_pct"] = 0
        _conversion_status["eta_text"] = ""
        _conversion_status["status_text"] = "Listo"
    return get_state()


def _conversion_worker(target_indices: List[int]) -> None:
    converter = PdfToEpubConverter()
    out_root = Path(str(_config["output_dir"]))
    total_batch = len(target_indices)
    ok_count = sum(1 for i in _queue if i["status"] == "ok")
    fail_count = 0

    total_pages = max(1, sum(max(1, int(_queue[i].get("pages", 10))) for i in target_indices))
    done_pages_before_book = 0
    start_time = time.perf_counter()
    avg_sec_per_page = 0.012

    _add_log("INFO", "EPUB", f"Iniciando conversión de {total_batch} archivo(s) PDF -> {out_root}")

    for step_idx, q_idx in enumerate(target_indices):
        item = _queue[q_idx]
        if _conversion_status["stop_requested"]:
            _conversion_status["status_text"] = "⏸️ Conversión pausada. Puedes pulsar 'Continuar / Reintentar'."
            _conversion_status["eta_text"] = "Pausado"
            _add_log("WARN", "EPUB", f"Conversión detenida por el usuario en el archivo #{step_idx + 1}/{total_batch}.")
            break

        item["status"] = "converting"
        item["message"] = "Convirtiendo..."
        _conversion_status["current_idx"] = step_idx + 1

        pdf_path = Path(str(item["path"]))
        base_folder = Path(str(item["base_folder"]))
        origin_mode = str(item["origin_mode"])

        try:
            rel_parent = pdf_path.parent.relative_to(base_folder) if origin_mode == "Carpeta" else Path()
        except ValueError:
            rel_parent = Path()

        target_epub = out_root / rel_parent / f"{pdf_path.stem}.epub"
        est_item_pages = max(1, int(item.get("pages", 10)))

        def _on_page(cur_p: int, tot_p: int) -> None:
            nonlocal total_pages, avg_sec_per_page
            if tot_p != est_item_pages:
                total_pages = max(1, total_pages - est_item_pages + tot_p)
                item["pages"] = tot_p
            cur_done = done_pages_before_book + cur_p
            elapsed_now = time.perf_counter() - start_time
            if cur_done > 0:
                avg_sec_per_page = elapsed_now / cur_done
            pct = min(99, round((cur_done / max(1, total_pages)) * 100))
            rem_p = max(0, total_pages - cur_done)
            rem_s = rem_p * avg_sec_per_page
            _conversion_status["progress_pct"] = pct
            _conversion_status["eta_seconds"] = int(round(rem_s))
            _conversion_status["eta_text"] = _format_eta(rem_s)
            _conversion_status["status_text"] = (
                f"Convirtiendo {step_idx + 1}/{total_batch}: {item['name']} (pág. {cur_p}/{tot_p})"
            )
            item["message"] = f"Pág. {cur_p}/{tot_p}..."

        success, msg, stats = converter.convert_file(pdf_path, target_epub, page_callback=_on_page)

        item_pages = max(1, stats.get("pages", 0) or int(item.get("pages", 10)))
        done_pages_before_book += item_pages
        elapsed = time.perf_counter() - start_time
        if done_pages_before_book > 0:
            avg_sec_per_page = elapsed / done_pages_before_book

        item["message"] = msg
        if success:
            ok_count += 1
            item["status"] = "ok"
            item["epub_path"] = str(target_epub)
            _add_log("OK", "EPUB", f"[{step_idx + 1}/{total_batch}] {item['name']} -> {msg}")
        else:
            fail_count += 1
            item["status"] = "error"
            _add_log("ERROR", "EPUB", f"[{step_idx + 1}/{total_batch}] {item['name']} -> {msg}")

        _conversion_status["ok_count"] = ok_count
        _conversion_status["fail_count"] = fail_count
        _conversion_status["progress_pct"] = round(((step_idx + 1) / total_batch) * 100) if total_batch > 0 else 100

        rem_pages_after = max(0, total_pages - done_pages_before_book)
        rem_sec_after = rem_pages_after * avg_sec_per_page
        _conversion_status["eta_seconds"] = int(round(rem_sec_after))
        _conversion_status["eta_text"] = _format_eta(rem_sec_after) if rem_pages_after > 0 else "0 s"

    total_elapsed = time.perf_counter() - start_time
    _conversion_status["is_converting"] = False
    was_stopped = bool(_conversion_status["stop_requested"])
    _conversion_status["stop_requested"] = False
    if not was_stopped:
        _conversion_status["eta_text"] = "Completado"
        _conversion_status["status_text"] = (
            f"Finalizado en {total_elapsed:.1f}s ({ok_count} convertidos, {fail_count} fallidos)"
        )
        _add_log("INFO", "EPUB", f"Conversión finalizada en {total_elapsed:.1f}s: {ok_count} OK, {fail_count} con error.")


@app.route("/api/convert/start", methods=["POST"])
def start_conversion():
    if _conversion_status["is_converting"] or _load_status["is_loading"]:
        return jsonify({"error": "Proceso en curso"}), 400
    if not _queue:
        return jsonify({"error": "Primero carga archivos PDF en la lista"}), 400

    data = request.get_json(silent=True) or {}
    mode = str(data.get("mode", "continue"))  # "continue" | "retry" | "force_all"

    with _state_lock:
        if mode == "force_all":
            for i in _queue:
                i["status"] = "pending"
                i["message"] = "Pendiente"
        elif mode == "retry":
            for i in _queue:
                if i["status"] == "error":
                    i["status"] = "pending"
                    i["message"] = "Listo para reintentar"

        target_indices = [idx for idx, i in enumerate(_queue) if i["status"] in ("pending", "error")]
        if not target_indices:
            # Si todos ya estaban en 'ok' y el usuario pulsa convertir de nuevo, reconvertir todos
            for i in _queue:
                i["status"] = "pending"
            target_indices = list(range(len(_queue)))

        total_pages = sum(max(1, int(_queue[i].get("pages", 10))) for i in target_indices)
        initial_eta = total_pages * 0.012

        _conversion_status["is_converting"] = True
        _conversion_status["stop_requested"] = False
        _conversion_status["progress_pct"] = 0
        _conversion_status["current_idx"] = 0
        _conversion_status["total"] = len(target_indices)
        _conversion_status["ok_count"] = sum(1 for i in _queue if i["status"] == "ok")
        _conversion_status["fail_count"] = 0
        _conversion_status["eta_seconds"] = int(round(initial_eta))
        _conversion_status["eta_text"] = _format_eta(initial_eta)
        _conversion_status["status_text"] = f"Iniciando ({len(target_indices)} archivo(s) pendientes)..."

    worker = threading.Thread(target=_conversion_worker, args=(target_indices,), daemon=True)
    worker.start()
    return get_state()


@app.route("/api/convert/stop", methods=["POST"])
def stop_conversion():
    if _conversion_status["is_converting"]:
        _conversion_status["stop_requested"] = True
        _conversion_status["status_text"] = "Deteniendo..."
    return get_state()


# ==============================================================================
# FUNCIÓN 2: CARGAR LIBROS AL KINDLE POR CABLE USB
# ==============================================================================

@app.route("/api/usb/select-converted", methods=["POST"])
def usb_select_converted():
    """Selecciona automáticamente la carpeta de salida de EPUBs convertidos."""
    out_dir = Path(str(_config["output_dir"])).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    with _state_lock:
        _usb_pending["has_selection"] = True
        _usb_pending["mode"] = "Carpeta"
        _usb_pending["display_path"] = str(out_dir)
        _usb_pending["paths"] = [str(out_dir)]
        _usb_load_status["progress_pct"] = 0
        _usb_load_status["status_text"] = "Carpeta de EPUBs convertidos seleccionada. Pulsa 'Cargar'."
    return get_state()


@app.route("/api/usb/select-folder", methods=["POST"])
def usb_select_folder():
    if _usb_load_status["is_loading"] or _usb_transfer_status["is_transferring"]:
        return jsonify({"error": "Proceso en curso"}), 400

    chosen_dir = _native_pick_folder(
        str(_config["output_dir"]),
        "Selecciona la carpeta con tus libros (.epub, .azw, .mobi, .pdf)",
    )
    if not chosen_dir:
        return get_state()

    folder = Path(chosen_dir).resolve()
    with _state_lock:
        _usb_pending["has_selection"] = True
        _usb_pending["mode"] = "Carpeta"
        _usb_pending["display_path"] = str(folder)
        _usb_pending["paths"] = [str(folder)]
        _usb_load_status["progress_pct"] = 0
        _usb_load_status["status_text"] = "Carpeta seleccionada. Pulsa 'Cargar'."
    return get_state()


@app.route("/api/usb/select-files", methods=["POST"])
def usb_select_files():
    if _usb_load_status["is_loading"] or _usb_transfer_status["is_transferring"]:
        return jsonify({"error": "Proceso en curso"}), 400

    chosen = _native_pick_files(
        str(_config["output_dir"]),
        "Libros (*.epub;*.azw;*.azw3;*.mobi;*.pdf)|*.epub;*.azw;*.azw3;*.mobi;*.pdf|Todos (*.*)|*.*",
    )
    if not chosen:
        return get_state()

    resolved_list = [str(Path(p).resolve()) for p in chosen if Path(p).exists()]
    if not resolved_list:
        return get_state()

    first_p = Path(resolved_list[0])
    display = first_p.name if len(resolved_list) == 1 else f"{len(resolved_list)} libros seleccionados ({first_p.parent.name})"

    with _state_lock:
        _usb_pending["has_selection"] = True
        _usb_pending["mode"] = "Individual"
        _usb_pending["display_path"] = display
        _usb_pending["paths"] = resolved_list
        _usb_load_status["progress_pct"] = 0
        _usb_load_status["status_text"] = "Libro(s) seleccionado(s). Pulsa 'Cargar'."
    return get_state()


def _usb_load_worker(mode: str, raw_paths: List[str], recursive: bool) -> None:
    global _next_usb_id
    valid_exts = {".epub", ".azw", ".azw3", ".mobi", ".pdf"}
    try:
        candidates: List[Path] = []
        if mode == "Carpeta" and raw_paths:
            folder = Path(raw_paths[0])
            if folder.exists():
                it = folder.rglob("*") if recursive else folder.glob("*")
                candidates = sorted(
                    [p.resolve() for p in it if p.is_file() and p.suffix.lower() in valid_exts],
                    key=lambda x: x.name.lower(),
                )
        else:
            for rp in raw_paths:
                p = Path(rp).resolve()
                if p.is_file() and p.suffix.lower() in valid_exts:
                    candidates.append(p)

        total = len(candidates)
        _usb_load_status["total"] = total
        _usb_load_status["current"] = 0

        if total == 0:
            _usb_load_status["progress_pct"] = 100
            _usb_load_status["status_text"] = "No se encontraron libros (.epub/.mobi/.azw) en la selección."
            _usb_load_status["is_loading"] = False
            return

        existing_paths = {Path(str(item["path"])).resolve() for item in _usb_queue}
        added_count = 0

        for idx, book_path in enumerate(candidates, start=1):
            _usb_load_status["current"] = idx
            _usb_load_status["progress_pct"] = round((idx / total) * 100)
            _usb_load_status["status_text"] = f"Cargando {idx} de {total}: {book_path.name}"

            if book_path in existing_paths:
                continue

            size_kb = book_path.stat().st_size / 1024.0
            with _state_lock:
                uid = _next_usb_id
                _next_usb_id += 1
                _usb_queue.append({
                    "id": uid,
                    "name": book_path.name,
                    "ext": book_path.suffix.upper().lstrip("."),
                    "path": str(book_path),
                    "folder": str(book_path.parent),
                    "size_kb": round(size_kb, 1),
                    "size_mb": round(size_kb / 1024.0, 2),
                    "status": "pending",
                    "message": "Listo para enviar a Kindle",
                    "dest_path": "",
                })
                existing_paths.add(book_path)
                added_count += 1

        _usb_load_status["progress_pct"] = 100
        _usb_load_status["status_text"] = f"Carga completada: {added_count} libro(s) listos."
        _usb_pending["has_selection"] = False
    finally:
        _usb_load_status["is_loading"] = False


@app.route("/api/usb/load/start", methods=["POST"])
def usb_start_loading():
    if _usb_load_status["is_loading"] or _usb_transfer_status["is_transferring"]:
        return jsonify({"error": "Proceso en curso"}), 400
    if not _usb_pending["has_selection"]:
        return jsonify({"error": "Primero selecciona una carpeta o archivo de libro"}), 400

    with _state_lock:
        _usb_load_status["is_loading"] = True
        _usb_load_status["progress_pct"] = 0
        _usb_load_status["current"] = 0
        _usb_load_status["total"] = 0
        _usb_load_status["status_text"] = "Escaneando libros..."

        mode = str(_usb_pending["mode"])
        paths = list(_usb_pending["paths"])
        rec = bool(_config["recursive_scan"])

    t = threading.Thread(target=_usb_load_worker, args=(mode, paths, rec), daemon=True)
    t.start()
    return get_state()


@app.route("/api/usb/detect-kindle", methods=["POST"])
def usb_detect_kindle():
    found = KindleUsbPacker.detect_connected_kindle_Folders()
    with _state_lock:
        if found:
            current_k = str(_config.get("kindle_usb_dir", "")).strip()
            valid_paths = {f["path"] for f in found}
            if not current_k or current_k not in valid_paths:
                _config["kindle_usb_dir"] = found[0]["path"]
    return jsonify({
        "detected": found,
        "kindle_usb_dir": _config["kindle_usb_dir"],
    })


@app.route("/api/usb/pick-kindle-dir", methods=["POST"])
def usb_pick_kindle_dir():
    chosen = KindleUsbPacker.pick_kindle_folder_dialog(
        "Selecciona tu Kindle (ej. Kindle Paperwhite -> Internal Storage -> documents)"
    )
    if chosen:
        with _state_lock:
            if chosen.lower().startswith("mtp://"):
                _config["kindle_usb_dir"] = chosen
            else:
                _config["kindle_usb_dir"] = str(Path(chosen).resolve())
    return get_state()


@app.route("/api/usb/queue/remove", methods=["POST"])
def usb_remove_item():
    if _usb_transfer_status["is_transferring"]:
        return jsonify({"error": "Transferencia en curso"}), 400
    data = request.get_json(silent=True) or {}
    item_id = data.get("id")
    with _state_lock:
        _usb_queue[:] = [i for i in _usb_queue if i["id"] != item_id]
    return get_state()


@app.route("/api/usb/queue/clear", methods=["POST"])
def usb_clear_queue():
    if _usb_transfer_status["is_transferring"]:
        return jsonify({"error": "Transferencia en curso"}), 400
    with _state_lock:
        _usb_queue.clear()
        _usb_transfer_status["progress_pct"] = 0
        _usb_transfer_status["eta_text"] = ""
        _usb_transfer_status["status_text"] = "Listo"
    return get_state()


def _usb_transfer_worker(target_indices: List[int]) -> None:
    kindle_dir_str = str(_config["kindle_usb_dir"]).strip()
    usb_fmt = str(_config.get("usb_format", "mobi"))
    total_batch = len(target_indices)
    ok_count = sum(1 for i in _usb_queue if i["status"] == "ok")
    fail_count = 0
    consecutive_mtp_errors = 0

    start_time = time.perf_counter()
    avg_sec_per_book = 0.7 if kindle_dir_str.lower().startswith("mtp://") else 0.25

    _add_log(
        "INFO",
        "USB",
        f"Iniciando envío al Kindle ({total_batch} libro(s) en lote) -> Destino: {kindle_dir_str} | Formato: .{usb_fmt.upper()} + .sdr",
    )

    auto_paused_disconnect = False

    for step_idx, q_idx in enumerate(target_indices):
        item = _usb_queue[q_idx]
        if _usb_transfer_status["stop_requested"]:
            _usb_transfer_status["status_text"] = "⏸️ Transferencia pausada. Pulsa 'Continuar / Reintentar' para seguir."
            _usb_transfer_status["eta_text"] = "Pausado"
            _add_log("WARN", "USB", f"Transferencia pausada por el usuario en el libro #{step_idx + 1}/{total_batch}.")
            break

        item["status"] = "converting"
        item["message"] = "Enviando al Kindle..."
        _usb_transfer_status["current_idx"] = step_idx + 1

        rem_books = max(1, total_batch - step_idx)
        est_sec = rem_books * avg_sec_per_book
        _usb_transfer_status["eta_seconds"] = int(round(est_sec))
        _usb_transfer_status["eta_text"] = _format_eta(est_sec)
        _usb_transfer_status["status_text"] = f"Enviando {step_idx + 1} de {total_batch}: {item['name']}"

        src_path = Path(str(item["path"]))
        t_book = time.perf_counter()
        success, msg, dest_p = KindleUsbPacker.transfer_book_to_kindle_usb(
            src_path, kindle_dir_str, usb_format=usb_fmt
        )
        book_sec = time.perf_counter() - t_book

        elapsed = time.perf_counter() - start_time
        avg_sec_per_book = elapsed / (step_idx + 1)

        item["message"] = msg
        if success:
            ok_count += 1
            consecutive_mtp_errors = 0
            item["status"] = "ok"
            item["dest_path"] = dest_p
            _add_log("OK", "USB", f"[{step_idx + 1}/{total_batch}] {item['name']} -> {msg} ({book_sec:.2f}s)")
        else:
            fail_count += 1
            item["status"] = "error"
            _add_log("ERROR", "USB", f"[{step_idx + 1}/{total_batch}] {item['name']} -> {msg}")
            if "desconectado" in msg.lower() or "mtp" in msg.lower():
                consecutive_mtp_errors += 1
                if consecutive_mtp_errors >= 3:
                    auto_paused_disconnect = True
                    _usb_transfer_status["status_text"] = (
                        "⏸️ Pausado automático: Kindle desconectado. Reconecta el cable USB y pulsa 'Reintentar / Continuar'."
                    )
                    _usb_transfer_status["eta_text"] = "Esperando Kindle"
                    _add_log(
                        "WARN",
                        "USB",
                        "Se detectaron 3 errores consecutivos de conexión MTP. Cola pausada automáticamente para conservar el punto donde quedó.",
                    )
                    break

        _usb_transfer_status["ok_count"] = ok_count
        _usb_transfer_status["fail_count"] = sum(1 for i in _usb_queue if i["status"] == "error")
        _usb_transfer_status["progress_pct"] = round(((step_idx + 1) / total_batch) * 100) if total_batch > 0 else 100

        rem_after = max(0, total_batch - (step_idx + 1))
        rem_sec_after = rem_after * avg_sec_per_book
        _usb_transfer_status["eta_seconds"] = int(round(rem_sec_after))
        _usb_transfer_status["eta_text"] = _format_eta(rem_sec_after) if rem_after > 0 else "0 s"

    total_elapsed = time.perf_counter() - start_time
    was_stopped = bool(_usb_transfer_status["stop_requested"])
    _usb_transfer_status["is_transferring"] = False
    _usb_transfer_status["stop_requested"] = False
    total_err_now = sum(1 for i in _usb_queue if i["status"] == "error")
    total_pend_now = sum(1 for i in _usb_queue if i["status"] == "pending")

    if not was_stopped and not auto_paused_disconnect:
        _usb_transfer_status["eta_text"] = "Completado"
        _usb_transfer_status["status_text"] = (
            f"Finalizado en {total_elapsed:.1f}s ({ok_count} en Kindle, {total_err_now} fallidos, {total_pend_now} pendientes)"
        )
        _add_log(
            "INFO",
            "USB",
            f"Proceso finalizado en {total_elapsed:.1f}s: {ok_count} en Kindle, {total_err_now} fallidos, {total_pend_now} pendientes.",
        )


@app.route("/api/usb/transfer/start", methods=["POST"])
def usb_start_transfer():
    if _usb_transfer_status["is_transferring"] or _usb_load_status["is_loading"]:
        return jsonify({"error": "Proceso en curso"}), 400
    if not _usb_queue:
        return jsonify({"error": "Primero carga libros en la lista para enviar al Kindle"}), 400

    kdir = str(_config.get("kindle_usb_dir", "")).strip()
    if not kdir:
        return jsonify({"error": "Selecciona o auto-detecta primero tu Kindle conectado por USB"}), 400

    data = request.get_json(silent=True) or {}
    mode = str(data.get("mode", "continue"))  # "continue" | "retry" | "force_all"

    with _state_lock:
        if mode == "force_all":
            for i in _usb_queue:
                i["status"] = "pending"
                i["message"] = "Listo para enviar a Kindle"
        elif mode == "retry":
            for i in _usb_queue:
                if i["status"] == "error":
                    i["status"] = "pending"
                    i["message"] = "Listo para reintentar"

        target_indices = [idx for idx, i in enumerate(_usb_queue) if i["status"] in ("pending", "error")]
        if not target_indices:
            for i in _usb_queue:
                i["status"] = "pending"
                i["message"] = "Listo para reenviar"
            target_indices = list(range(len(_usb_queue)))

        initial_eta = len(target_indices) * (0.7 if kdir.lower().startswith("mtp://") else 0.25)

        _usb_transfer_status["is_transferring"] = True
        _usb_transfer_status["stop_requested"] = False
        _usb_transfer_status["progress_pct"] = 0
        _usb_transfer_status["current_idx"] = 0
        _usb_transfer_status["total"] = len(target_indices)
        _usb_transfer_status["ok_count"] = sum(1 for i in _usb_queue if i["status"] == "ok")
        _usb_transfer_status["fail_count"] = sum(1 for i in _usb_queue if i["status"] == "error")
        _usb_transfer_status["eta_seconds"] = int(round(initial_eta))
        _usb_transfer_status["eta_text"] = _format_eta(initial_eta)
        _usb_transfer_status["status_text"] = f"Enviando {len(target_indices)} libro(s) restantes al Kindle..."

    worker = threading.Thread(target=_usb_transfer_worker, args=(target_indices,), daemon=True)
    worker.start()
    return get_state()


@app.route("/api/usb/transfer/stop", methods=["POST"])
def usb_stop_transfer():
    if _usb_transfer_status["is_transferring"]:
        _usb_transfer_status["stop_requested"] = True
        _usb_transfer_status["status_text"] = "Deteniendo..."
    return get_state()


@app.route("/api/open-location", methods=["POST"])
def open_location():
    data = request.get_json(silent=True) or {}
    target_type = data.get("type", "output")
    item_id = data.get("id")

    if target_type == "item" and item_id is not None:
        item = next((i for i in _queue if i["id"] == item_id), None)
        if item and item.get("epub_path") and Path(str(item["epub_path"])).exists():
            epub_p = Path(str(item["epub_path"])).resolve()
            if sys.platform.startswith("win"):
                subprocess.Popen(["explorer", f"/select,{epub_p}"])
            return jsonify({"opened": str(epub_p)})

    if target_type == "usb_item" and item_id is not None:
        item = next((i for i in _usb_queue if i["id"] == item_id), None)
        if item and item.get("dest_path"):
            dp_str = str(item["dest_path"])
            if dp_str.lower().startswith("mtp://"):
                parent_mtp = dp_str.rsplit("/", 1)[0]
                KindleUsbPacker.open_mtp_folder_in_explorer(parent_mtp)
                return jsonify({"opened": parent_mtp})
            elif Path(dp_str).exists():
                dest_p = Path(dp_str).resolve()
                if sys.platform.startswith("win"):
                    subprocess.Popen(["explorer", f"/select,{dest_p}"])
                return jsonify({"opened": str(dest_p)})

    if target_type == "kindle":
        kdir = str(_config.get("kindle_usb_dir", "")).strip()
        if kdir.lower().startswith("mtp://"):
            KindleUsbPacker.open_mtp_folder_in_explorer(kdir)
            return jsonify({"opened": kdir})
        elif kdir and Path(kdir).exists():
            if sys.platform.startswith("win"):
                os.startfile(str(Path(kdir).resolve()))
            return jsonify({"opened": kdir})

    if target_type == "logfile":
        if not _LOG_FILE.exists():
            _add_log("INFO", "SYS", "Archivo de log inicializado.")
        if sys.platform.startswith("win") and _LOG_FILE.exists():
            os.startfile(str(_LOG_FILE.resolve()))
        return jsonify({"opened": str(_LOG_FILE)})

    out_dir = Path(str(_config["output_dir"]))
    out_dir.mkdir(parents=True, exist_ok=True)
    if sys.platform.startswith("win"):
        os.startfile(str(out_dir))
    return jsonify({"opened": str(out_dir)})
