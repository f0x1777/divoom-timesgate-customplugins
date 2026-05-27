from __future__ import annotations

import json
import os
import shlex
import socket
import subprocess
from typing import Any

import requests


DEFAULT_HEALTH_CHECKS = "WEB:http:http://localhost:3000,API:http:http://localhost:8000/health,DB:tcp:localhost:5432"


def _parse_checks(value: str | None = None) -> list[tuple[str, str, str]]:
    raw = DEFAULT_HEALTH_CHECKS if value is None else value
    checks: list[tuple[str, str, str]] = []
    for item in raw.split(","):
        parts = item.strip().split(":", 2)
        if len(parts) != 3:
            continue
        label, kind, target = parts
        label = label.strip()[:5]
        kind = kind.strip().lower()
        target = target.strip()
        if label and kind and target:
            checks.append((label, kind, target))
    return checks


def _http_ok(url: str, timeout: float) -> tuple[bool, str]:
    response = requests.get(url, timeout=timeout)
    return response.status_code < 400, str(response.status_code)


def _tcp_ok(target: str, timeout: float) -> tuple[bool, str]:
    host, port_text = target.rsplit(":", 1)
    with socket.create_connection((host, int(port_text)), timeout=timeout):
        return True, "open"


def _cmd_ok(command: str, timeout: float) -> tuple[bool, str]:
    result = subprocess.run(
        shlex.split(command),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    detail = str(result.returncode)
    return result.returncode == 0, detail


def check_service(label: str, kind: str, target: str, timeout: float = 1.5) -> dict[str, Any]:
    try:
        if kind == "http":
            ok, detail = _http_ok(target, timeout)
        elif kind == "tcp":
            ok, detail = _tcp_ok(target, timeout)
        elif kind == "cmd":
            ok, detail = _cmd_ok(target, timeout)
        else:
            ok, detail = False, "kind"
    except Exception as e:
        ok, detail = False, type(e).__name__

    return {
        "label": label,
        "kind": kind,
        "target": target,
        "ok": ok,
        "detail": detail,
    }


def tailscale_status(timeout: float = 1.5) -> dict[str, Any]:
    if os.getenv("TAILSCALE_HEALTH", "1").lower() in ("0", "false", "no"):
        return {"enabled": False, "ok": False, "state": "off", "peers": -1}
    try:
        result = subprocess.run(
            ["tailscale", "status", "--json"],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if result.returncode != 0:
            return {"enabled": True, "ok": False, "state": "down", "peers": -1}
        data = json.loads(result.stdout)
        state = str(data.get("BackendState", "")).lower()
        peers = data.get("Peer") or {}
        online_peers = sum(1 for peer in peers.values() if peer.get("Online"))
        return {
            "enabled": True,
            "ok": state == "running",
            "state": state or "unknown",
            "peers": online_peers,
        }
    except FileNotFoundError:
        return {"enabled": True, "ok": False, "state": "missing", "peers": -1}
    except Exception as e:
        return {"enabled": True, "ok": False, "state": type(e).__name__, "peers": -1}


def get_health(max_checks: int = 5) -> dict[str, Any]:
    timeout = float(os.getenv("HEALTH_TIMEOUT_SECONDS", "1.5"))
    checks = [
        check_service(label, kind, target, timeout=timeout)
        for label, kind, target in _parse_checks(os.getenv("HEALTH_CHECKS"))[:max_checks]
    ]
    return {
        "checks": checks,
        "tailscale": tailscale_status(timeout=timeout),
    }
