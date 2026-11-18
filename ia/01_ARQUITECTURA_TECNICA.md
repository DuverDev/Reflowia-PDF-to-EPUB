# 🏗️ Arquitectura Técnica — Reflowia PDF to EPUB

## 1. Visión General
- **Propósito:** Suite de escritorio ligera con **menú desplegable de funciones** para:
  1. **Convertir PDF a EPUB (`#panel-convert`):** Convierte documentos PDF (individuales o por carpetas completas) a libros electrónicos EPUB con diseño fluido universal compatible con todos los tamaños y modelos de Amazon Kindle.
  2. **Cargar Libros al Kindle por Cable USB (`#panel-usb`):** Empaqueta y transfiere los libros convertidos directamente a la carpeta `documents/` del Kindle conectado por cable USB, generando el archivo nativo `<Nombre>_<ASIN>.azw` junto con su carpeta compañera `<Nombre>_<ASIN>.sdr`.
- **Portabilidad:** Empaquetado en un único ejecutable (`dist/Reflowia PDF to EPUB.exe`) sin dependencias externas. La carpeta `ia/` pertenece exclusivamente al repositorio de código para documentación y registro de sesiones de desarrollo con IA.

---

## 2. Selector de Función en Menú Desplegable (`<select id="func-select">`)
Para mantener una interfaz visualmente limpia y ligera, el panel lateral izquierdo incluye un selector desplegable superior que alterna dinámicamente entre los módulos de la aplicación:
- **`convert` (`⚡ 1. Convertir PDF a EPUB`):** Muestra únicamente los controles de selección de PDFs, carga con barra de progreso, carpeta de destino y conversión a EPUB con tiempo estimado.
- **`usb` (`🔌 2. Cargar Libros al Kindle (USB)`):** Muestra únicamente los controles para cargar libros convertidos, detectar la unidad USB del Kindle (`documents/`), elegir el modo de empaquetado (`.azw + .sdr`, `.mobi + .sdr` o `.epub + .sdr`) y transferir con barra de progreso y tiempo estimado.

---

## 3. Flujo de Interfaz Ligera (3 Pasos en Ambos Módulos)
1. **Selección Previa:**
   - Función 1: `/api/select-folder` y `/api/select-files` muestran la ruta seleccionada en `#sel-box`.
   - Función 2: `/api/usb/select-converted`, `/api/usb/select-folder` y `/api/usb/select-files` muestran la ruta seleccionada en `#usb-sel-box`.
2. **Botón "📥 Cargar" con Barra de Progreso (`0% - 100%`):**
   - Escanea la carpeta o archivos seleccionados mostrando una barra de progreso en tiempo real antes de poblar la tabla derecha.
3. **Botón de Acción Principal con Barra de Progreso y Tiempo Estimado (`ETA`):**
   - **Función 1 (`⚡ Convertir a EPUB`):** Convierte los PDFs cargados a formato EPUB universal mostrando porcentaje y `Tiempo estimado:`.
   - **Función 2 (`📲 Enviar al Kindle por USB`):** Empaqueta cada libro en formato compatible con lectura USB directa en Kindle (`<Título>_<ASIN>.azw` + carpeta `<Título>_<ASIN>.sdr`) dentro de `Kindle/documents/` mostrando porcentaje y `Tiempo estimado:`.
