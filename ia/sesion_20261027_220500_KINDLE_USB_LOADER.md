# Sesión IA: Menú Desplegable de Funciones + Cargador Kindle por Cable USB (`.azw` + `.sdr`)

- **Fecha:** 2026-10-27 22:05:00
- **Proyecto:** Reflowia PDF to EPUB
- **Archivo único de sesión:** `ia/sesion_20261027_220500_KINDLE_USB_LOADER.md`

---

## 1. Objetivo de la Sesión
1. Incorporar un **menú desplegable (`<select id="func-select">`)** en la parte superior del panel izquierdo para separar las herramientas de la aplicación sin recargar visualmente la interfaz.
2. Agregar la **Función 2: Cargar Libros al Kindle (USB)** para enviar los libros convertidos directamente al Kindle conectado por cable USB a la PC.
3. Replicar la estructura nativa de la carpeta `documents/` del Kindle mostrada por el usuario:
   - Archivo principal compatible con lectura directa por cable USB: `<Título>_<ASIN>.azw` (o `.mobi` / `.epub`).
   - Carpeta compañera `<Título>_<ASIN>.sdr` (Sidecar Data Record) donde el Kindle almacena el progreso de lectura, notas y marcadores.
4. Mantener el flujo visual requerido por el usuario:
   - Selección explícita + botón **"📥 Cargar"** con barra de progreso (`0% - 100%`).
   - Botón de acción principal (**"📲 Enviar al Kindle por USB"**) con barra de progreso (`0% - 100%`) y **tiempo estimado restante (`Tiempo estimado:`)**.

---

## 2. Cambios Implementados

### 2.1. Motor `KindleUsbPacker` en `converter.py`
- **`detect_kindle_drives()`**: Escanea unidades montadas (`D:\` a `Z:\`) identificando aquellas que contienen la carpeta `documents/` o marcadores propios de Kindle (`.sdr`, `.azw`, `.kfx`, `system`).
- **`extract_epub_data(epub_path)`**: Extrae metadatos (`dc:title`, `dc:creator`), portada JPEG y capítulos XHTML desde cualquier archivo `.epub` generado.
- **`build_palm_mobi_bytes(...)`**: Empaqueta en Python puro (sin requerir herramientas externas instaladas) un contenedor binario **PalmDB / MOBI (`BOOKMOBI`)** codificado en UTF-8 (`65001`) con cabeceras **EXTH** (`cde_type = EBOK`, `ASIN = B0...`, `Author`, `UpdatedTitle`, `CoverOffset`) e imagen de portada integrada, o usa `ebook-convert` de Calibre automáticamente si está disponible en el sistema.
- **`transfer_book_to_kindle_usb(...)`**: Genera en la carpeta `documents/` del Kindle el archivo `<Nombre>_<ASIN>.azw` junto con su carpeta `<Nombre>_<ASIN>.sdr`.

### 2.2. Nuevos Endpoints en `server.py`
- `/api/usb/select-converted`: Selecciona automáticamente la carpeta de salida donde se guardaron los EPUB convertidos en la Función 1.
- `/api/usb/select-folder` y `/api/usb/select-files`: Selección de carpeta o archivos individuales (`.epub`, `.azw`, `.azw3`, `.mobi`, `.kfx`).
- `/api/usb/load/start`: Carga los libros seleccionados mostrando la barra de progreso de carga (`0% - 100%`).
- `/api/usb/detect-kindle` y `/api/usb/pick-kindle-dir`: Auto-detección de la carpeta `documents/` del Kindle por USB o selección manual.
- `/api/usb/transfer/start` y `/api/usb/transfer/stop`: Transferencia y empaquetado `.azw` + `.sdr` en segundo plano con cálculo de **ETA (`Tiempo estimado`)** y barra de progreso en tiempo real.

### 2.3. Interfaz SPA con Menú Desplegable en `templates/index.html`
- Selector superior **Función Activa** que alterna limpiamente entre:
  1. `⚡ 1. Convertir PDF a EPUB`
  2. `🔌 2. Cargar Libros al Kindle (USB)`
- Cada modo tiene su propia barra superior de resumen, su propia tabla en el panel derecho y sus propios controles en la barra lateral, manteniendo la pantalla limpia y ligera.



---

## 3. Soporte Nativo para Kindles MTP (`Kindle Paperwhite` / `Scribe` / `Colorsoft`)
- **Causa identificada:** Los modelos modernos de Kindle (como `Kindle Paperwhite` con firmware 5.16.3+) se montan en Windows 11 como **Dispositivo Portátil MTP (`Portable Device`)** bajo `Este equipo` sin letra de unidad (`D:`, `E:`), por lo que el selector clásico `FOS_FORCEFILESYSTEM` los oculta.
- **Solución implementada en `KindleUsbPacker`:**
  1. **`detect_connected_kindle_Folders()`**: Consulta el espacio de nombres `Shell.Application.NameSpace(17)` (`Este equipo`) detectando automáticamente `mtp://Kindle Paperwhite/Internal Storage/documents/Downloads/Items01` y `mtp://Kindle Paperwhite/Internal Storage/documents` (además de unidades USB con letra).
  2. **`pick_kindle_folder_dialog()`**: Abre el diálogo del Shell de Windows enraizado en `Este equipo` (`17`), donde `Kindle Paperwhite` sí aparece y puede seleccionarse directamente.
  3. **`copy_package_to_mtp()`**: Empaqueta el libro `.azw` / `.mobi` / `.epub` en un directorio temporal local y lo transfiere vía `Shell.Application` (`CopyHere` + `NewFolder` para la carpeta `.sdr`) directamente al almacenamiento interno MTP del Kindle.
