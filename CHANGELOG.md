# Cambios / Changelog

## 1.2.1 — 2026-11-18

### Seguridad
- **Servidor local blindado:** la API en `127.0.0.1` solo atiende a la propia ventana de la app. Rechaza peticiones de otros sitios web (CSRF) y de otros dominios (DNS rebinding), que antes podían iniciar conversiones o transferencias al Kindle.

### Legal y marca
- Condiciones de uso iguales a las de [dmdevlabs.com/terminos](https://dmdevlabs.com/terminos), en español e inglés (cambian con el idioma de la app) y en `TERMINOS.md`.
- Licencia GPL-3.0 completa en `LICENSE`; marca unificada como **DMDev Labs**.
- Quitados restos de nombres anteriores y reportes de sesión generados por la app (`reflowia.log` y reportes automáticos quedan fuera de git).

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
