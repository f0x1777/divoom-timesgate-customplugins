"""
Cliente HTTP para el Divoom Times Gate.
Protocolo: POST http://<IP>/post con JSON.

Comandos que funcionan en Times Gate (confirmados):
  - Tools/SetScoreBoard  → muestra dos números grandes (azul vs rojo)
  - Tools/SetTimer       → temporizador con alarma
  - Tools/SetStopWatch   → cronómetro
  - Device/PlayBuzzer    → beep del dispositivo
  - Channel/SetBrightness→ brillo
  - Draw/SendHttpText    → texto scrolleante (a verificar en screen)
  - Draw/SendHttpGif     → acepta sin error pero NO muestra (firmware actual)
"""

import base64
import io
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import requests
from PIL import Image


_BG_GIF_BYTES: bytes | None = None
_ASSETS: dict[str, bytes] = {}
_ASSET_SERVER: ThreadingHTTPServer | None = None
_ASSET_THREAD: threading.Thread | None = None
_ASSET_HOST_IP: str | None = None


def _post(ip: str, payload: dict, timeout: int = 8) -> dict:
    try:
        r = requests.post(f"http://{ip}/post", json=payload, timeout=timeout)
        return r.json()
    except Exception as e:
        return {"error": str(e)}


# ── Scoreboard (método confirmado) ──────────────────────────────────────────

def send_scoreboard(ip: str, blue: int, red: int) -> bool:
    """
    Muestra dos números en el Times Gate usando el modo Scoreboard.
    blue / red: enteros 0-999.
    """
    resp = _post(ip, {
        "Command": "Tools/SetScoreBoard",
        "BlueScore": int(blue),
        "RedScore": int(red),
    })
    if resp.get("error_code", -1) != 0:
        print(f"[divoom] SetScoreBoard failed: {resp}")
    return resp.get("error_code", -1) == 0


def play_buzzer(
    ip: str,
    play_total_time: int = 1200,
    active_time_in_cycle: int = 200,
    off_time_in_cycle: int = 150,
) -> bool:
    """Dispara el buzzer del Divoom sin cambiar el contenido de pantalla."""
    resp = _post(ip, {
        "Command": "Device/PlayBuzzer",
        "ActiveTimeInCycle": int(active_time_in_cycle),
        "OffTimeInCycle": int(off_time_in_cycle),
        "PlayTotalTime": int(play_total_time),
    })
    if resp.get("error_code", -1) != 0:
        print(f"[divoom] PlayBuzzer failed: {resp}")
    return resp.get("error_code", -1) == 0


def send_usage_display(ip: str, session: float, week: float, design: float) -> bool:
    """
    Muestra el uso de Claude en el Times Gate vía scoreboard.

    Cicla entre dos vistas cada llamada:
      Vista 1 (par):  BlueScore=session%  RedScore=week%
      Vista 2 (impar): BlueScore=design%  RedScore=0  + texto "DESIGN"

    session, week, design: 0.0–1.0 (−1.0 = desconocido → muestra −1)
    """
    def to_int(v: float) -> int:
        return int(v * 100) if v >= 0 else -1

    s = max(0, to_int(session))
    w = max(0, to_int(week))
    d = max(0, to_int(design))

    # Vista 1: session vs week
    ok1 = send_scoreboard(ip, s, w)

    return ok1


def send_usage_cycle(ip: str, session: float, week: float, design: float,
                     hold_secs: float = 5.0) -> bool:
    """
    Muestra session vs week por hold_secs, luego design vs 0 por hold_secs.
    Útil para mostrar los tres valores en secuencia.
    """
    def to_int(v: float) -> int:
        return max(0, int(v * 100)) if v >= 0 else 0

    s = to_int(session)
    w = to_int(week)
    d = to_int(design)

    ok = send_scoreboard(ip, s, w)
    time.sleep(hold_secs)
    ok &= send_scoreboard(ip, d, 0)
    time.sleep(hold_secs)
    ok &= send_scoreboard(ip, s, w)  # vuelve a la vista principal

    return ok


def send_text(ip: str, text: str, color: str = "#FF6600",
              speed: int = 80, lcd_index: int | None = None) -> bool:
    """
    Envía texto scrolleante. lcd_index=None → sin especificar pantalla.
    """
    payload: dict = {
        "Command": "Draw/SendHttpText",
        "TextId": int(time.time()) % 100,
        "x": 0, "y": 0,
        "dir": 0,
        "font": 2,
        "TextWidth": 64,
        "Textheight": 16,
        "speed": speed,
        "color": color,
        "align": 1,
        "TextString": text,
    }
    if lcd_index is not None:
        payload["LcdIndex"] = lcd_index

    resp = _post(ip, payload)
    if resp.get("error_code", -1) != 0:
        print(f"[divoom] SendHttpText failed: {resp}")
    return resp.get("error_code", -1) == 0


def _local_ip_for(target_ip: str) -> str:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect((target_ip, 80))
        return s.getsockname()[0]


def _background_gif() -> bytes:
    global _BG_GIF_BYTES
    if _BG_GIF_BYTES is None:
        image = Image.new("RGB", (128, 128), "#050505")
        buf = io.BytesIO()
        image.save(buf, format="GIF")
        _BG_GIF_BYTES = buf.getvalue()
    return _BG_GIF_BYTES


def _set_asset(name: str, data: bytes):
    _ASSETS[name.lstrip("/")] = data


def _asset_url(target_ip: str, name: str = "bg.gif") -> str:
    global _ASSET_HOST_IP, _ASSET_SERVER, _ASSET_THREAD

    host_ip = _local_ip_for(target_ip)
    if _ASSET_SERVER is not None and _ASSET_HOST_IP == host_ip:
        return f"http://{host_ip}:{_ASSET_SERVER.server_port}/{name.lstrip('/')}"

    bg = _background_gif()
    _ASSETS.setdefault("bg.gif", bg)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            asset_name = self.path.split("?", 1)[0].lstrip("/") or "bg.gif"
            data = _ASSETS.get(asset_name)
            if data is not None:
                self.send_response(200)
                self.send_header("Content-Type", "image/gif")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            self.send_response(404)
            self.end_headers()

        def log_message(self, format, *args):
            return

    _ASSET_SERVER = ThreadingHTTPServer(("0.0.0.0", 0), Handler)
    _ASSET_THREAD = threading.Thread(target=_ASSET_SERVER.serve_forever, daemon=True)
    _ASSET_THREAD.start()
    _ASSET_HOST_IP = host_ip
    return f"http://{host_ip}:{_ASSET_SERVER.server_port}/{name.lstrip('/')}"


def send_panel_text(
    ip: str,
    lcd_index: int,
    lines: list[str],
    color: str = "#FFFFFF",
    background_url: str | None = None,
) -> bool:
    """
    Fuerza texto visible en una pantalla individual del Times Gate.

    Times Gate usa pantallas 128x128; Draw/SendHttpItemList con type=22
    crea un componente custom por panel, más visible que el scoreboard.
    """
    items = []
    y_positions = [8, 42, 76]
    for idx, line in enumerate(lines[:3]):
        items.append({
            "TextId": 10 + lcd_index * 3 + idx,
            "type": 22,
            "x": 0,
            "y": y_positions[idx],
            "dir": 0,
            "font": 4 if len(line) <= 6 else 2,
            "TextWidth": 128,
            "Textheight": 16,
            "TextString": line,
            "speed": 80,
            "color": color,
        })

    payload = {
        "Command": "Draw/SendHttpItemList",
        "LcdIndex": int(lcd_index),
        "NewFlag": 1,
        "ItemList": items,
    }
    if background_url:
        payload["BackgroudGif"] = background_url

    resp = _post(ip, payload)
    if resp.get("error_code", -1) != 0:
        print(f"[divoom] SendHttpItemList lcd={lcd_index} failed: {resp}")
    return resp.get("error_code", -1) == 0


def send_limit_panels(
    ip: str,
    provider: str,
    primary_label: str,
    primary_pct: int,
    secondary_label: str,
    secondary_pct: int,
    context_label: str | None = None,
    context_pct: int | None = None,
) -> bool:
    """Muestra limites como texto grande repartido en las 5 pantallas."""
    panels = [
        [provider.upper(), "LIMITS"],
        [primary_label.upper(), f"{primary_pct}%"],
        [secondary_label.upper(), f"{secondary_pct}%"],
    ]
    if context_label is not None and context_pct is not None:
        panels.append([context_label.upper(), f"{context_pct}%"])
    else:
        panels.append(["", ""])
    panels.append(["UPDATED", time.strftime("%H:%M")])

    ok = True
    colors = ["#FF8800", "#00AAFF", "#FF3333", "#44FF66", "#FFFFFF"]
    background_url = _asset_url(ip)
    for lcd_index, lines in enumerate(panels):
        ok &= send_panel_text(ip, lcd_index, lines, colors[lcd_index], background_url)
        time.sleep(0.15)
    time.sleep(1.5)
    return ok


def send_limit_panel(
    ip: str,
    lcd_index: int,
    title: str,
    line_1: str,
    line_2: str,
    color: str = "#FFFFFF",
) -> bool:
    """Muestra todos los limites de un proveedor en una sola pantalla."""
    return send_panel_text(
        ip,
        lcd_index,
        [title.upper(), line_1.upper(), line_2.upper()],
        color,
        _asset_url(ip),
    )


def send_image_panel(ip: str, lcd_index: int, asset_name: str, gif_bytes: bytes) -> bool:
    """Muestra un GIF renderizado como fondo del panel."""
    _set_asset(asset_name, gif_bytes)
    return send_panel_text(ip, lcd_index, [" "], "#050505", _asset_url(ip, asset_name))


def clear_panels(ip: str, lcd_indexes: list[int]) -> bool:
    """Limpia pantallas que no forman parte del dashboard actual."""
    ok = True
    background_url = _asset_url(ip)
    for lcd_index in lcd_indexes:
        ok &= send_panel_text(ip, lcd_index, ["", "", ""], "#050505", background_url)
        time.sleep(0.1)
    return ok


# ── GIF (para futura versión con firmware actualizado) ───────────────────────

def _encode_frame(img: Image.Image) -> str:
    rgb = img.convert("RGB")
    raw = bytes(v for px in rgb.getdata() for v in px)
    return base64.b64encode(raw).decode("ascii")


def send_animation(
    ip: str,
    frames: list[Image.Image],
    speed_ms: int = 600,
    lcd_index: int = 4,
) -> bool:
    """
    Envía animación GIF. Requiere firmware con soporte Draw/SendHttpGif.
    En firmware actual del Times Gate no muestra nada (pero acepta sin error).
    """
    url = f"http://{ip}/post"
    pic_id = int(time.time()) % 10000
    ok = True

    for i, frame in enumerate(frames):
        resized = frame.resize((32, 32), Image.LANCZOS)
        payload = {
            "Command": "Draw/SendHttpGif",
            "PicNum": len(frames),
            "PicWidth": 32,
            "PicOffset": i,
            "PicID": pic_id,
            "PicSpeed": speed_ms,
            "PicData": _encode_frame(resized),
            "LcdIndex": lcd_index,
        }
        try:
            r = requests.post(url, json=payload, timeout=8)
            resp = r.json()
            if resp.get("error_code", 0) != 0:
                print(f"[divoom] Frame {i}: error {resp}")
                ok = False
        except Exception as e:
            print(f"[divoom] Frame {i}: {e}")
            ok = False
        time.sleep(0.06)

    return ok


# ── Utilidades ───────────────────────────────────────────────────────────────

def ping(ip: str) -> bool:
    try:
        r = requests.post(
            f"http://{ip}/post",
            json={"Command": "Channel/GetIndex"},
            timeout=4,
        )
        return r.status_code == 200
    except Exception:
        return False


def get_device_info(ip: str) -> dict:
    try:
        r = requests.post(
            f"http://{ip}/post",
            json={"Command": "Device/GetDeviceTime"},
            timeout=4,
        )
        return r.json()
    except Exception as e:
        return {"error": str(e)}


def set_brightness(ip: str, level: int) -> bool:
    """level: 0–100"""
    resp = _post(ip, {"Command": "Channel/SetBrightness", "Brightness": int(level)})
    return resp.get("error_code", -1) == 0
