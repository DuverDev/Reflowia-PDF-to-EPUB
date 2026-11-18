# Cambios / Changelog

## 1.2.0 — 2026-11-14

### Interfaz, estabilidad y legal
- **Tema Claro activado por defecto** (conmutador rápido a Modo Oscuro en la barra superior).
- **Correcciones en la interfaz del asistente:** eliminados controles HTML y claves de traducción duplicadas, y reparadas las funciones JavaScript de conversión (`startConversion`) y transferencia USB (`usbStartTransfer`).
- **Avisos legales y de marcas actualizados:** licencia GNU GPL-3.0, cláusula «TAL CUAL» (*AS IS*) y no afiliación con Amazon.com, Inc. / Kindle.

### Compilación y distribución
- Eliminación de certificados autofirmados locales (`create_cert.ps1` / `Set-AuthenticodeSignature`).
- Dependencias en `requirements.txt` ajustadas para compatibilidad limpia con Python 3.12 en CI.
- Compilación automatizada en GitHub Actions (`windows-latest`) con archivo de verificación `.sha256`.

## 1.1.0 — 2026-10-27

- Soporte para dispositivos Kindle mediante protocolo MTP (Kindle Paperwhite).
- Extracción de texto e imágenes hasta 15x más rápida con PyMuPDF y COM en proceso.
- Visor integrado de registro (`reflowia.log`) y acciones de Reintentar fallidos / Continuar / Reprocesar todos.

## 1.0.0 — 2026-10-26

- Lanzamiento inicial de Reflowia PDF to EPUB.
