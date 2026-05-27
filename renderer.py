"""
Genera imágenes PIL de 128x128 para el Times Gate.
Layout:
  y  0-31: claw animation (4 frames, pulso naranja)
  y 32-59: SESSION bar
  y 60-87: WEEK bar
  y 88-115: DESIGN bar
  y 116-127: (negro)
"""

from PIL import Image, ImageDraw, ImageFont
import math

W, H = 128, 128

# Paleta
BG         = (5, 5, 12)
OR_HI      = (255, 140,   0)   # naranja brillante
OR_MID     = (200, 100,   0)
OR_LO      = (80,  40,   0)
OR_DIM     = (30,  15,   0)
WHITE      = (220, 220, 220)
GRAY_LABEL = (120, 120, 120)
GRAY_BAR   = (28,  28,  35)
GREEN      = (30,  190,  80)
YELLOW     = (220, 180,   0)
RED        = (200,  50,  50)


def bar_color(pct: float) -> tuple:
    if pct < 0.6:
        return GREEN
    elif pct < 0.85:
        return YELLOW
    return RED


# ── Claw pixel art (40×28, coordenadas (col, row) con valor 1=outline 2=glow) ──
# Diseño: la "C" angular del logo de Claude, en un diamante externo
def _claw_pixels() -> list[tuple[int, int, int]]:
    """
    Retorna lista de (x, y, tipo) donde tipo=1=outline naranja, 2=glow interior.

    Diseño: "C" angular estilo Claude logo — dos C anidadas, abriendo a la derecha.
    Grid de 44×28 centrado en la franja de 128×30.
    """
    # Definición manual del símbolo en un grid de strings (1=outline, 2=glow, .=vacio)
    # 44 chars de ancho, 28 rows
    grid = [
        #0         1         2         3         4
        #0123456789012345678901234567890123456789012 3
        "...11111111111111111111111111111111111111...",  # 0
        "..1..........................................1.",  # 1  <- solo bordes izq/der
        ".1..........................................1..",
        "1..22222222222222222222222222222222222222.....",  # 3
        "1..2..............................................",  # <- outer C abre acá
        "1..2..............................................",
        "1..2..............................................",
        "1..2...33333333333333333333333333333333......",  # 7
        "1..2...3.......................................",  # 8
        "1..2...3.......................................",
        "1..2...3.......................................",  # 10  <- inner C (opening right)
        "1..2...3.......................................",
        "1..2...3.......................................",
        "1..2...3.......................................",  # 13
        "1..2...33333333333333333333333333333333......",  # 14
        "1..2..............................................",
        "1..2..............................................",
        "1..2..............................................",
        "1..22222222222222222222222222222222222222.....",  # 18
        ".1..........................................1..",
        "..1..........................................1.",
        "...11111111111111111111111111111111111111...",  # 21
    ]

    # Grid más limpio — rediseño con coordenadas explícitas en 44×22
    CW, CH = 44, 22
    template = [[0] * CW for _ in range(CH)]

    # Outer frame (tipo 1): rectángulo con abertura derecha
    # Top y Bottom
    for x in range(2, CW - 2):
        template[0][x] = 1
        template[CH - 1][x] = 1
    # Left wall
    for y in range(0, CH):
        template[y][0] = 1
        template[y][1] = 1

    # Outer C — no cierra por la derecha (deja abierto x > CW//2+4)
    OPEN_FROM = CW // 2 + 5
    for y in [0, 1, CH - 2, CH - 1]:
        for x in range(OPEN_FROM, CW):
            template[y][x] = 0  # borrar esquinas de la apertura

    # Inner frame (tipo 2): C más pequeña, margen 5px, también abierta a la derecha
    MX, MY = 5, 4
    # Top y Bottom del inner
    for x in range(MX, OPEN_FROM - 2):
        template[MY][x] = 2
        template[CH - MY - 1][x] = 2
    # Left wall del inner
    for y in range(MY, CH - MY):
        template[y][MX] = 2
        template[y][MX + 1] = 2

    # Glow: un pixel dentro del inner frame (tipo 3 → color suave)
    MX2, MY2 = MX + 3, MY + 2
    OPEN2 = OPEN_FROM - 4
    for x in range(MX2, OPEN2):
        template[MY2][x] = 3
        template[CH - MY2 - 1][x] = 3
    for y in range(MY2, CH - MY2):
        template[y][MX2] = 3

    OFFSET_X = (128 - CW) // 2
    OFFSET_Y = 4

    result = []
    for gy, row in enumerate(template):
        for gx, val in enumerate(row):
            if val:
                result.append((OFFSET_X + gx, OFFSET_Y + gy, val))
    return result


_CLAW = _claw_pixels()

# 4 frames: exterior pulsa, interior glow va en contrafase
# tipo 1=outer, 2=inner C, 3=inner glow suave
_CLAW_PALETTES = [
    {1: OR_HI,  2: OR_LO,  3: OR_DIM},  # frame 0: exterior brillante
    {1: OR_MID, 2: OR_MID, 3: OR_LO},   # frame 1: medio
    {1: OR_LO,  2: OR_HI,  3: OR_MID},  # frame 2: interior brilla
    {1: OR_MID, 2: OR_MID, 3: OR_LO},   # frame 3: medio
]


def _render_section(draw: ImageDraw.Draw, y_top: int, label: str, pct: float):
    """
    Dibuja una sección en y_top..y_top+27 (28px total):
      Row +0:  label (izquierda) + porcentaje (derecha)  — 10px
      Row +12: barra de progreso                          — 8px
    Así no hay overlap con la sección siguiente.
    """
    font = ImageFont.load_default()

    PAD_L  = 4
    PAD_R  = 4
    BAR_H  = 8

    pct_str = f"{int(pct * 100):3d}%" if pct >= 0 else "  ?%"
    color   = bar_color(pct) if pct >= 0 else GRAY_LABEL

    # Label izquierda
    draw.text((PAD_L, y_top), label.strip(), fill=GRAY_LABEL, font=font)

    # Porcentaje derecha (alineado a 128-pad)
    pct_bbox = font.getbbox(pct_str)
    pct_w    = pct_bbox[2] - pct_bbox[0]
    draw.text((128 - PAD_R - pct_w, y_top), pct_str, fill=color, font=font)

    # Barra
    bar_y = y_top + 12
    BAR_W = 128 - PAD_L - PAD_R
    draw.rectangle([PAD_L, bar_y, PAD_L + BAR_W - 1, bar_y + BAR_H - 1],
                   fill=GRAY_BAR)
    if pct >= 0:
        fill_w = max(2, int(BAR_W * min(1.0, pct)))
        draw.rectangle([PAD_L, bar_y, PAD_L + fill_w - 1, bar_y + BAR_H - 1],
                       fill=bar_color(pct))


def render_frames(session: float, week: float, design: float) -> list[Image.Image]:
    """
    Genera 4 frames de animación (128×128).
    Parámetros:
      session, week, design: 0.0-1.0 (uso). -1.0 si desconocido.
    """
    frames: list[Image.Image] = []

    for frame_idx, palette in enumerate(_CLAW_PALETTES):
        img = Image.new("RGB", (W, H), BG)
        draw = ImageDraw.Draw(img)

        # --- Claw animado ---
        for cx, cy, ctype in _CLAW:
            img.putpixel((cx, cy), palette[ctype])

        # --- Secciones de uso (cada una ocupa 28px) ---
        #   y=30: SESSION  (label+%=row 30, bar=row 42)
        #   y=58: WEEK     (label+%=row 58, bar=row 70)
        #   y=86: DESIGN   (label+%=row 86, bar=row 98)
        _render_section(draw, 30, "SESSION", session)
        _render_section(draw, 58, "WEEK",    week)
        _render_section(draw, 86, "DESIGN",  design)

        frames.append(img)

    return frames
