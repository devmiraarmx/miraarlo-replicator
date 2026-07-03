"""Sello de Medidas — estampa medidas (diámetro/altura/base) sobre una imagen.

Genera una nueva imagen tipo ficha técnica:
  - DIÁMETRO: flecha horizontal doble ARRIBA de la imagen, label+valor encima.
  - ALTURA:   flecha vertical doble a la IZQUIERDA, label+valor a la izquierda.
  - BASE:     flecha horizontal doble ABAJO, label+valor debajo.

El canvas se EXPANDE respecto a la imagen original (nunca la recorta) para dejar
espacio a las flechas y el texto. Fondo blanco por defecto.
"""

import logging
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

log = logging.getLogger(__name__)

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

    # Normaliza valores (mayúsculas, sin espacios sobrantes).
    vals = {}
    for key, _label in _FIELDS:
        raw = (measurements or {}).get(key, "")
        vals[key] = str(raw).strip().upper() if raw else ""

    def _compute_metrics(ref_w):
        """Calcula fuentes, flechas y márgenes escalados a un ancho de referencia.

        El tamaño de fuente y el grosor de las flechas escalan con el ANCHO DEL
        CANVAS final (no con la imagen original). Como el canvas depende de los
        márgenes y estos del tamaño de texto, se itera: primero con el ancho de la
        imagen y luego con el ancho de canvas resultante.
        """
        value_fs = max(26, int(ref_w * 0.030))
        label_fs = max(22, int(ref_w * 0.024))
        value_font = _load_font(value_fs)
        label_font = _load_font(label_fs)

        gap = max(8, int(ref_w * 0.012))
        small_gap = max(4, gap // 2)
        head_w = max(14, int(ref_w * 0.018))
        head_len = max(18, int(ref_w * 0.024))
        line_w = max(3, int(ref_w * 0.005))

        _, label_h = _text_size(label_font, "AÁ")
        _, value_h = _text_size(value_font, "0CM")
        text_block_h = label_h + small_gap + value_h
        min_pad = gap * 2

        # Espacio reservado por lado según la medida presente.
        reserve_v = gap + head_w + gap + text_block_h + gap
        reserve_top = reserve_v if vals["diametro"] else min_pad
        reserve_bottom = reserve_v if vals["base"] else min_pad
        if vals["altura"]:
            lbl_w, _ = _text_size(label_font, "ALTURA")
            val_w, _ = _text_size(value_font, vals["altura"])
            reserve_left = gap + max(lbl_w, val_w) + gap + head_w + gap
        else:
            reserve_left = min_pad
        reserve_right = min_pad + head_w // 2

        # Márgenes simétricos: la imagen queda centrada horizontal y verticalmente,
        # y cada lado conserva el espacio necesario para su flecha/texto.
        margin_h = max(reserve_left, reserve_right)
        margin_v = max(reserve_top, reserve_bottom)
        canvas_w = w + 2 * margin_h
        canvas_h = h + 2 * margin_v

        return {
            "value_font": value_font, "label_font": label_font,
            "value_fs": value_fs, "label_fs": label_fs,
            "gap": gap, "small_gap": small_gap,
            "head_w": head_w, "head_len": head_len, "line_w": line_w,
            "label_h": label_h, "value_h": value_h, "text_block_h": text_block_h,
            "margin_h": margin_h, "margin_v": margin_v,
            "canvas_w": canvas_w, "canvas_h": canvas_h,
        }

    # Dos pasadas: estima con el ancho de la imagen, refina con el ancho de canvas.
    m = _compute_metrics(w)
    m = _compute_metrics(m["canvas_w"])

    value_font, label_font = m["value_font"], m["label_font"]
    gap, small_gap = m["gap"], m["small_gap"]
    head_w, head_len, line_w = m["head_w"], m["head_len"], m["line_w"]
    label_h, value_h, text_block_h = m["label_h"], m["value_h"], m["text_block_h"]
    margin_left = margin_right = m["margin_h"]
    margin_top = margin_bottom = m["margin_v"]
    canvas_w, canvas_h = m["canvas_w"], m["canvas_h"]

    # ── Canvas expandido; imagen CENTRADA en el área disponible ──
    canvas = Image.new("RGB", (canvas_w, canvas_h), bg_color)
    avail_w = canvas_w - margin_left - margin_right
    avail_h = canvas_h - margin_top - margin_bottom
    paste_x = margin_left + (avail_w - w) // 2
    paste_y = margin_top + (avail_h - h) // 2
    canvas.paste(src, (paste_x, paste_y))
    draw = ImageDraw.Draw(canvas)

    log.info(
        "Sello de medidas: original=%dx%d -> canvas=%dx%d, paste=(%d,%d), "
        "fuente label=%dpx valor=%dpx, linea=%dpx",
        w, h, canvas_w, canvas_h, paste_x, paste_y, m["label_fs"], m["value_fs"], line_w,
    )

    # Coordenadas de la caja de la imagen dentro del canvas.
    ix0, iy0 = paste_x, paste_y
    ix1, iy1 = paste_x + w, paste_y + h
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
