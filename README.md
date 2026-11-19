# Reflowia PDF to EPUB (v1.2.3)

Conversor universal de documentos **PDF a EPUB** con texto fluido (*reflowable*), para lectores Kindle y otros lectores electrónicos.

Desarrollado por **DMDev Labs** — [dmdevlabs.com](https://dmdevlabs.com). Gratis, de código abierto y 100% local, con arquitectura portable de un solo ejecutable (`Flask` + `pywebview` + `PyMuPDF`).

---

## Características Principales

- **Selección por Carpeta Completa o Archivos Individuales:** Permite elegir una carpeta completa (con soporte de subcarpetas) o uno/varios archivos PDF individuales.
- **Carga con Barra de Progreso:** Visualiza la ruta seleccionada antes de procesar y escanea los documentos mediante el botón **Cargar** con barra de progreso en vivo.
- **Conversión Universal a EPUB con Tiempo Estimado:** Reconstruye párrafos cortados, elimina guiones de división silábica al final de renglón, limpia encabezados/numeración de página, extrae la portada e ilustraciones internas y muestra barra de progreso con **tiempo estimado restante**.
- **Transferencia Directa a Kindle (USB y MTP):** Envío directo a lectores Kindle por unidad USB o protocolo MTP (incluyendo Kindle Paperwhite), con visor de registro (`reflowia.log`) y botones de Reintentar/Continuar.
- **Tema Claro por Defecto, Modo Oscuro y Bilingüe (ES/EN):** Interfaz limpia con avisos legales GPL-3.0 y marcas actualizados.
- **Compilación Limpia y Verificada:** Generación de un único ejecutable desde GitHub Actions (`windows-latest`) con suma de verificación `.sha256`.

---

## Estructura del Proyecto

- `app.py`: Punto de entrada principal (levanta el servidor local y la ventana nativa `pywebview`).
- `server.py`: API local Flask para selección nativa de carpetas/archivos, barra de carga y conversión con cálculo de tiempo estimado.
- `converter.py`: Motor de extracción `PyMuPDF`, limpieza heurística `TextReflowProcessor` y empaquetador universal `KindleEpubBuilder`.
- `templates/index.html`: Interfaz gráfica SPA ligera con soporte de temas Oscuro/Claro e idioma Español/Inglés.
- `ia/`: Documentación técnica de arquitectura y bitácora de desarrollo.

## Descargas y verificación

1. Descarga `Reflowia PDF to EPUB.exe` desde [Releases](../../releases/latest).
2. Cada release trae el SHA-256 del ejecutable (también en el archivo `.sha256`) y un enlace a VirusTotal.
3. El ejecutable no tiene certificado de firma comercial: Windows SmartScreen puede mostrar «Windows protegió su PC». Comprueba el SHA-256 y, si coincide, elige **Más información → Ejecutar de todas formas**.

La página del proyecto en [dmdevlabs.com/proyectos/reflowia](https://dmdevlabs.com/proyectos/reflowia) muestra las mismas descargas.

## Compilar desde el código fuente

```bat
pip install -r requirements.txt
run_app.bat      &:: ejecutar en desarrollo
build.bat        &:: genera dist\Reflowia PDF to EPUB.exe y su .sha256
```

Los releases oficiales los compila GitHub Actions (`windows-latest`) con el workflow **Release**.

## Privacidad y seguridad

- Todo se procesa en tu equipo: no sube documentos, no usa cuentas ni envía telemetría.
- No incluye libros ni elimina, rompe o elude protecciones DRM: solo convierte PDF sin protección sobre los que tengas derechos.
- La interfaz corre en un servidor local en `127.0.0.1` que solo atiende a la propia ventana de la app: rechaza peticiones de otros sitios web y de otros dominios.

## Licencia y condiciones de uso

- Código bajo **GNU GPL-3.0** ([LICENSE](LICENSE)).
- Se entrega «tal cual» (*as is*), sin garantías. Al usarlo aceptas las [condiciones de uso](TERMINOS.md), las mismas de [dmdevlabs.com/terminos](https://dmdevlabs.com/terminos).
- Amazon y Kindle son marcas de Amazon.com, Inc. o sus afiliadas. Reflowia es un proyecto independiente de DMDev Labs, sin afiliación, patrocinio ni respaldo de Amazon.
- Contacto: [contacto@dmdevlabs.com](mailto:contacto@dmdevlabs.com).

---

© 2026 DMDev Labs · [dmdevlabs.com](https://dmdevlabs.com)
