# 🧠 Carpeta `ia/` — Centro de Documentación y Sesiones Únicas

Bienvenido al repositorio documental inteligente de **Atelier Kindle (Conversor PDF a EPUB Multi-Tamaño)**.
Esta carpeta cumple dos propósitos fundamentales:
1. **Documentación integral del sistema:** Arquitectura, heurística de reconstrucción de texto, perfiles de tamaños de Amazon Kindle y manual de uso (Interfaz Gráfica y CLI).
2. **Trazabilidad por Sesión Única:** Cada vez que se inicia la aplicación o se ejecuta un lote de conversión, `IASessionManager` genera automáticamente un archivo único con formato `sesion_YYYYMMDD_HHMMSS_<ID>.md` dentro de esta misma carpeta `ia/`.

---

## 📚 Índice de Documentación

| Archivo | Descripción |
| :--- | :--- |
| [`00_INDICE_IA.md`](./00_INDICE_IA.md) | Índice maestro de la carpeta `ia/` y descripción del sistema de sesiones. |
| [`01_ARQUITECTURA_TECNICA.md`](./01_ARQUITECTURA_TECNICA.md) | Explicación detallada de las clases, flujo de datos, heurística de párrafos y empaquetador EPUB. |
| [`02_PERFILES_KINDLE.md`](./02_PERFILES_KINDLE.md) | Especificaciones técnicas de los perfiles de pantalla para Kindle de 6", 6.8", 7" y 10.2" (Scribe). |
| [`03_MANUAL_USUARIO.md`](./03_MANUAL_USUARIO.md) | Guía paso a paso para convertir archivos individuales, carpetas completas y usar la consola CLI. |

---

## 🗂️ Formato del Archivo Único por Sesión (`sesion_YYYYMMDD_HHMMSS_<ID>.md`)

Cada ejecución de [`app_pdf_to_epub.py`](../app_pdf_to_epub.py) crea en tiempo real su propio archivo de sesión sin sobrescribir sesiones anteriores. Cada archivo de sesión registra:
1. **Metadatos de la sesión:** ID único (timestamp + UUID corto), fecha/hora de inicio, duración acumulada, versión de Python y estado de PyMuPDF.
2. **Configuración activa:** Perfil de tamaño Kindle seleccionado, opciones de portada, extracción de imágenes, reflow heurístico y carpeta de destino.
3. **Resumen estadístico:** Cantidad de PDFs procesados, exitosos, avisos y comparativa de peso en MB (PDF de entrada vs EPUB resultante).
4. **Tabla detallada archivo por archivo:** Hora, nombre del PDF, modo de origen (`Individual` o `Carpeta`), perfil Kindle aplicado, páginas, capítulos generados, ilustraciones extraídas y estado final.
5. **Bitácora cronológica de eventos:** Registro con marca de tiempo de cada acción realizada durante la sesión.

