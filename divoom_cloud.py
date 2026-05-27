"""
Divoom cloud API client (appin.divoom-gz.com).
Handles login, device discovery, and pushing custom GIFs via cloud.

Times Gate uses 5 × 32×32 px LCD panels. For cloud push we need:
  1. login → token + userId
  2. get device list → find Times Gate by MAC → get DeviceId
  3. push image via cloud → Device/DrawGif

The cloud API supports both:
  - Sending commands to device (proxy mode — cloud relays to device)
  - Setting channel mode on individual panels
"""

import base64
import io
import os
import time
import requests
from PIL import Image

CLOUD_BASE = "https://appin.divoom-gz.com"
DEVICE_MAC = os.getenv("DIVOOM_MAC", "").upper()


def _post(endpoint: str, payload: dict, token: str = "", user_id: str = "") -> dict:
    if token:
        payload.setdefault("Token", token)
    if user_id:
        payload.setdefault("UserId", user_id)
    try:
        r = requests.post(f"{CLOUD_BASE}/{endpoint}", json=payload, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"ReturnCode": -1, "ReturnMessage": str(e)}


def login(email: str, password: str) -> dict:
    """
    Returns dict with keys: ok (bool), token, user_id, message.
    """
    data = _post("UserLogin", {"Email": email, "Password": password})
    code = data.get("ReturnCode", -1)
    if code == 0:
        return {
            "ok": True,
            "token": data.get("Token", ""),
            "user_id": str(data.get("UserId", "")),
            "message": "ok",
        }
    return {"ok": False, "token": "", "user_id": "", "message": data.get("ReturnMessage", str(data))}


def get_device_list(token: str, user_id: str) -> list[dict]:
    """Returns list of device dicts from the account."""
    data = _post("GetDeviceList", {}, token=token, user_id=user_id)
    if data.get("ReturnCode", -1) == 0:
        return data.get("DeviceList", [])
    return []


def find_device(token: str, user_id: str, mac: str = DEVICE_MAC) -> dict | None:
    """
    Find device by MAC address. Returns device dict or None.
    Device dict contains: DeviceId, DeviceName, DeviceMac, etc.
    """
    devices = get_device_list(token, user_id)
    mac_clean = mac.upper().replace("-", ":").replace(" ", "")
    for d in devices:
        d_mac = d.get("DeviceMac", "").upper().replace("-", ":").replace(" ", "")
        if d_mac == mac_clean:
            return d
    # If not found by MAC, return first device for debugging
    if devices:
        print(f"[cloud] MAC {mac} not found. Available: {[d.get('DeviceMac') for d in devices]}")
        print(f"[cloud] Using first device: {devices[0].get('DeviceName')} ({devices[0].get('DeviceMac')})")
        return devices[0]
    return None


def set_channel(token: str, user_id: str, device_id: int, channel: int = 3,
                lcd_index: int | None = None) -> bool:
    """
    Switch the device (or a specific panel) to a channel.
    channel=3 → Custom/DIY mode on most Divoom devices.
    """
    payload: dict = {"DeviceId": device_id, "SelectIndex": channel}
    if lcd_index is not None:
        payload["LcdIndex"] = lcd_index
    data = _post("Device/SetChannel", payload, token=token, user_id=user_id)
    ok = data.get("ReturnCode", -1) == 0
    if not ok:
        print(f"[cloud] SetChannel failed: {data}")
    return ok


def _frame_to_b64(img: Image.Image) -> str:
    """Encode PIL image as base64 raw RGB bytes."""
    rgb = img.convert("RGB")
    raw = bytes(v for px in rgb.getdata() for v in px)
    return base64.b64encode(raw).decode("ascii")


def send_gif_to_device(
    token: str,
    user_id: str,
    device_id: int,
    frames: list[Image.Image],
    speed_ms: int = 600,
    lcd_index: int = 4,
) -> bool:
    """
    Push animated GIF frames to a specific panel via cloud API.
    The cloud API relays the Draw/SendHttpGif command to the device.
    """
    pic_id = int(time.time()) % 10000
    ok = True

    for i, frame in enumerate(frames):
        # Resize to 32x32 for individual Times Gate panel
        panel = frame.resize((32, 32), Image.LANCZOS)

        payload = {
            "DeviceId": device_id,
            "Command": "Draw/SendHttpGif",
            "PicNum": len(frames),
            "PicWidth": 32,
            "PicOffset": i,
            "PicID": pic_id,
            "PicSpeed": speed_ms,
            "PicData": _frame_to_b64(panel),
            "LcdIndex": lcd_index,
        }
        data = _post("Device/Draw", payload, token=token, user_id=user_id)
        if data.get("ReturnCode", -1) != 0:
            print(f"[cloud] Frame {i} error: {data}")
            ok = False
        time.sleep(0.08)

    return ok


def send_command_to_device(
    token: str, user_id: str, device_id: int, command: dict
) -> dict:
    """Send an arbitrary local-API command via cloud relay."""
    payload = {"DeviceId": device_id, **command}
    return _post("Device/SendCommand", payload, token=token, user_id=user_id)


def probe_cloud_endpoints(token: str, user_id: str, device_id: int):
    """Debug helper: try several cloud endpoints to find what works."""
    endpoints = [
        "Device/Draw",
        "Device/DrawGif",
        "Device/SendCommand",
        "Device/SetChannel",
        "Device/Command",
    ]
    for ep in endpoints:
        r = _post(ep, {"DeviceId": device_id, "Command": "Channel/GetIndex"},
                  token=token, user_id=user_id)
        print(f"  {ep}: {r}")
