# 📱 Perfiles de Pantalla para Kindle de Varios Tamaños

Uno de los pilares de **Reflowia PDF to EPUB** es garantizar que el EPUB generado se lea con proporciones tipográficas e imágenes nítidas en **cualquier tamaño de Amazon Kindle**, desde el modelo compacto de 6 pulgadas hasta el Kindle Scribe de 10.2 pulgadas.

---

## Tabla Comparativa de Perfiles Incluidos

| Clave (`--profile`) | Dispositivo Objetivo | Tamaño Pantalla | Resolución Referencia | PPI | Escala Portada | Margen Lateral | Interlineado Base |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `universal` | **Universal Adaptativo (Todos los Kindle)** | 6.0" a 10.2" | 1236 × 1648 px | 300 | `1.60x` | `2.5%` | `1.52` |
| `kindle_6` | **Kindle Básico / Compacto** | 6.0" | 1072 × 1448 px | 300 | `1.35x` | `1.5%` | `1.45` |
| `paperwhite_7` | **Kindle Paperwhite (Gen 10/11/12)** | 6.8" - 7.0" | 1264 × 1680 px | 300 | `1.65x` | `2.8%` | `1.52` |
| `oasis_7` | **Kindle Oasis / Colorsoft** | 7.0" | 1264 × 1680 px | 300 | `1.75x` | `3.2%` | `1.55` |
| `scribe_10` | **Kindle Scribe Gran Formato** | 10.2" | 1860 × 2480 px | 300 | `2.20x` | `4.5%` | `1.60` |

---

## ¿Cómo funciona la adaptación multi-tamaño?

1. **Unidades Relativas (`em`, `%`, `vh`):**
   Ningún elemento de texto o margen usa píxeles fijos (`px`). De este modo, cuando el lector cambia el tamaño de letra en la barra de herramientas del Kindle (del nivel 1 al 14), los títulos, sangrías e interlineados escalan proporcionalmente.
2. **Consultas de Medios (`@media screen`):**
   Incluso al elegir un perfil base, la hoja de estilos `OEBPS/style.css` incorpora tres tramos adaptativos:
   - `max-width: 600px`: Reduce márgenes laterales a `1.2%` para ganar palabras por línea en pantallas de 6".
   - `601px a 1100px`: Optimiza la caja de texto para Paperwhite (6.8"/7") y Oasis (7").
   - `min-width: 1101px`: Amplía los márgenes a `5%` y el interlineado a `1.62` en Kindle Scribe (10.2") para evitar líneas demasiado largas que cansan la vista.
3. **Imágenes y Portadas Inteligentes:**
   Las imágenes y la portada usan `max-width: 100%; max-height: 96vh; object-fit: contain;` junto con `page-break-inside: avoid;`, evitando que una figura se parta en dos páginas o desborde la pantalla del Kindle.

