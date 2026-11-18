# Sesión de Desarrollo — 2026-10-27 23:14:00
## Diagnóstico y Corrección de Transferencia MTP a Kindle Paperwhite + Visor de Log + Reintentar Fallidos / Continuar

### 1. Diagnóstico de Causa Raíz (Por qué falló en el libro #425 y por qué no aparecían en la pantalla del Kindle)
Al inspeccionar directamente el dispositivo `Kindle Paperwhite` conectado por MTP (`mtp://Kindle Paperwhite/Internal Storage/documents/Downloads/Items01`), se descubrieron **3 causas técnicas exactas**:

1. **Condición de carrera asíncrona en `Shell.Application.CopyHere` + `shutil.rmtree(staging_dir)`:**
   - El método COM `Folder.CopyHere(book_abs, 20)` de Windows Explorer para dispositivos MTP **es asíncrono**: lanza un hilo en segundo plano de Windows Shell y retorna inmediatamente en `< 1 ms`.
   - El bloque `finally: shutil.rmtree(staging_dir, ignore_errors=True)` se ejecutaba **1 milisegundo después**, borrando el archivo `.azw`/`.mobi` temporal antes de que Windows MTP terminara de transmitirlo por el cable USB.
   - Como resultado: en `Items01` se crearon 423 carpetas `.sdr` vacías (`NewFolder` sí es síncrono), pero solo 1 archivo `.azw` alcanzó a copiarse. Además, al encolar 424 operaciones `CopyHere` asíncronas simultáneas, el servicio MTP del Kindle colapsó y se desconectó en el libro #425.
   - **Solución implementada:** En `KindleUsbPacker.copy_package_to_mtp`, después de invocar `CopyHere`, se realiza una espera activa ligera mediante `com_call(cur_folder, "ParseName", book_name)` (búsqueda `O(1)` por nombre sin enumerar la carpeta) hasta confirmar físicamente que el archivo ya existe dentro del almacenamiento del Kindle antes de eliminar `staging_dir`. Además, se añadió reintento automático (`3 intentos`) ante micro-cortes MTP.

2. **Ruta de destino para libros enviados por USB (`Internal Storage/documents` vs `documents/Downloads/Items01`):**
   - La subcarpeta `documents/Downloads/Items01` es exclusiva del demonio de descargas de Amazon Cloud (KFX/AZW con licencia DRM en `/var/local/cc.db`). El indexador local del Kindle ignora archivos sin DRM puestos manualmente en `Items01`.
   - **Solución implementada:** `detect_connected_kindle_folders()` ahora prioriza y selecciona por defecto **`mtp://Kindle Paperwhite/Internal Storage/documents` (`Recomendado`)**.

3. **Cabecera binaria MOBI6 (`build_mobi_azw_bytes`) idéntica a `kindlegen`:**
   - Se analizaron los bytes del encabezado del diccionario oficial del Kindle del usuario y se ajustó `build_mobi_azw_bytes` para incluir registros estándar `FLIS`, `FCIS`, `EOF`, offsets `0xFFFFFFFF` en `drm_offset`/`drm_count`, y metadatos `EXTH` completos (`113`/`504` ASIN, `501=EBOK`, `524=es`, `204=201`, `205=2`, `206=9`), estableciendo **`.mobi + carpeta .sdr`** como formato predeterminado.

### 2. Nuevas Funciones de Resiliencia y Diagnóstico
- **Registro Persistente (`reflowia.log`) y Visor de Log en Tiempo Real (`📋 Log`):**
  - Guarda cada evento (`INFO`, `WARN`, `ERROR`) con marca de tiempo en `reflowia.log` y en memoria.
  - Botón superior **`📋 Log`** con contador rojo de errores, filtro (`Todos` / `Solo Errores`), botón para abrir `reflowia.log` en el bloc de notas y botón para limpiar el registro.
- **Pausa Automática Inteligente y Botón `🔄 Reintentar Fallidos / Continuar`:**
  - Si el cable USB/MTP se desconecta durante un lote grande (tras 3 errores consecutivos de desconexión MTP), la cola **pausa automáticamente** dejando el resto de libros en estado `Pendiente` en lugar de marcar los cientos restantes como error.
  - Al reconectar el Kindle y pulsar **`🔄 Reintentar Fallidos (X) / Continuar (Y)`**, la aplicación salta todos los libros que ya tienen `status == "ok"` y procesa únicamente los fallidos y pendientes desde donde quedó.

