"""Generate the Reflowia PDF to EPUB app icon (DMDev Labs)."""
from PIL import Image, ImageDraw
import os


def draw_rounded_rect(draw, xy, radius, fill):
    x0, y0, x1, y1 = xy
    r = radius
    draw.rectangle([x0 + r, y0, x1 - r, y1], fill=fill)
    draw.rectangle([x0, y0 + r, x1, y1 - r], fill=fill)
    draw.pieslice([x0, y0, x0 + 2 * r, y0 + 2 * r], 180, 270, fill=fill)
    draw.pieslice([x1 - 2 * r, y0, x1, y0 + 2 * r], 270, 360, fill=fill)
    draw.pieslice([x0, y1 - 2 * r, x0 + 2 * r, y1], 90, 180, fill=fill)
    draw.pieslice([x1 - 2 * r, y1 - 2 * r, x1, y1], 0, 90, fill=fill)


def generate_icon(size: int):
    s = size
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    margin = s * 0.06
    corner = s * 0.22
    bg_color = (0, 150, 120)
    bg_highlight = (0, 170, 135)

    draw_rounded_rect(draw, (margin, margin, s - margin, s - margin), corner, bg_color)
    inner_m = s * 0.08
    draw_rounded_rect(draw, (inner_m, inner_m, s * 0.65, s * 0.55), corner * 0.85, bg_highlight)

    # Dispositivo Kindle / Libro blanco central
    kx0, ky0 = s * 0.24, s * 0.18
    kx1, ky1 = s * 0.76, s * 0.82
    draw_rounded_rect(draw, (kx0, ky0, kx1, ky1), s * 0.07, (255, 255, 255))

    # Pantalla E-Ink interior
    sx0, sy0 = s * 0.29, s * 0.24
    sx1, sy1 = s * 0.71, s * 0.71
    draw_rounded_rect(draw, (sx0, sy0, sx1, sy1), s * 0.03, (224, 247, 239))

    # Renglones de texto fluido dentro del Kindle
    lw = max(1, int(s * 0.024))
    line_col = (0, 130, 100)
    for idx, y_pct in enumerate((0.33, 0.43, 0.53, 0.62)):
        y = s * y_pct
        x_end = sx1 - (s * 0.06 if idx < 3 else s * 0.16)
        draw.line([sx0 + s * 0.06, y, x_end, y], fill=line_col, width=lw)

    # Insignia circular inferior derecha (flecha conversión EPUB)
    badge_r = s * 0.15
    bcx, bcy = s * 0.73, s * 0.75
    draw.ellipse([bcx - badge_r, bcy - badge_r, bcx + badge_r, bcy + badge_r], fill=(17, 27, 33))
    draw.ellipse(
        [bcx - badge_r * 0.82, bcy - badge_r * 0.82, bcx + badge_r * 0.82, bcy + badge_r * 0.82],
        fill=(0, 168, 132),
    )

    # Símbolo de rayo / conversión en blanco
    pts = [
        (bcx + badge_r * 0.08, bcy - badge_r * 0.52),
        (bcx - badge_r * 0.35, bcy + badge_r * 0.06),
        (bcx + badge_r * 0.02, bcy + badge_r * 0.06),
        (bcx - badge_r * 0.10, bcy + badge_r * 0.52),
        (bcx + badge_r * 0.36, bcy - badge_r * 0.06),
        (bcx - badge_r * 0.02, bcy - badge_r * 0.06),
    ]
    draw.polygon(pts, fill=(255, 255, 255))
    return img


if __name__ == "__main__":
    sizes = [16, 24, 32, 48, 64, 128, 256]
    images = [generate_icon(s) for s in sizes]

    base_dir = os.path.dirname(os.path.abspath(__file__))
    ico_path = os.path.join(base_dir, "app.ico")
    images[-1].save(ico_path, format="ICO", sizes=[(s, s) for s in sizes], append_images=images[:-1])

    png_path = os.path.join(base_dir, "app_icon_256.png")
    images[-1].save(png_path, format="PNG")

    print(f"app.ico generado ({len(sizes)} tamaños: {sizes})")
    print("app_icon_256.png generado (preview)")

