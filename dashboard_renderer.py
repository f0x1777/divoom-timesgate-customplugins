from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
import math
import os
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageSequence


W = 128
H = 128


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial.ttf",
    ]
    for path in candidates:
        if path and Path(path).exists():
            try:
                return ImageFont.truetype(path, size=size)
            except Exception:
                pass
    return ImageFont.load_default()


FONT_TITLE = _font(12, True)
FONT_BIG = _font(20, True)
FONT_MED = _font(14, True)
FONT_ROW = _font(10, True)
FONT_MARKET_PRICE = _font(11, True)
FONT_SMALL = _font(8)
FONT_TINY = _font(7)


def _pct(value: float | int | None) -> str:
    if not isinstance(value, (int, float)) or value < 0:
        return "?"
    return f"{max(0, min(100, round(value * 100)))}%"


def _available_from_used(value: float | int | None) -> float:
    if not isinstance(value, (int, float)) or value < 0:
        return -1.0
    return max(0.0, min(1.0, 1.0 - float(value)))


def _reset_label(value: Any) -> str:
    if not value:
        return "--"
    try:
        if isinstance(value, (int, float)):
            dt = datetime.fromtimestamp(float(value), tz=timezone.utc).astimezone()
        else:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone()
    except Exception:
        return "--"

    now = datetime.now().astimezone()
    if dt.date() == now.date():
        return dt.strftime("%H:%M")
    return dt.strftime("%a %H")


def _save_gif(frames: list[Image.Image], duration: int = 450) -> bytes:
    buf = BytesIO()
    frames[0].save(
        buf,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=duration,
        loop=0,
        optimize=False,
    )
    return buf.getvalue()


def _save_gif_with_durations(frames: list[Image.Image], durations: list[int]) -> bytes:
    buf = BytesIO()
    frames[0].save(
        buf,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=durations or 100,
        loop=0,
        optimize=False,
        disposal=1,
    )
    return buf.getvalue()


def _base(bg: str = "#050608") -> Image.Image:
    return Image.new("RGB", (W, H), bg)


def _draw_header(draw: ImageDraw.ImageDraw, title: str, color: str):
    draw.rounded_rectangle((2, 2, 125, 18), radius=3, fill="#11151A", outline=color)
    draw.text((6, 4), title, font=FONT_TITLE, fill="#FFFFFF")


def _draw_row(draw: ImageDraw.ImageDraw, y: int, label: str, pct: str, reset: str, color: str):
    draw.text((5, y), label, font=FONT_ROW, fill="#B7C0C7")
    draw.text((42, y), pct, font=FONT_ROW, fill=color)
    draw.text((82, y + 1), reset, font=FONT_SMALL, fill="#D9DEE3")


def _draw_openai_mark(draw: ImageDraw.ImageDraw, cx: int, cy: int, pulse: int = 0, scale: float = 1.0):
    radius = int((10 + pulse) * scale)
    dot = max(2, int(3 * scale))
    for i in range(6):
        angle = math.tau * i / 6
        x = cx + math.cos(angle) * radius
        y = cy + math.sin(angle) * radius
        draw.ellipse((x - dot, y - dot, x + dot, y + dot), fill="#FFFFFF")
    inner = max(4, int(5 * scale))
    draw.ellipse((cx - inner, cy - inner, cx + inner, cy + inner), outline="#FFFFFF", width=max(2, int(2 * scale)))


def _draw_clawmp(draw: ImageDraw.ImageDraw, x: int, y: int, bounce: int = 0):
    y -= bounce
    draw.arc((x, y, x + 14, y + 16), 210, 335, fill="#FF8A00", width=2)
    draw.arc((x + 8, y, x + 22, y + 16), 205, 330, fill="#FF8A00", width=2)
    draw.line((x + 11, y + 6, x + 11, y + 21), fill="#FF8A00", width=2)
    draw.text((x + 26, y + 7), "Clawmp", font=FONT_SMALL, fill="#FFFFFF")


def render_codex_panel(usage: dict, waiting: bool = False) -> bytes:
    primary_avail = _available_from_used(usage.get("primary"))
    secondary_avail = _available_from_used(usage.get("secondary"))

    frames: list[Image.Image] = []
    for pulse in ([0, 2] if waiting else [0]):
        img = _base("#06100D")
        draw = ImageDraw.Draw(img)
        draw.text((7 + pulse, 8), "5h", font=FONT_MED, fill="#A9B8B0")
        draw.text((49, 5), _pct(primary_avail), font=FONT_BIG, fill="#19C37D")
        draw.text((49, 31), _reset_label(usage.get("primary_reset")), font=FONT_MED, fill="#FFFFFF")
        draw.line((6, 61, 122, 61), fill="#17382A")
        draw.text((7, 70), "Wk", font=FONT_MED, fill="#A9B8B0")
        draw.text((49 + pulse, 67), _pct(secondary_avail), font=FONT_BIG, fill="#19C37D")
        draw.text((49, 93), _reset_label(usage.get("secondary_reset")), font=FONT_MED, fill="#FFFFFF")
        if waiting:
            draw.text((94, 112), "INPUT", font=FONT_TINY, fill="#FFD166")
        frames.append(img)
    return _save_gif(frames)


def render_claude_panel(usage: dict, waiting: bool = False) -> bytes:
    session_avail = _available_from_used(usage.get("session"))
    week_avail = _available_from_used(usage.get("week"))
    design_avail = _available_from_used(usage.get("design"))
    sonnet_avail = _available_from_used(usage.get("sonnet"))

    frames: list[Image.Image] = []
    for bounce in ([0, 3] if waiting else [0]):
        img = _base("#100B06")
        draw = ImageDraw.Draw(img)
        rows = [
            ("5h", session_avail, usage.get("session_reset")),
            ("Wk", week_avail, usage.get("week_reset")),
            ("Dsg", design_avail, usage.get("design_reset")),
            ("Son", sonnet_avail, usage.get("sonnet_reset")),
        ]
        for idx, (label, value, reset) in enumerate(rows):
            y = 4 + idx * 30
            draw.text((5, y + 4), label, font=FONT_ROW, fill="#D3B08A")
            draw.text((36, y), _pct(value), font=FONT_MED, fill="#FFB14A")
            draw.text((80, y + 3), _reset_label(reset), font=FONT_SMALL, fill="#FFFFFF")
            if idx < 3:
                draw.line((5, y + 27, 122, y + 27), fill="#3D230B")
        if waiting:
            draw.text((88 + bounce, 116), "INPUT", font=FONT_TINY, fill="#FFD166")
        frames.append(img)
    return _save_gif(frames)


def render_openai_logo_panel(waiting: bool = False) -> bytes:
    path_value = os.getenv("OPENAI_LOGO_GIF_PATH", "assets/openai-logo.gif")
    path = Path(path_value).expanduser()
    if not path.exists():
        return render_blank_panel()

    source = Image.open(path)
    marks: list[Image.Image] = []
    source_durations: list[int] = []
    for frame in ImageSequence.Iterator(source):
        mark = _foreground_mark(frame.convert("RGB"), threshold=55)
        if mark:
            mark.thumbnail((114, 114), Image.Resampling.LANCZOS)
            marks.append(mark)
            source_durations.append(int(frame.info.get("duration", 120) or 120))
    source.close()

    if not marks:
        return render_blank_panel()

    mode = os.getenv("OPENAI_LOGO_ANIMATION", "spin-on-wait").lower()
    if mode == "spin" or (mode == "spin-on-wait" and waiting):
        return _render_spinning_mark(marks[0], waiting=waiting)

    frames: list[Image.Image] = []
    durations: list[int] = []
    display_marks = marks if mode == "source" and waiting else [marks[0]]
    for idx, mark in enumerate(display_marks):
        canvas = Image.new("RGBA", (W, H), (0, 0, 0, 255))
        x = (W - mark.width) // 2
        y = (H - mark.height) // 2
        if waiting and idx % 2:
            y -= 2
        canvas.alpha_composite(mark, (x, y))
        frames.append(canvas.convert("RGB"))
        durations.append(source_durations[min(idx, len(source_durations) - 1)])

    if waiting and len(frames) == 1:
        frames.append(frames[0].resize((W, H)))
        durations.append(120)
    return _save_gif_with_durations(frames, durations)


def _foreground_mark(rgb: Image.Image, threshold: int) -> Image.Image | None:
    bg = rgb.getpixel((0, 0))
    mask = Image.new("L", rgb.size, 0)
    px = rgb.load()
    mp = mask.load()
    for y in range(rgb.height):
        for x in range(rgb.width):
            r, g, b = px[x, y]
            dist = abs(r - bg[0]) + abs(g - bg[1]) + abs(b - bg[2])
            if dist > threshold:
                mp[x, y] = 255
    bbox = mask.getbbox()
    if not bbox:
        return None
    mask = mask.crop(bbox)
    mark = Image.new("RGBA", mask.size, (255, 255, 255, 0))
    mark.putalpha(mask)
    return mark


def _render_spinning_mark(mark: Image.Image, waiting: bool = False) -> bytes:
    frames: list[Image.Image] = []
    durations: list[int] = []
    frame_count = int(os.getenv("OPENAI_LOGO_SPIN_FRAMES", "24"))
    duration = int(os.getenv("OPENAI_LOGO_SPIN_FRAME_MS", "70"))
    for idx in range(max(4, frame_count)):
        angle = -360 * idx / max(4, frame_count)
        rotated = mark.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True)
        rotated.thumbnail((116, 116), Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", (W, H), (0, 0, 0, 255))
        x = (W - rotated.width) // 2
        y = (H - rotated.height) // 2
        if waiting and idx % 6 in (1, 2):
            y -= 2
        canvas.alpha_composite(rotated, (x, y))
        frames.append(canvas.convert("RGB"))
        durations.append(duration)
    return _save_gif_with_durations(frames, durations)


def render_clawd_panel(waiting: bool = False) -> bytes:
    path_value = os.getenv("CLAWD_GIF_PATH", "assets/clawd.gif")
    path = Path(path_value).expanduser()
    if not path.exists():
        return render_blank_panel()

    source = Image.open(path)
    frames: list[Image.Image] = []
    durations: list[int] = []
    for idx, frame in enumerate(ImageSequence.Iterator(source)):
        rgba = frame.convert("RGBA")
        bg = rgba.getpixel((0, 0))[:3]
        mask = Image.new("L", rgba.size, 0)
        px = rgba.load()
        mp = mask.load()
        for y in range(rgba.height):
            for x in range(rgba.width):
                r, g, b, a = px[x, y]
                if a > 16 and abs(r - bg[0]) + abs(g - bg[1]) + abs(b - bg[2]) > 28:
                    mp[x, y] = 255
        bbox = mask.getbbox() or rgba.getchannel("A").getbbox()
        if bbox:
            rgba = rgba.crop(bbox)
            mask = mask.crop(bbox)
        clean = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
        src = rgba.load()
        mp = mask.load()
        dst = clean.load()
        for y in range(rgba.height):
            for x in range(rgba.width):
                if mp[x, y]:
                    r, g, b, a = src[x, y]
                    if r < 70 and g < 70 and b < 70:
                        dst[x, y] = (0, 0, 0, 255)
                    else:
                        dst[x, y] = (224, 111, 82, 255)
        rgba = clean
        rgba.thumbnail((122, 122), Image.Resampling.NEAREST)
        canvas = Image.new("RGBA", (W, H), (0, 0, 0, 255))
        x = (W - rgba.width) // 2
        y = (H - rgba.height) // 2
        if waiting:
            y -= 2
        canvas.alpha_composite(rgba, (x, y))
        frames.append(canvas.convert("RGB"))
        durations.append(int(frame.info.get("duration", 30) or 30))
        if not waiting:
            break

    if not frames:
        return render_blank_panel()
    return _save_gif_with_durations(frames, durations)


def render_blank_panel() -> bytes:
    return _save_gif([_base("#000000")])


def render_gengar_panel() -> bytes:
    path_value = os.getenv("GENGAR_GIF_PATH", "assets/center.gif")
    path = Path(path_value).expanduser()
    if not path.exists():
        return render_blank_panel()

    source = Image.open(path)
    frames: list[Image.Image] = []
    durations: list[int] = []
    for frame in ImageSequence.Iterator(source):
        rgba = frame.convert("RGBA")
        bbox = rgba.getchannel("A").getbbox()
        if bbox:
            rgba = rgba.crop(bbox)
        rgba.thumbnail((122, 122), Image.Resampling.NEAREST)
        canvas = Image.new("RGBA", (W, H), (0, 0, 0, 255))
        x = (W - rgba.width) // 2
        y = (H - rgba.height) // 2
        canvas.alpha_composite(rgba, (x, y))
        frames.append(canvas.convert("RGB"))
        durations.append(int(frame.info.get("duration", 100) or 100))

    if not frames:
        return render_blank_panel()
    return _save_gif_with_durations(frames, durations)


def render_ops_panel(
    quotes: list[dict[str, Any]],
    resources: dict[str, float],
    events: list[dict[str, Any]],
) -> bytes:
    img = _base("#080A0D")
    draw = ImageDraw.Draw(img)

    y = 4
    if quotes:
        for quote in quotes[:3]:
            label = str(quote.get("label", "?"))[:4]
            price = _short_price(quote.get("price"), quote)
            change = _signed_pct(quote.get("change_pct"))
            color = "#22C55E" if _num(quote.get("change_pct")) >= 0 else "#FB7185"
            draw.text((5, y), label, font=FONT_ROW, fill="#CBD5E1")
            draw.text((36, y - 1), price, font=FONT_MARKET_PRICE, fill="#FFFFFF")
            draw.text((86, y), change, font=FONT_SMALL, fill=color)
            y += 15
    else:
        draw.text((5, y), "MARKETS --", font=FONT_ROW, fill="#64748B")
        y += 16

    draw.line((5, 53, 122, 53), fill="#1E293B")
    _draw_metric_bar(draw, 5, 58, "CPU", resources.get("cpu"), "#38BDF8")
    _draw_metric_bar(draw, 5, 73, "MEM", resources.get("memory"), "#A78BFA")
    _draw_metric_bar(draw, 5, 88, "DSK", resources.get("disk"), "#FBBF24")
    _draw_network_metric(
        draw,
        5,
        106,
        resources.get("net_in_mbps"),
        resources.get("net_out_mbps"),
    )
    return _save_gif([img], duration=1000)


def render_health_panel(health: dict[str, Any]) -> bytes:
    img = _base("#070B10")
    draw = ImageDraw.Draw(img)

    checks = list(health.get("checks") or [])
    ok_count = sum(1 for item in checks if item.get("ok"))
    total = len(checks)
    color = "#34D399" if ok_count == total and total else "#FB7185"
    draw.text((5, 4), "SVC", font=FONT_MED, fill="#CBD5E1")
    draw.text((48, 2), f"{ok_count}/{total}", font=FONT_BIG, fill=color)
    draw.line((5, 28, 122, 28), fill="#1E293B")

    y = 34
    for item in checks[:5]:
        row_color = "#34D399" if item.get("ok") else "#FB7185"
        label = str(item.get("label", "?"))[:5]
        detail = str(item.get("detail", "--"))[:8]
        draw.ellipse((5, y + 2, 12, y + 9), fill=row_color)
        draw.text((17, y), label, font=FONT_ROW, fill="#FFFFFF")
        draw.text((61, y + 1), "OK" if item.get("ok") else "FAIL", font=FONT_SMALL, fill=row_color)
        draw.text((91, y + 1), detail, font=FONT_TINY, fill="#94A3B8")
        y += 15

    tailscale = health.get("tailscale") or {}
    draw.line((5, 111, 122, 111), fill="#1E293B")
    ts_ok = bool(tailscale.get("ok"))
    ts_color = "#34D399" if ts_ok else "#FB7185"
    state = str(tailscale.get("state", "--"))[:8].upper()
    peers = tailscale.get("peers", -1)
    peers_text = _compact_count(peers)
    draw.text((5, 116), "TS", font=FONT_ROW, fill="#94A3B8")
    draw.text((28, 116), "OK" if ts_ok else "OFF", font=FONT_ROW, fill=ts_color)
    draw.text((62, 117), state, font=FONT_SMALL, fill="#CBD5E1")
    draw.text((104, 117), peers_text, font=FONT_SMALL, fill="#CBD5E1")
    return _save_gif([img], duration=1000)


def _compact_count(value: Any) -> str:
    if not isinstance(value, int) or value < 0:
        return "--"
    if value >= 1000:
        return f"{value / 1000:.1f}K"
    return str(value)


def _draw_metric_bar(draw: ImageDraw.ImageDraw, x: int, y: int, label: str, value: Any, color: str):
    text = _pct_value(value)
    draw.text((x, y), label, font=FONT_ROW, fill="#94A3B8")

    pct_x = 123
    pct_bbox = draw.textbbox((0, 0), text, font=FONT_ROW)
    draw.text((pct_x - (pct_bbox[2] - pct_bbox[0]), y), text, font=FONT_ROW, fill=color)

    bar_x = x + 30
    bar_y = y + 3
    bar_w = 56
    bar_h = 7
    draw.rectangle((bar_x, bar_y, bar_x + bar_w, bar_y + bar_h), fill="#111827", outline="#334155")
    fill_w = _bar_fill_width(value, bar_w - 2)
    if fill_w > 0:
        draw.rectangle((bar_x + 1, bar_y + 1, bar_x + fill_w, bar_y + bar_h - 1), fill=color)


def _draw_network_metric(draw: ImageDraw.ImageDraw, x: int, y: int, inbound: Any, outbound: Any):
    draw.line((5, y - 5, 122, y - 5), fill="#1E293B")
    draw.text((x, y), "IN Mb/s", font=FONT_SMALL, fill="#94A3B8")
    draw.text((x + 65, y), "OUT Mb/s", font=FONT_SMALL, fill="#94A3B8")
    draw.text((x, y + 9), _mbps(inbound), font=FONT_MED, fill="#34D399")
    draw.text((x + 65, y + 9), _mbps(outbound), font=FONT_MED, fill="#FB7185")


def _bar_fill_width(value: Any, width: int) -> int:
    number = _num(value)
    if number < 0:
        return 0
    return max(0, min(width, round(width * number / 100)))


def _pct_value(value: Any) -> str:
    number = _num(value)
    return "--" if number < 0 else f"{round(number):02.0f}%"


def _mbps(value: Any) -> str:
    number = _num(value)
    if number < 0:
        return "--"
    if number >= 100:
        return f"{number:.0f}"
    if number >= 10:
        return f"{number:.1f}"
    return f"{number:.2f}"


def _event_label(event: dict[str, Any]) -> str:
    try:
        start = datetime.fromisoformat(str(event.get("start"))).astimezone()
        time_label = start.strftime("%H:%M")
    except Exception:
        time_label = "--:--"
    summary = str(event.get("summary", "Event"))
    return f"{time_label} {summary}"[:23]


def _short_price(value: Any, quote: dict[str, Any] | None = None) -> str:
    price = _num(value)
    if price < 0:
        return "--"
    if quote and quote.get("source") == "dolarapi":
        return f"{price:.0f}"
    if price >= 1000:
        return f"{price / 1000:.1f}K"
    if price >= 100:
        return f"{price:.0f}"
    if price >= 10:
        return f"{price:.1f}"
    return f"{price:.2f}"


def _signed_pct(value: Any) -> str:
    pct = _num(value)
    if pct < -99:
        return "--"
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.1f}"


def _num(value: Any) -> float:
    try:
        if value is None:
            return -1.0
        return float(value)
    except (TypeError, ValueError):
        return -1.0
