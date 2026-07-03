"""Sello de Medidas — estampa medidas (diámetro/altura/base) sobre una imagen.

Genera una nueva imagen tipo ficha técnica:
  - DIÁMETRO: flecha horizontal doble ARRIBA de la imagen, label+valor encima.
  - ALTURA:   flecha vertical doble a la IZQUIERDA, label+valor a la izquierda.
  - BASE:     flecha horizontal doble ABAJO, label+valor debajo.

El canvas se EXPANDE respecto a la imagen original (nunca la recorta) para dejar
espacio a las flechas y el texto. Fondo blanco por defecto.
"""

from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

# ── Estilo ────────────────────────────────────────────────────────────────
TEXT_COLOR = (232, 147, 90)   # #E8935A naranja/coral
ARROW_COLOR = (0, 0, 0)       # negro
BG_WHITE = (255, 255, 255)

# Rutas candidatas para una fuente bold (primera que exista).
_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "DejaVuSans-Bold.ttf",
]

# Orden y labels fijos de los campos.
_FIELDS = [
    ("diametro", "DIÁMETRO"),
    ("altura", "ALTURA"),
    ("base", "BASE"),
]


def _load_font(size):
    """Carga una fuente bold del tamaño pedido, con fallback a la default de PIL."""
    for path in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def _text_size(font, text):
    """Ancho y alto de un texto con la fuente dada."""
    left, top, right, bottom = font.getbbox(text)
    return right - left, bottom - top


def _draw_double_arrow(draw, p1, p2, color, line_w, head_len, head_w, horizontal):
    """Dibuja una flecha de doble punta triangular entre p1 y p2."""
    draw.line([p1, p2], fill=color, width=line_w)
    hw = head_w / 2.0
    if horizontal:
        (x1, y), (x2, _) = p1, p2
        # Punta izquierda (apunta hacia afuera, a la izquierda)
        draw.polygon([(x1, y), (x1 + head_len, y - hw), (x1 + head_len, y + hw)], fill=color)
        # Punta derecha
        draw.polygon([(x2, y), (x2 - head_len, y - hw), (x2 - head_len, y + hw)], fill=color)
    else:
        (x, y1), (_, y2) = p1, p2
        # Punta superior
        draw.polygon([(x, y1), (x - hw, y1 + head_len), (x + hw, y1 + head_len)], fill=color)
        # Punta inferior
        draw.polygon([(x, y2), (x - hw, y2 - head_len), (x + hw, y2 - head_len)], fill=color)


def generate_measurement_stamp(image, measurements, bg_color=BG_WHITE):
    """Genera la imagen con las medidas estampadas.

    Args:
        image: ruta, file-like o PIL.Image de la imagen de producto.
        measurements: dict {'diametro': '10 CM', 'altura': '20 CM', 'base': '8 CM'}.
            Los campos vacíos o ausentes se omiten (sin flecha ni margen extra).
        bg_color: color de fondo del canvas expandido (por defecto blanco).

    Returns:
        PIL.Image en modo RGB con el sello aplicado.
    """
    src = image if isinstance(image, Image.Image) else Image.open(image)
    # Aplanar sobre fondo del color elegido (respeta transparencia de la fuente).
    if src.mode in ("RGBA", "LA", "P"):
        src = src.convert("RGBA")
        flat = Image.new("RGB", src.size, bg_color)
        flat.paste(src, mask=src.split()[-1])
        src = flat
    else:
        src = src.convert("RGB")

    w, h = src.size

    # Métricas proporcionales al tamaño de la imagen.
    base_fs = max(28, int(min(w, h) * 0.06))
    label_fs = max(20, int(base_fs * 0.78))
    value_font = _load_font(base_fs)
    label_font = _load_font(label_fs)

    gap = max(8, base_fs // 4)
    small_gap = max(4, base_fs // 8)
    head_len = base_fs
    head_w = max(14, int(base_fs * 0.7))
    line_w = max(3, base_fs // 9)

    # Normaliza valores (mayúsculas, sin espacios sobrantes).
    vals = {}
    for key, _label in _FIELDS:
        raw = (measurements or {}).get(key, "")
        vals[key] = str(raw).strip().upper() if raw else ""

    # Alto del bloque de texto (label + valor), igual para todos.
    _, label_h = _text_size(label_font, "AÁ")
    _, value_h = _text_size(value_font, "0CM")
    text_block_h = label_h + small_gap + value_h

    min_pad = gap * 2

    # ── Márgenes por lado (solo si el campo correspondiente tiene valor) ──
    margin_top = (gap + head_w + gap + text_block_h + gap) if vals["diametro"] else min_pad
    margin_bottom = (gap + head_w + gap + text_block_h + gap) if vals["base"] else min_pad

    if vals["altura"]:
        lbl_w, _ = _text_size(label_font, "ALTURA")
        val_w, _ = _text_size(value_font, vals["altura"])
        alt_text_w = max(lbl_w, val_w)
        margin_left = gap + alt_text_w + gap + head_w + gap
    else:
        margin_left = min_pad
    margin_right = min_pad + head_w // 2

    # ── Canvas expandido ──
    canvas_w = w + margin_left + margin_right
    canvas_h = h + margin_top + margin_bottom
    canvas = Image.new("RGB", (canvas_w, canvas_h), bg_color)
    canvas.paste(src, (margin_left, margin_top))
    draw = ImageDraw.Draw(canvas)

    # Coordenadas de la caja de la imagen dentro del canvas.
    ix0, iy0 = margin_left, margin_top
    ix1, iy1 = margin_left + w, margin_top + h
    cx = (ix0 + ix1) / 2.0
    cy = (iy0 + iy1) / 2.0

    # ── DIÁMETRO (arriba) ──
    if vals["diametro"]:
        shaft_y = iy0 - gap - head_w / 2.0
        _draw_double_arrow(draw, (ix0, shaft_y), (ix1, shaft_y),
                           ARROW_COLOR, line_w, head_len, head_w, horizontal=True)
        value_cy = shaft_y - head_w / 2.0 - gap - value_h / 2.0
        label_cy = value_cy - value_h / 2.0 - small_gap - label_h / 2.0
        draw.text((cx, label_cy), "DIÁMETRO", font=label_font, fill=TEXT_COLOR, anchor="mm")
        draw.text((cx, value_cy), vals["diametro"], font=value_font, fill=TEXT_COLOR, anchor="mm")

    # ── BASE (abajo) ──
    if vals["base"]:
        shaft_y = iy1 + gap + head_w / 2.0
        _draw_double_arrow(draw, (ix0, shaft_y), (ix1, shaft_y),
                           ARROW_COLOR, line_w, head_len, head_w, horizontal=True)
        value_cy = shaft_y + head_w / 2.0 + gap + value_h / 2.0
        label_cy = value_cy + value_h / 2.0 + small_gap + label_h / 2.0
        draw.text((cx, label_cy), "BASE", font=label_font, fill=TEXT_COLOR, anchor="mm")
        draw.text((cx, value_cy), vals["base"], font=value_font, fill=TEXT_COLOR, anchor="mm")

    # ── ALTURA (izquierda) ──
    if vals["altura"]:
        shaft_x = ix0 - gap - head_w / 2.0
        _draw_double_arrow(draw, (shaft_x, iy0), (shaft_x, iy1),
                           ARROW_COLOR, line_w, head_len, head_w, horizontal=False)
        text_right = shaft_x - head_w / 2.0 - gap
        label_cy = cy - (text_block_h / 2.0) + label_h / 2.0
        value_cy = cy + (text_block_h / 2.0) - value_h / 2.0
        draw.text((text_right, label_cy), "ALTURA", font=label_font, fill=TEXT_COLOR, anchor="rm")
        draw.text((text_right, value_cy), vals["altura"], font=value_font, fill=TEXT_COLOR, anchor="rm")

    return canvas


def generate_measurement_stamp_png(image, measurements, bg_color=BG_WHITE):
    """Igual que generate_measurement_stamp pero devuelve un BytesIO PNG listo para servir."""
    result = generate_measurement_stamp(image, measurements, bg_color=bg_color)
    buf = BytesIO()
    result.save(buf, format="PNG")
    buf.seek(0)
    return buf
