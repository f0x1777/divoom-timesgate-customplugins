from __future__ import annotations

import json
from datetime import datetime, timezone
from io import BytesIO
import math
import os
from pathlib import Path
from typing import Any

from PIL import Image, ImageColor, ImageDraw, ImageFont, ImageSequence


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


def _save_gif_with_durations(frames: list[Image.Image], durations: list[int], disposal: int = 1) -> bytes:
    buf = BytesIO()
    frames[0].save(
        buf,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=durations or 100,
        loop=0,
        optimize=False,
        disposal=disposal,
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


def _draw_waiting_overlay(draw: ImageDraw.ImageDraw, color: str):
    draw.rounded_rectangle((40, 27, 88, 101), radius=7, fill="#000000", outline=color, width=2)
    draw.text((54, 32), "!", font=_font(58, True), fill=color)


def _status_label(status: str | None) -> tuple[str, str]:
    normalized = (status or "chilling").lower()
    if normalized == "alerting":
        return "WAIT", "#FACC15"
    if normalized == "working":
        return "WORK", "#38BDF8"
    return "IDLE", "#94A3B8"


def _draw_status_badge(draw: ImageDraw.ImageDraw, status: str | None, outline: str):
    label, fill = _status_label(status)
    draw.rounded_rectangle((42, 55, 86, 68), radius=3, fill="#050608", outline=outline)
    draw.text((50, 57), label, font=FONT_TINY, fill=fill)


def _draw_clauddy_limit_badges(draw: ImageDraw.ImageDraw, usage: dict | None):
    if not usage:
        return
    session = _pct(_available_from_used(usage.get("session")))
    week = _pct(_available_from_used(usage.get("week")))
    _draw_limit_badges(draw, session, week, "CLAUDDY")


def _draw_codex_limit_badges(draw: ImageDraw.ImageDraw, usage: dict | None):
    if not usage:
        return
    primary = _pct(_available_from_used(usage.get("primary")))
    secondary = _pct(_available_from_used(usage.get("secondary")))
    _draw_limit_badges(draw, primary, secondary, "CODEX_PET")


def _draw_limit_badges(draw: ImageDraw.ImageDraw, first: str, second: str, env_prefix: str):
    fill = os.getenv(f"{env_prefix}_BADGE_BG", "#000000")
    outline = os.getenv(f"{env_prefix}_BADGE_OUTLINE", "#334155")
    badges = [("5H", first, 2), ("WK", second, 66)]
    for label, value, x in badges:
        draw.rounded_rectangle((x, 3, x + 60, 25), radius=3, fill=fill, outline=outline)
        draw.text((x + 4, 8), label, font=FONT_ROW, fill="#CBD5E1")
        draw.text((x + 25, 5), value, font=FONT_MED, fill="#FFFFFF")


def _replace_flat_background(rgba: Image.Image, target: str, tolerance: int = 6) -> Image.Image:
    if os.getenv("CLAUDDY_REPLACE_SOURCE_BG", "1").lower() in ("0", "false", "no"):
        return rgba
    bg = rgba.getpixel((0, 0))[:3]
    replacement = ImageColor.getrgb(target)
    px = rgba.load()
    for y in range(rgba.height):
        for x in range(rgba.width):
            r, g, b, a = px[x, y]
            if a and abs(r - bg[0]) + abs(g - bg[1]) + abs(b - bg[2]) <= tolerance:
                px[x, y] = (*replacement, a)
    return rgba


def render_codex_panel(usage: dict, waiting: bool = False, status: str | None = None) -> bytes:
    primary_avail = _available_from_used(usage.get("primary"))
    secondary_avail = _available_from_used(usage.get("secondary"))
    status = status or ("alerting" if waiting else "chilling")

    img = _base("#06100D")
    draw = ImageDraw.Draw(img)
    draw.text((7, 8), "5h", font=FONT_MED, fill="#A9B8B0")
    draw.text((49, 5), _pct(primary_avail), font=FONT_BIG, fill="#19C37D")
    draw.text((49, 31), _reset_label(usage.get("primary_reset")), font=FONT_MED, fill="#FFFFFF")
    draw.line((6, 61, 122, 61), fill="#17382A")
    draw.text((7, 70), "WK", font=FONT_MED, fill="#A9B8B0")
    draw.text((49, 67), _pct(secondary_avail), font=FONT_BIG, fill="#19C37D")
    draw.text((49, 93), _reset_label(usage.get("secondary_reset")), font=FONT_MED, fill="#FFFFFF")
    _draw_status_badge(draw, status, "#17382A")
    if waiting:
        _draw_waiting_overlay(draw, "#19C37D")
    return _save_gif([img])


def render_codex_pet_panel(status: str = "chilling", usage: dict | None = None) -> bytes:
    spritesheet_path = _codex_pet_spritesheet_path()
    if not spritesheet_path.exists():
        return render_codex_panel(usage or {}, status=status)

    state = status if status in ("chilling", "working", "alerting") else "chilling"
    frame_indexes = _codex_pet_frame_indexes(state)
    bg = os.getenv("CODEX_PET_PANEL_BG", "#000000")
    try:
        frame_ms = int(os.getenv("CODEX_PET_FRAME_MS", "180"))
    except ValueError:
        frame_ms = 180

    try:
        source = Image.open(spritesheet_path).convert("RGBA")
    except Exception:
        return render_codex_panel(usage or {}, status=status)

    columns, rows = _codex_pet_grid_size(source)
    cell_w, cell_h = _codex_pet_cell_size(source, columns, rows)
    frames: list[Image.Image] = []
    durations: list[int] = []
    for idx in frame_indexes:
        if idx < 0:
            continue
        col = idx % columns
        row = idx // columns
        x = col * cell_w
        y = row * cell_h
        if x + cell_w > source.width or y + cell_h > source.height:
            continue
        sprite = source.crop((x, y, x + cell_w, y + cell_h))
        bbox = sprite.getchannel("A").getbbox()
        if bbox:
            sprite = sprite.crop(bbox)
        sprite.thumbnail((120, 96), Image.Resampling.NEAREST)

        canvas = Image.new("RGBA", (W, H), bg)
        px = (W - sprite.width) // 2
        py = 29 + (96 - sprite.height) // 2
        if state == "alerting" and len(frames) % 2:
            py -= 2
        canvas.alpha_composite(sprite, (px, py))
        rendered = canvas.convert("RGB")
        _draw_codex_limit_badges(ImageDraw.Draw(rendered), usage)
        frames.append(rendered)
        durations.append(frame_ms)
    source.close()

    if not frames:
        return render_codex_panel(usage or {}, status=status)
    return _save_gif_with_durations(frames, durations, disposal=2)


def _codex_pet_cell_size(source: Image.Image, columns: int | None = None, rows: int | None = None) -> tuple[int, int]:
    columns, rows = (columns, rows) if columns is not None and rows is not None else _codex_pet_grid_size(source)
    return max(1, source.width // columns), max(1, source.height // rows)


def _codex_pet_grid_size(source: Image.Image) -> tuple[int, int]:
    columns = _env_int("CODEX_PET_GRID_COLUMNS", 8)
    rows = _env_int("CODEX_PET_GRID_ROWS", 9)
    return min(max(1, columns), max(1, source.width)), min(max(1, rows), max(1, source.height))


def _codex_pet_frame_indexes(state: str) -> list[int]:
    defaults = {
        "chilling": [0, 1, 2, 3, 4, 5],
        "working": [56, 57, 58, 59, 60, 61],
        "alerting": [24, 25, 26, 27],
    }
    value = os.getenv(f"CODEX_PET_{state.upper()}_FRAMES")
    if not value:
        return defaults[state]
    parsed = []
    for part in value.split(","):
        try:
            idx = int(part.strip())
        except ValueError:
            continue
        if idx >= 0:
            parsed.append(idx)
    return parsed or defaults[state]


def _codex_pet_spritesheet_path() -> Path:
    explicit = os.getenv("CODEX_PET_SPRITESHEET", "").strip()
    if explicit:
        return Path(explicit).expanduser()

    pet_name = os.getenv("CODEX_PET_NAME", "cappy").strip() or "cappy"
    pets_dir = Path(os.getenv("CODEX_PETS_DIR", "~/.codex/pets")).expanduser()
    pet_dir = pets_dir / pet_name
    manifest_path = pet_dir / "pet.json"
    if manifest_path.exists():
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            spritesheet = str(data.get("spritesheetPath") or "").strip()
            if spritesheet:
                path = Path(spritesheet).expanduser()
                resolved = None if path.is_absolute() else _safe_child_path(pet_dir, path)
                if resolved and resolved.exists():
                    return resolved
        except Exception:
            pass

    for name in ("spritesheet.webp", "spritesheet.png", "spritesheet.gif"):
        candidate = pet_dir / name
        if candidate.exists():
            return candidate
    return pet_dir / "spritesheet.webp"


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _safe_child_path(parent: Path, child: Path) -> Path | None:
    parent_resolved = parent.resolve(strict=False)
    resolved = (parent / child).resolve(strict=False)
    try:
        resolved.relative_to(parent_resolved)
    except ValueError:
        return None
    return resolved


def render_claude_panel(usage: dict, waiting: bool = False, status: str | None = None) -> bytes:
    session_avail = _available_from_used(usage.get("session"))
    week_avail = _available_from_used(usage.get("week"))
    status = status or ("alerting" if waiting else "chilling")

    img = _base("#100B06")
    draw = ImageDraw.Draw(img)
    draw.text((7, 8), "5h", font=FONT_MED, fill="#D3B08A")
    draw.text((49, 5), _pct(session_avail), font=FONT_BIG, fill="#FFB14A")
    draw.text((49, 31), _reset_label(usage.get("session_reset")), font=FONT_MED, fill="#FFFFFF")
    draw.line((6, 61, 122, 61), fill="#3D230B")
    draw.text((7, 70), "WK", font=FONT_MED, fill="#D3B08A")
    draw.text((49, 67), _pct(week_avail), font=FONT_BIG, fill="#FFB14A")
    draw.text((49, 93), _reset_label(usage.get("week_reset")), font=FONT_MED, fill="#FFFFFF")
    _draw_status_badge(draw, status, "#3D230B")
    if waiting:
        _draw_waiting_overlay(draw, "#FFB14A")
    return _save_gif([img])


def render_openai_logo_panel(waiting: bool = False) -> bytes:
    path_value = os.getenv("OPENAI_LOGO_GIF_PATH", "local/openai-logo.gif")
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
    path_value = os.getenv("STATUS_GIF_PATH", os.getenv("CLAWD_GIF_PATH", "local/status.gif"))
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


def render_clauddy_panel(status: str = "chilling", usage: dict | None = None) -> bytes:
    state = status if status in ("chilling", "working", "alerting") else "chilling"
    assets_dir = Path(os.getenv("CLAUDDY_ASSETS_DIR", "local/clauddy")).expanduser()
    bg = os.getenv("CLAUDDY_PANEL_BG", "#000000")
    path = assets_dir / f"{state}.gif"
    if not path.exists():
        return render_blank_panel()

    source = Image.open(path)
    frames: list[Image.Image] = []
    durations: list[int] = []
    for frame in ImageSequence.Iterator(source):
        rgba = frame.convert("RGBA")
        rgba = _replace_flat_background(rgba, bg)
        rgba = rgba.resize((W, H), Image.Resampling.NEAREST)
        canvas = Image.new("RGBA", (W, H), bg)
        canvas.alpha_composite(rgba, (0, 0))
        rendered = canvas.convert("RGB")
        _draw_clauddy_limit_badges(ImageDraw.Draw(rendered), usage)
        frames.append(rendered)
        durations.append(int(frame.info.get("duration", 100) or 100))
    source.close()

    if not frames:
        return render_blank_panel()
    return _save_gif_with_durations(frames, durations, disposal=2)


def render_blank_panel() -> bytes:
    return _save_gif([_base("#000000")])


def render_gengar_panel() -> bytes:
    path_value = os.getenv("CENTER_GIF_PATH", os.getenv("GENGAR_GIF_PATH", "local/center.gif"))
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
    _draw_temp_bar(draw, 5, 88, "TMP", resources.get("cpu_temp_c"), "#FBBF24")
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


def render_calendar_panel(events: list[dict[str, Any]]) -> bytes:
    img = _base("#090A12")
    draw = ImageDraw.Draw(img)

    now = datetime.now().astimezone()
    draw.text((5, 5), "CAL", font=FONT_MED, fill="#CBD5E1")
    draw.text((58, 4), now.strftime("%a %d"), font=FONT_ROW, fill="#94A3B8")
    draw.line((5, 27, 122, 27), fill="#1E293B")

    if not events:
        draw.text((16, 52), "NO EVENTS", font=FONT_MED, fill="#94A3B8")
        draw.text((19, 75), "NEXT 48H", font=FONT_ROW, fill="#64748B")
        return _save_gif([img], duration=1000)

    first = events[0]
    start = _event_start(first)
    time_label = start.strftime("%H:%M") if start else "--:--"
    day_label = start.strftime("%a") if start else "--"
    summary = _fit_text(draw, str(first.get("summary", "Event")), FONT_ROW, 116)
    draw.text((7, 34), time_label, font=FONT_BIG, fill="#FBBF24")
    draw.text((78, 39), day_label, font=FONT_ROW, fill="#94A3B8")
    draw.text((7, 64), summary, font=FONT_ROW, fill="#FFFFFF")

    y = 84
    for event in events[1:3]:
        start = _event_start(event)
        row_time = start.strftime("%H:%M") if start else "--:--"
        row_summary = _fit_text(draw, str(event.get("summary", "Event")), FONT_SMALL, 72)
        draw.text((7, y), row_time, font=FONT_ROW, fill="#A78BFA")
        draw.text((48, y + 1), row_summary, font=FONT_SMALL, fill="#CBD5E1")
        y += 17
    return _save_gif([img], duration=1000)


def _event_start(event: dict[str, Any]) -> datetime | None:
    try:
        return datetime.fromisoformat(str(event.get("start"))).astimezone()
    except Exception:
        return None


def _fit_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> str:
    clean = " ".join(text.split())
    if draw.textlength(clean, font=font) <= max_width:
        return clean
    ellipsis = "."
    while clean and draw.textlength(clean + ellipsis, font=font) > max_width:
        clean = clean[:-1]
    return (clean + ellipsis) if clean else ellipsis


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


def _draw_temp_bar(draw: ImageDraw.ImageDraw, x: int, y: int, label: str, value: Any, color: str):
    text = _temp_value(value)
    draw.text((x, y), label, font=FONT_ROW, fill="#94A3B8")

    pct_x = 123
    pct_bbox = draw.textbbox((0, 0), text, font=FONT_ROW)
    draw.text((pct_x - (pct_bbox[2] - pct_bbox[0]), y), text, font=FONT_ROW, fill=color)

    bar_x = x + 30
    bar_y = y + 3
    bar_w = 56
    bar_h = 7
    draw.rectangle((bar_x, bar_y, bar_x + bar_w, bar_y + bar_h), fill="#111827", outline="#334155")
    fill_w = _temp_fill_width(value, bar_w - 2)
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


def _temp_value(value: Any) -> str:
    number = _num(value)
    return "--C" if number < 0 else f"{round(number):02.0f}C"


def _temp_fill_width(value: Any, width: int) -> int:
    number = _num(value)
    if number < 0:
        return 0
    low = float(os.getenv("CPU_TEMP_MIN_C", "30"))
    high = float(os.getenv("CPU_TEMP_MAX_C", "100"))
    span = max(1.0, high - low)
    ratio = (number - low) / span
    return max(0, min(width, round(width * ratio)))


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
