"""
Extrae usage de Claude.

La ruta preferida en macOS usa Google Chrome ya logueado para abrir la API de
usage y leer el JSON renderizado por el browser. Eso evita descifrar cookies
manualmente y esquiva los problemas de Keychain de pycookiecheat.
"""

import json
import os
from pathlib import Path
import subprocess
import time
from datetime import datetime
import glob
import requests

ORG_ID   = os.getenv("CLAUDE_ORG_ID", "")
API_URL  = f"https://claude.ai/api/organizations/{ORG_ID}/usage" if ORG_ID else ""
HEADERS  = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
CHROME_APP = os.getenv("CLAUDE_CHROME_APP", "Google Chrome")
SCRAPER_METHOD = os.getenv("CLAUDE_SCRAPER", "chrome").lower()
CACHE_PATH = Path(os.getenv("CLAUDE_USAGE_CACHE", "logs/claude_usage_cache.json"))
CACHE_TTL_SECS = int(os.getenv("CLAUDE_USAGE_CACHE_SECONDS", "3600"))
STALE_CACHE_TTL_SECS = int(os.getenv("CLAUDE_USAGE_STALE_CACHE_SECONDS", "86400"))
CLAUDE_HOME = Path(os.getenv("CLAUDE_HOME", "~/.claude")).expanduser()


def _empty_usage(source: str) -> dict:
    return {
        "session": -1.0,
        "week": -1.0,
        "design": -1.0,
        "sonnet": -1.0,
        "session_reset": None,
        "week_reset": None,
        "design_reset": None,
        "sonnet_reset": None,
        "source": source,
    }


def _parse_pct_env(name: str) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return -1.0
    try:
        value = float(raw.strip().rstrip("%"))
    except ValueError:
        return -1.0
    if value > 1:
        value = value / 100.0
    return max(0.0, min(1.0, round(value, 4)))


def _available_from_used(value: float) -> float:
    return max(0.0, min(1.0, 1.0 - value)) if value >= 0 else -1.0


def _usage_from_env() -> dict | None:
    usage = {
        "session": _parse_pct_env("CLAUDE_SESSION_PCT"),
        "week": _parse_pct_env("CLAUDE_WEEK_PCT"),
        "design": -1.0,
        "sonnet": _parse_pct_env("CLAUDE_SONNET_PCT"),
        "session_reset": None,
        "week_reset": None,
        "design_reset": None,
        "sonnet_reset": None,
        "source": "env",
    }
    if any(isinstance(v, (int, float)) and v >= 0 for k, v in usage.items() if k != "source"):
        return usage
    return None


def _usage_from_cache(max_age_secs: int) -> dict | None:
    if max_age_secs <= 0 or not CACHE_PATH.exists():
        return None
    try:
        age = time.time() - CACHE_PATH.stat().st_mtime
        if age > max_age_secs:
            return None
        usage = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(usage, dict) or not _is_known(usage):
        return None
    usage["source"] = f"cache:{usage.get('source', 'unknown')}"
    return usage


def _write_cache(usage: dict):
    if not _is_known(usage):
        return
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(json.dumps(usage), encoding="utf-8")
    except Exception as e:
        print(f"[scraper] Cache write skipped: {e}")


def _usage_from_api_data(data: dict, source: str) -> dict:
    usage = _empty_usage(source)

    def pct(key: str) -> float:
        v = data.get(key)
        if isinstance(v, dict) and v.get("utilization") is not None:
            return round(float(v["utilization"]) / 100.0, 4)
        return -1.0

    def reset_at(key: str) -> str | None:
        v = data.get(key)
        if isinstance(v, dict):
            raw = v.get("resets_at")
            return str(raw) if raw else None
        return None

    usage["session"] = pct("five_hour")
    usage["week"] = pct("seven_day")
    usage["sonnet"] = pct("seven_day_sonnet")
    usage["session_reset"] = reset_at("five_hour")
    usage["week_reset"] = reset_at("seven_day")
    usage["sonnet_reset"] = reset_at("seven_day_sonnet")
    return usage


def _is_known(usage: dict) -> bool:
    return any(isinstance(v, (int, float)) and v >= 0 for k, v in usage.items() if k != "source")


def _extract_json(text: str) -> dict:
    stripped = text.strip()
    if stripped.startswith("{"):
        return json.loads(stripped)

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end > start:
        return json.loads(stripped[start:end + 1])
    raise ValueError("Chrome did not return JSON from Claude usage API")


def _parse_timestamp(value: str) -> float:
    if not value:
        return 0.0
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def _candidate_session_files(claude_home: Path) -> list[Path]:
    pattern = str(claude_home / "projects" / "**" / "*.jsonl")
    files = [Path(p) for p in glob.glob(pattern, recursive=True)]
    return sorted(files, key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)


def _user_message_is_tool_result(entry: dict) -> bool:
    message = entry.get("message")
    if not isinstance(message, dict):
        return False
    content = message.get("content")
    if not isinstance(content, list):
        return False
    return any(isinstance(item, dict) and item.get("type") == "tool_result" for item in content)


def _state_from_entry(entry: dict, source: Path) -> dict | None:
    entry_type = entry.get("type")
    ts = entry.get("timestamp", "")

    if entry_type == "assistant":
        message = entry.get("message")
        if not isinstance(message, dict):
            return None
        stop_reason = message.get("stop_reason")
        if stop_reason == "end_turn":
            return {
                "waiting_input": True,
                "state": "waiting_input",
                "timestamp": ts,
                "source": str(source),
            }
        if stop_reason == "tool_use":
            return {
                "waiting_input": False,
                "state": "active",
                "timestamp": ts,
                "source": str(source),
            }

    if entry_type == "user":
        return {
            "waiting_input": False,
            "state": "active_tool_result" if _user_message_is_tool_result(entry) else "active",
            "timestamp": ts,
            "source": str(source),
        }

    return None


def get_interaction_state(claude_home: Path | None = None, max_files: int = 20) -> dict:
    """Infer whether Claude Code/Desktop is waiting for user input."""
    root = claude_home or CLAUDE_HOME
    latest = {
        "waiting_input": False,
        "state": "unknown",
        "timestamp": "",
        "source": "",
    }
    latest_ts = 0.0

    try:
        for path in _candidate_session_files(root)[:max_files]:
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    state = _state_from_entry(entry, path)
                    if not state:
                        continue
                    ts = _parse_timestamp(state.get("timestamp", ""))
                    if ts >= latest_ts:
                        latest_ts = ts
                        latest = state
    except Exception as e:
        print(f"[claude] Interaction state error: {e}")

    return latest


def _usage_from_chrome() -> dict:
    if not API_URL:
        raise RuntimeError("CLAUDE_ORG_ID is not configured")

    script = r'''
on run argv
  set targetUrl to item 1 of argv
  tell application "Google Chrome"
    activate
    if (count of windows) = 0 then make new window
    set usageTab to make new tab at end of tabs of window 1 with properties {URL:targetUrl}
    set active tab index of window 1 to (count of tabs of window 1)
    repeat 20 times
      delay 0.5
      tell usageTab to set readyState to execute javascript "document.readyState"
      if readyState is "complete" then exit repeat
    end repeat
    set bodyText to ""
    repeat 20 times
      tell usageTab to set bodyText to execute javascript "document.body ? document.body.innerText : ''"
      if bodyText starts with "{" then exit repeat
      delay 0.5
    end repeat
    close usageTab
  end tell
  return bodyText
end run
'''
    try:
        result = subprocess.run(
            ["osascript", "-", API_URL],
            input=script,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except subprocess.TimeoutExpired as e:
        raise RuntimeError("Chrome AppleScript timed out; unlock Chrome or use env fallback") from e

    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(detail or "Chrome AppleScript failed")

    text = result.stdout.strip()
    data = _extract_json(text)
    return _usage_from_api_data(data, "chrome")


def _usage_from_pycookiecheat() -> dict:
    if not API_URL:
        raise RuntimeError("CLAUDE_ORG_ID is not configured")

    from pycookiecheat import chrome_cookies

    cookies = chrome_cookies("https://claude.ai")
    r = requests.get(API_URL, cookies=cookies, headers=HEADERS, timeout=10)
    r.raise_for_status()
    return _usage_from_api_data(r.json(), "pycookiecheat")


def get_usage() -> dict:
    """
    Retorna porcentajes de uso (0.0-1.0):
      session  -> ventana de 5 horas
      week     -> semanal (todos los modelos)
      sonnet   -> Sonnet semanal
    Retorna -1.0 para campos no disponibles.
    """
    env_usage = _usage_from_env()
    if env_usage:
        return env_usage

    cached_usage = _usage_from_cache(CACHE_TTL_SECS)
    if cached_usage:
        return cached_usage

    methods = []
    if SCRAPER_METHOD in ("chrome", "auto"):
        methods.append(("chrome", _usage_from_chrome))
    if SCRAPER_METHOD in ("cookies", "pycookiecheat", "auto"):
        methods.append(("pycookiecheat", _usage_from_pycookiecheat))
    if SCRAPER_METHOD not in ("chrome", "cookies", "pycookiecheat", "auto"):
        methods = [("chrome", _usage_from_chrome), ("pycookiecheat", _usage_from_pycookiecheat)]

    last_error = None
    for name, method in methods:
        try:
            usage = method()
            if _is_known(usage):
                _write_cache(usage)
                return usage
            last_error = f"{name} returned no usage fields"
        except Exception as e:
            last_error = f"{name}: {e}"

    if last_error:
        print(f"[scraper] Error: {last_error}")
    stale_usage = _usage_from_cache(STALE_CACHE_TTL_SECS)
    if stale_usage:
        print("[scraper] Usando cache stale de Claude para evitar pedir permisos otra vez.")
        return stale_usage
    return _empty_usage(SCRAPER_METHOD)


def dump_raw_for_debug():
    usage = get_usage()
    state = get_interaction_state()
    print("\n=== Usage ===")
    for k in ("session", "week", "sonnet"):
        v = _available_from_used(usage.get(k, -1.0))
        print(f"  {k:8s}: {v:.0%} available" if v >= 0 else f"  {k:8s}: desconocido")
    for k in ("session_reset", "week_reset", "sonnet_reset"):
        if usage.get(k):
            print(f"  {k:13s}: {usage[k]}")
    if usage.get("source"):
        print(f"  source  : {usage['source']}")
    print(f"  state   : {state['state']}")
    if state.get("timestamp"):
        print(f"  state_ts: {state['timestamp']}")


def save_cookies_interactive():
    print("[scraper] Abriendo Claude en Chrome para que inicies sesion.")
    subprocess.run(["open", "-a", CHROME_APP, "https://claude.ai"], check=False)
    print("[scraper] Luego ejecuta: .venv/bin/python main.py --debug --provider claude")
    print("[scraper] Alternativa: define CLAUDE_SESSION_PCT, CLAUDE_WEEK_PCT y CLAUDE_SONNET_PCT.")
