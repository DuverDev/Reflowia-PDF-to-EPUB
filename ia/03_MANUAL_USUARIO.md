# 📖 Manual de Usuario — Reflowia PDF to EPUB

## 1. Ejecución Portable (Un Solo Ejecutable)
1. Ve a la carpeta `dist/` y haz doble clic en **`Reflowia PDF to EPUB.exe`** (o ejecuta `run_app.bat` en modo desarrollo).
2. En la parte superior izquierda encontrarás el **menú desplegable `Función Activa`**, desde donde puedes alternar entre las funciones sin recargar visualmente la pantalla:
   - **⚡ 1. Convertir PDF a EPUB**
   - **🔌 2. Cargar Libros al Kindle (USB)**

---

## 2. Función 1: Convertir PDF a EPUB Universal
1. En el menú desplegable elige **⚡ 1. Convertir PDF a EPUB**.
2. En **1. Seleccionar Origen**, elige **📁 Carpeta** o **📄 PDF(s)**. Verás la ruta elegida en el recuadro *"Seleccionado:"*.
3. Pulsa **📥 Cargar**: se mostrará una **barra de progreso de carga (`0% - 100%`)** mientras se analizan los PDFs y se agregan a la tabla.
4. Pulsa **⚡ Convertir a EPUB**: verás la **barra de progreso de conversión (`0% - 100%`)** junto con el **Tiempo estimado restante** hasta finalizar. Todos los EPUB generados son universales para cualquier tamaño de Kindle.

---

## 3. Función 2: Cargar Libros al Kindle por Cable USB
1. Conecta tu Kindle a la PC mediante **cable USB** y elige en el menú desplegable **🔌 2. Cargar Libros al Kindle (USB)**.
2. En **1. Seleccionar Libros a Cargar**, puedes pulsar:
   - **✨ Usar EPUBs recién convertidos** (toma automáticamente la carpeta donde convertiste tus libros), o
   - **📁 Carpeta** / **📄 Libros** para elegir cualquier carpeta o archivos `.epub`, `.azw`, `.mobi`, `.kfx`.
3. Pulsa **📥 Cargar**: verás la barra de progreso (`0% - 100%`) y los libros aparecerán en la tabla listos para enviarse.
4. En **2. Destino en Kindle (Cable USB)**:
   - Pulsa **🔍 Auto-detectar Kindle USB** (detecta automáticamente la unidad del Kindle y su carpeta `documents`), o **📂 Elegir `documents`** para seleccionarla manualmente.
   - Mantén la opción recomendada **📦 Kindle USB Directo (.AZW + carpeta .sdr)** para que el Kindle reconozca el libro inmediatamente por cable USB creando tanto el archivo `<Libro>_<ASIN>.azw` como su carpeta `<Libro>_<ASIN>.sdr`.
5. Pulsa **📲 Enviar al Kindle por USB**: verás la barra de progreso (`0% - 100%`) y el **Tiempo estimado** hasta que todos tus libros estén dentro del Kindle.
