# Reflowia PDF to EPUB (v1.2.0)

Conversor universal de documentos **PDF a EPUB** con texto fluido (*reflowable*), compatible con todos los tamaños y formatos de Amazon Kindle y lectores electrónicos.

Desarrollado por **DMDevLabs** con arquitectura portable de un solo ejecutable (`Flask` + `pywebview` + `PyMuPDF`).

---

## Características Principales

- **Selección por Carpeta Completa o Archivos Individuales:** Permite elegir una carpeta completa (con soporte de subcarpetas) o uno/varios archivos PDF individuales.
- **Carga con Barra de Progreso:** Visualiza la ruta seleccionada antes de procesar y escanea los documentos mediante el botón **Cargar** con barra de progreso en vivo.
- **Conversión Universal a EPUB con Tiempo Estimado:** Reconstruye párrafos cortados, elimina guiones de división silábica al final de renglón, limpia encabezados/numeración de página, extrae la portada e ilustraciones internas y muestra barra de progreso con **tiempo estimado restante**.
- **Transferencia Directa a Kindle (USB y MTP):** Envío directo a lectores Kindle por unidad USB o protocolo MTP (incluyendo Kindle Paperwhite), con visor de registro (`reflowia.log`) y botones de Reintentar/Continuar.
- **Tema Claro por Defecto, Modo Oscuro y Bilingüe (ES/EN):** Interfaz limpia con avisos legales GPL-3.0 y marcas actualizados.
- **Compilación Limpia y Verificada:** Generación de un único ejecutable desde GitHub Actions (`windows-latest`) con suma de verificación `.sha256`.

---

## Ejecución en Desarrollo

```bat
run_app.bat
```

## Compilar Ejecutable Portable Único (`dist\Reflowia PDF to EPUB.exe`)

```bat
build.bat
```

---

## Estructura del Proyecto

- `app.py`: Punto de entrada principal (levanta el servidor local y la ventana nativa `pywebview`).
- `server.py`: API local Flask para selección nativa de carpetas/archivos, barra de carga y conversión con cálculo de tiempo estimado.
- `converter.py`: Motor de extracción `PyMuPDF`, limpieza heurística `TextReflowProcessor` y empaquetador universal `KindleEpubBuilder`.
- `templates/index.html`: Interfaz gráfica SPA ligera con soporte de temas Oscuro/Claro e idioma Español/Inglés.
- `ia/`: Documentación técnica de arquitectura y bitácora de sesiones de desarrollo.

