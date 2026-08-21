"""
Gera icone do aplicativo Nutri Assistent.
Cria um ICO com fundo verde-oliva, letra 'N' e folha decorativa.
"""
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import math


def create_icon(output_path: Path = None):
    """Cria icone multi-tamanho e salva como ICO."""
    if output_path is None:
        output_path = Path(__file__).parent / "extra" / "icon.ico"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    sizes = [16, 24, 32, 48, 64, 128, 256]
    images = []

    # Cores da palette
    BG = (118, 124, 87, 255)          # #767c57 verde-oliva
    BG_DARK = (90, 98, 65, 255)       # borda mais escura
    TEXT = (255, 255, 255, 255)        # branco
    ACCENT = (191, 200, 145, 255)     # #bfc891 verde claro
    LEAF = (150, 180, 100, 255)       # verde folha

    for size in sizes:
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        pad = max(1, size // 12)
        center = size // 2

        # --- Fundo: circulo com gradiente simulado ---
        draw.ellipse(
            [pad, pad, size - pad - 1, size - pad - 1],
            fill=BG,
            outline=BG_DARK,
            width=max(1, size // 24),
        )

        # --- Folha decorativa (canto superior direito) ---
        if size >= 32:
            leaf_scale = size / 256
            lx = int(size * 0.70)
            ly = int(size * 0.22)
            lr = max(2, int(18 * leaf_scale))

            # Folha principal
            leaf_bbox = [lx - lr, ly - lr, lx + lr, ly + int(lr * 0.5)]
            draw.ellipse(leaf_bbox, fill=LEAF)

            # Raste da folha
            stem_w = max(1, int(2 * leaf_scale))
            draw.line(
                [(lx, ly), (lx - int(8 * leaf_scale), ly + int(12 * leaf_scale))],
                fill=ACCENT, width=stem_w
            )

        # --- Letra 'N' centralizada ---
        font_size = int(size * 0.52)
        font = None
        for fname in ["arialbd.ttf", "arial.ttf", "segoeuib.ttf",
                       "segoeui.ttf", "consolab.ttf", "verdanab.ttf"]:
            try:
                font = ImageFont.truetype(fname, font_size)
                break
            except (OSError, IOError):
                continue
        if font is None:
            font = ImageFont.load_default()

        # Medir e centralizar
        bbox = draw.textbbox((0, 0), "N", font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        x = (size - tw) // 2
        y = (size - th) // 2 - bbox[1] + int(size * 0.02)

        # Sombra
        shadow = max(1, size // 64)
        draw.text((x + shadow, y + shadow), "N",
                  fill=(50, 55, 35, 160), font=font)
        # Texto principal
        draw.text((x, y), "N", fill=TEXT, font=font)

        # --- Ponto de destaque (berilo) ---
        if size >= 24:
            dr = max(2, int(size * 0.055))
            dx = int(size * 0.74)
            dy = int(size * 0.30)
            draw.ellipse(
                [dx - dr, dy - dr, dx + dr, dy + dr],
                fill=ACCENT,
            )

        images.append(img)

    # Salvar ICO
    images[-1].save(
        str(output_path),
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=images[:-1],
    )

    # Salvar PNG 256x256 para referencia
    png_path = output_path.with_suffix(".png")
    images[-1].save(str(png_path), format="PNG")

    print(f"ICO gerado: {output_path}")
    print(f"PNG gerado: {png_path}")
    return output_path


if __name__ == "__main__":
    create_icon()
