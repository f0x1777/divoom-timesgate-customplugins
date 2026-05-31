#!/usr/bin/env python3
"""
Claude/Codex Meter — muestra limites de uso en el Divoom Times Gate.

Uso:
  python main.py --login     # primera vez: abre browser para login
  python main.py --debug     # muestra que devuelven los scrapers (sin enviar)
  python main.py             # modo normal: loop infinito
  python main.py --once      # envía una vez y termina
"""

import argparse
from datetime import datetime
import hashlib
import os
import re
import subprocess
import time

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv():
        return False

load_dotenv()

DIVOOM_IP      = os.getenv("DIVOOM_IP", "")
DIVOOM_MAC     = os.getenv("DIVOOM_MAC", "")
LCD_INDEX      = int(os.getenv("DIVOOM_LCD_INDEX", "4"))
REFRESH_SECS   = int(os.getenv("REFRESH_SECONDS", "300"))
STATE_REFRESH_SECS = int(os.getenv("STATE_REFRESH_SECONDS", "15"))
VIEW_HOLD_SECS = float(os.getenv("DIVOOM_VIEW_HOLD_SECONDS", "5"))
ANIM_SPEED_MS  = 600  # ms por frame de la animación del claw
AUTO_DISCOVER  = os.getenv("DIVOOM_AUTO_DISCOVER", "1").lower() not in ("0", "false", "no")
CENTER_PANEL    = os.getenv("CENTER_PANEL", "gif").lower()
SCREEN_1_PANEL  = os.getenv("SCREEN_1_PANEL", "openai").lower()
SCREEN_2_PANEL  = os.getenv("SCREEN_2_PANEL", CENTER_PANEL if CENTER_PANEL in ("ops", "health") else "gengar").lower()
SCREEN_3_PANEL  = os.getenv("SCREEN_3_PANEL", "clawd").lower()

CODEX_WAITING_INPUT = False
CODEX_INTERACTION_STATUS = "chilling"
LAST_CODEX_WAITING_INPUT: bool | None = None
LAST_CODEX_USAGE: dict | None = None
LAST_CODEX_DISPLAY_SIGNATURE: tuple | None = None
CLAUDE_WAITING_INPUT = False
CLAUDE_INTERACTION_STATUS = "chilling"
LAST_CLAUDE_WAITING_INPUT: bool | None = None
LAST_CLAUDE_USAGE: dict | None = None
LAST_LIMIT_ZERO_STATE: dict[str, bool] = {}
LAST_CALENDAR_ALERT_KEYS: set[str] = set()
LAST_PANEL_DIGESTS: dict[int, str] = {}
LAST_PANEL_UPLOAD_TS: dict[int, float] = {}
LAST_IMMUTABLE_PANEL_SENDS: set[int] = set()

LIMIT_FIELDS = {
    "codex": (
        ("primary", "5h"),
        ("secondary", "WK"),
    ),
    "claude": (
        ("session", "5h"),
        ("week", "WK"),
    ),
}


def pct_str(v: float) -> str:
    return f"{int(v*100)}%" if v >= 0 else "?"


def to_percent(v: float) -> int:
    return max(0, int(v * 100)) if v >= 0 else 0


def available_value(v: float) -> float:
    return max(0.0, min(1.0, 1.0 - v)) if v >= 0 else -1.0


def available_pct_str(v: float) -> str:
    return pct_str(available_value(v))


def to_available_percent(v: float) -> int:
    return to_percent(available_value(v))


def normalize_mac(value: str) -> str:
    parts = re.split(r"[:-]", value.strip().lower())
    return ":".join(part.zfill(2) for part in parts if part)


def discover_divoom_ip_by_mac(mac: str = DIVOOM_MAC) -> str | None:
    target = normalize_mac(mac)
    if not target:
        return None

    try:
        result = subprocess.run(
            ["arp", "-a"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except Exception:
        return None

    for line in result.stdout.splitlines():
        ip_match = re.search(r"\(([\d.]+)\)", line)
        mac_match = re.search(r"\bat\s+([0-9a-fA-F:-]+)\s+", line)
        if ip_match and mac_match and normalize_mac(mac_match.group(1)) == target:
            return ip_match.group(1)
    return None


def apply_network_overrides(ip_arg: str | None):
    global DIVOOM_IP

    if ip_arg:
        DIVOOM_IP = ip_arg
        return

    if not AUTO_DISCOVER:
        return

    discovered = discover_divoom_ip_by_mac()
    if discovered and discovered != DIVOOM_IP:
        print(f"[meter] Divoom descubierto por MAC: {DIVOOM_IP} -> {discovered}")
        DIVOOM_IP = discovered


def has_divoom_ip() -> bool:
    if DIVOOM_IP:
        return True
    print("[meter] DIVOOM_IP is not configured. Copy .env.example to .env and set your device IP.")
    return False


def usage_is_known(usage: dict) -> bool:
    return any(isinstance(v, (int, float)) and v >= 0 for v in usage.values())


def env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.lower() in ("1", "true", "yes", "on")


def env_csv(name: str, default: str = "") -> set[str]:
    raw = os.getenv(name, default)
    return {part.strip().lower() for part in raw.split(",") if part.strip()}


def static_panel_is_immutable(panel: str) -> bool:
    immutable = env_csv("DIVOOM_IMMUTABLE_PANELS", "center,gengar,mascot")
    return panel.lower() in immutable


def min_panel_upload_seconds() -> int:
    try:
        return max(0, int(os.getenv("DIVOOM_MIN_PANEL_UPLOAD_SECONDS", "300")))
    except ValueError:
        return 300


def send_image_panel_if_changed(lcd_index: int, asset_name: str, gif: bytes, reason: str = "") -> bool:
    import divoom

    digest = hashlib.sha256(gif).hexdigest()
    label = reason or asset_name
    skip_unchanged = env_flag("DIVOOM_SKIP_UNCHANGED_PANELS", True)
    if skip_unchanged and LAST_PANEL_DIGESTS.get(lcd_index) == digest:
        print(f"[meter] SKIP - screen {lcd_index} unchanged ({label})")
        return True

    min_interval = min_panel_upload_seconds()
    last_upload = LAST_PANEL_UPLOAD_TS.get(lcd_index)
    if last_upload is not None and min_interval > 0:
        elapsed = time.time() - last_upload
        if elapsed < min_interval:
            remaining = int(min_interval - elapsed)
            print(f"[meter] SKIP - screen {lcd_index} upload cooldown {remaining}s ({label})")
            return True

    ok = divoom.send_image_panel(DIVOOM_IP, lcd_index, asset_name, gif)
    if ok:
        LAST_PANEL_DIGESTS[lcd_index] = digest
        LAST_PANEL_UPLOAD_TS[lcd_index] = time.time()
    return ok


def send_static_panel(lcd_index: int, panel: str) -> bool:
    if static_panel_is_immutable(panel) and lcd_index in LAST_IMMUTABLE_PANEL_SENDS:
        print(f"[meter] SKIP - screen {lcd_index} immutable ({panel})")
        return True

    ok = send_image_panel_if_changed(lcd_index, f"{panel}.gif", render_static_panel(panel), panel)
    if ok and static_panel_is_immutable(panel):
        LAST_IMMUTABLE_PANEL_SENDS.add(lcd_index)
    return ok


def codex_waiting_input() -> bool:
    return env_flag("CODEX_WAITING_INPUT") or CODEX_WAITING_INPUT


def claude_waiting_input() -> bool:
    return env_flag("CLAUDE_WAITING_INPUT") or CLAUDE_WAITING_INPUT


def interaction_status(provider: str) -> str:
    override = os.getenv(f"{provider.upper()}_INTERACTION_STATUS", "").strip().lower()
    if override in ("chilling", "working", "alerting"):
        return override
    if provider == "codex":
        return CODEX_INTERACTION_STATUS
    return CLAUDE_INTERACTION_STATUS


def combined_assistant_status() -> str:
    states = (interaction_status("codex"), interaction_status("claude"))
    if "alerting" in states:
        return "alerting"
    if "working" in states:
        return "working"
    return "chilling"


def clauddy_status() -> str:
    provider = os.getenv("CLAUDDY_STATUS_PROVIDER", "claude").strip().lower()
    if provider == "codex":
        return interaction_status("codex")
    if provider == "combined":
        return combined_assistant_status()
    return interaction_status("claude")


def claude_usage_panel_style() -> str:
    style = os.getenv("CLAUDE_USAGE_PANEL_STYLE", "clauddy").strip().lower()
    if style in ("clauddy", "classic"):
        return style
    return "clauddy"


def codex_usage_panel_style() -> str:
    style = os.getenv("CODEX_USAGE_PANEL_STYLE", "pet").strip().lower()
    if style in ("pet", "classic"):
        return style
    return "pet"


def interaction_state_is_stale(state: dict, provider: str) -> bool:
    timestamp = state.get("timestamp")
    if not timestamp:
        return False
    raw_limit = os.getenv(
        f"{provider.upper()}_INTERACTION_STATE_STALE_SECONDS",
        os.getenv("INTERACTION_STATE_STALE_SECONDS", "3600"),
    )
    try:
        limit = int(raw_limit)
    except ValueError:
        limit = 3600
    if limit <= 0:
        return False
    try:
        if isinstance(timestamp, (int, float)):
            ts = float(timestamp)
        else:
            ts = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return False
    return time.time() - ts > limit


def status_from_interaction_state(state: dict, provider: str = "") -> str:
    if provider and interaction_state_is_stale(state, provider):
        return "chilling"
    if state.get("waiting_input"):
        return "alerting"
    raw_state = str(state.get("state") or "").lower()
    if raw_state in ("active", "active_tool_result", "task_started", "tool_use", "working"):
        return "working"
    return "chilling"


def beep_for_interaction(provider: str = "CODEX"):
    provider = provider.upper()
    if not env_flag(f"BEEP_ON_{provider}_WAITING", env_flag("BEEP_ON_WAITING", True)):
        return
    play_alert_beep(provider)


def play_alert_beep(provider: str = "ALERT"):
    provider = provider.upper()

    if env_flag("DIVOOM_BEEP", True) and DIVOOM_IP:
        try:
            import divoom
            if divoom.play_buzzer(
                DIVOOM_IP,
                int(os.getenv("DIVOOM_BEEP_TOTAL_MS", "1800")),
                int(os.getenv("DIVOOM_BEEP_ACTIVE_MS", "300")),
                int(os.getenv("DIVOOM_BEEP_OFF_MS", "140")),
            ):
                print(f"[meter] Divoom beep OK ({provider})")
                return
        except Exception as e:
            print(f"[meter] Divoom beep failed: {e}")
    elif env_flag("DIVOOM_BEEP", True):
        print("[meter] Divoom beep skipped: DIVOOM_IP is empty")

    if not env_flag("MAC_BEEP_FALLBACK", True):
        return
    try:
        subprocess.run(["osascript", "-e", "beep 1"], timeout=2, check=False)
    except Exception as e:
        print(f"[meter] Beep failed: {e}")


def emit_pending_beeps(codex_waiting: bool = False, claude_waiting: bool = False):
    if not codex_waiting and not claude_waiting:
        return
    delay_ms = int(os.getenv("DIVOOM_BEEP_AFTER_PANEL_DELAY_MS", "250"))
    if env_flag("DIVOOM_BEEP", True) and delay_ms > 0:
        time.sleep(delay_ms / 1000)
    if codex_waiting:
        beep_for_interaction("CODEX")
    if claude_waiting:
        beep_for_interaction("CLAUDE")


def emit_limit_alerts(events: list[tuple[str, str, str]]):
    if not events:
        return
    delay_ms = int(os.getenv("DIVOOM_BEEP_AFTER_PANEL_DELAY_MS", "250"))
    if env_flag("DIVOOM_BEEP", True) and delay_ms > 0:
        time.sleep(delay_ms / 1000)
    for provider, label, state in events:
        print(f"[meter] Limit alert -> {provider.upper()} {label} {state}")
        play_alert_beep(f"{provider.upper()}_{state.upper()}")


def emit_calendar_alerts(events: list[dict]):
    if not events:
        return
    delay_ms = int(os.getenv("DIVOOM_BEEP_AFTER_PANEL_DELAY_MS", "250"))
    if env_flag("DIVOOM_BEEP", True) and delay_ms > 0:
        time.sleep(delay_ms / 1000)
    for _event in events:
        print("[meter] Calendar event alert")
        play_alert_beep("CALENDAR_EVENT")


def collect_calendar_event_alerts() -> list[dict]:
    if not env_flag("BEEP_ON_CALENDAR_EVENTS", True):
        return []
    try:
        from calendar_provider import get_due_events

        window_seconds = int(os.getenv("CALENDAR_EVENT_ALERT_WINDOW_SECONDS", "90"))
        events = get_due_events(window_seconds=window_seconds, max_items=int(os.getenv("CALENDAR_EVENT_ALERT_MAX", "3")))
    except Exception as e:
        print(f"[meter] Calendar alert error: {e}")
        return []

    alerts = []
    for event in events:
        key = _calendar_event_key(event)
        if key in LAST_CALENDAR_ALERT_KEYS:
            continue
        LAST_CALENDAR_ALERT_KEYS.add(key)
        alerts.append(event)
    return alerts


def _calendar_event_key(event: dict) -> str:
    uid = str(event.get("uid") or "").strip()
    start = str(event.get("start") or "").strip()
    if uid:
        return f"{uid}:{start}"
    return f"{start}:{str(event.get('summary') or '').strip()}"


def collect_limit_alerts(provider: str, usage: dict) -> list[tuple[str, str, str]]:
    if not env_flag("BEEP_ON_LIMIT_ALERTS", True):
        return []
    if not env_flag(f"BEEP_ON_{provider.upper()}_LIMIT_ALERTS", True):
        return []

    events: list[tuple[str, str, str]] = []
    zero_threshold = int(os.getenv("LIMIT_ZERO_AVAILABLE_PERCENT", "0"))
    for field, label in LIMIT_FIELDS.get(provider, ()):
        raw_value = usage.get(field)
        if not isinstance(raw_value, (int, float)) or raw_value < 0:
            continue
        available_percent = to_available_percent(raw_value)
        is_zero = available_percent <= zero_threshold
        key = f"{provider}:{field}"
        previous = LAST_LIMIT_ZERO_STATE.get(key)
        LAST_LIMIT_ZERO_STATE[key] = is_zero
        if previous is None or previous == is_zero:
            continue
        state = "exhausted" if is_zero else "reset"
        events.append((provider, label, state))
    return events


def refresh_codex_interaction_state(beep: bool = True) -> bool:
    global CODEX_WAITING_INPUT, CODEX_INTERACTION_STATUS, LAST_CODEX_WAITING_INPUT

    if not env_flag("CODEX_WAITING_AUTO", True):
        CODEX_WAITING_INPUT = env_flag("CODEX_WAITING_INPUT")
        CODEX_INTERACTION_STATUS = "alerting" if CODEX_WAITING_INPUT else "chilling"
        return False

    from codex_scraper import get_interaction_state

    state = get_interaction_state()
    waiting = bool(state.get("waiting_input"))
    status = status_from_interaction_state(state, "codex")
    changed = (
        LAST_CODEX_WAITING_INPUT is not None
        and (waiting != LAST_CODEX_WAITING_INPUT or status != CODEX_INTERACTION_STATUS)
    )
    if changed:
        print(f"[meter] Codex state -> {status} ({state.get('state')})")
    if changed and waiting and beep:
        beep_for_interaction()
    CODEX_WAITING_INPUT = waiting
    CODEX_INTERACTION_STATUS = status
    LAST_CODEX_WAITING_INPUT = waiting
    return changed


def refresh_claude_interaction_state(beep: bool = True) -> bool:
    global CLAUDE_WAITING_INPUT, CLAUDE_INTERACTION_STATUS, LAST_CLAUDE_WAITING_INPUT

    if not env_flag("CLAUDE_WAITING_AUTO", True):
        CLAUDE_WAITING_INPUT = env_flag("CLAUDE_WAITING_INPUT")
        CLAUDE_INTERACTION_STATUS = "alerting" if CLAUDE_WAITING_INPUT else "chilling"
        return False

    from claude_scraper import get_interaction_state

    state = get_interaction_state()
    waiting = bool(state.get("waiting_input"))
    status = status_from_interaction_state(state, "claude")
    changed = (
        LAST_CLAUDE_WAITING_INPUT is not None
        and (waiting != LAST_CLAUDE_WAITING_INPUT or status != CLAUDE_INTERACTION_STATUS)
    )
    if changed:
        print(f"[meter] Claude state -> {status} ({state.get('state')})")
    if changed and waiting and beep:
        beep_for_interaction("CLAUDE")
    CLAUDE_WAITING_INPUT = waiting
    CLAUDE_INTERACTION_STATUS = status
    LAST_CLAUDE_WAITING_INPUT = waiting
    return changed


def send_limit_view(
    label: str,
    lcd_index: int,
    primary_label: str,
    primary_value: float,
    secondary_label: str,
    secondary_value: float,
    context_label: str | None,
    context_value: float | None,
    fallback_text: str,
) -> bool:
    import divoom
    from dashboard_renderer import render_clauddy_panel, render_claude_panel, render_codex_panel, render_codex_pet_panel

    primary_pct = to_available_percent(primary_value)
    secondary_pct = to_available_percent(secondary_value)
    context_pct = to_available_percent(context_value) if context_value is not None else None
    current_usage = getattr(send_limit_view, "_usage", {})
    if label == "claude":
        claude_usage = {
            "session": primary_value,
            "week": secondary_value,
            "design": -1.0,
            "sonnet": -1.0,
            "session_reset": current_usage.get("session_reset"),
            "week_reset": current_usage.get("week_reset"),
            "design_reset": None,
            "sonnet_reset": None,
        }
        if claude_usage_panel_style() == "classic":
            gif = render_claude_panel(
                claude_usage,
                waiting=claude_waiting_input(),
                status=interaction_status("claude"),
            )
        else:
            gif = render_clauddy_panel(clauddy_status(), claude_usage)
        asset_name = "claude.gif"
    else:
        codex_usage = {
            "primary": primary_value,
            "secondary": secondary_value,
            "primary_reset": current_usage.get("primary_reset"),
            "secondary_reset": current_usage.get("secondary_reset"),
        }
        if codex_usage_panel_style() == "classic":
            gif = render_codex_panel(
                codex_usage,
                waiting=codex_waiting_input(),
                status=interaction_status("codex"),
            )
        else:
            gif = render_codex_pet_panel(interaction_status("codex"), codex_usage)
        asset_name = "codex.gif"

    divoom.set_brightness(DIVOOM_IP, 80)
    ok = send_image_panel_if_changed(lcd_index, asset_name, gif, label)

    if ok:
        print(
            f"[meter] OK - {label} panels: "
            f"{primary_label}={primary_pct}% {secondary_label}={secondary_pct}%"
            + (f" {context_label}={context_pct}%" if context_label and context_pct is not None else "")
        )
        return True

    print(f"[meter] Error al enviar paneles {label}; probando scoreboard fallback")
    ok = divoom.send_scoreboard(DIVOOM_IP, blue=primary_pct, red=secondary_pct)
    if ok:
        print(f"[meter] OK - {label} fallback: blue={primary_pct}% red={secondary_pct}%")
        divoom.send_text(DIVOOM_IP, fallback_text, color="#FF8800")
    else:
        print(f"[meter] Error al enviar {label}")
    return ok


def send_claude_usage(usage: dict) -> bool:
    global LAST_CLAUDE_USAGE
    LAST_CLAUDE_USAGE = usage
    send_limit_view._usage = usage
    return send_limit_view(
        "claude",
        4,
        "session",
        usage["session"],
        "week",
        usage["week"],
        None,
        None,
        f"CLAUDE 5H:{available_pct_str(usage['session'])} WK:{available_pct_str(usage['week'])}",
    )


def send_codex_usage(usage: dict) -> bool:
    global LAST_CODEX_USAGE, LAST_CODEX_DISPLAY_SIGNATURE
    LAST_CODEX_USAGE = usage
    send_limit_view._usage = usage
    ok = send_limit_view(
        "codex",
        0,
        "primary",
        usage["primary"],
        "week",
        usage["secondary"],
        None,
        None,
        f"CODEX 5H:{available_pct_str(usage['primary'])} WK:{available_pct_str(usage['secondary'])}",
    )
    if ok:
        LAST_CODEX_DISPLAY_SIGNATURE = codex_display_signature(usage)
    return ok


def send_static_panels() -> bool:
    ok = True
    ok &= send_static_panel(1, SCREEN_1_PANEL)
    ok &= send_static_panel(2, SCREEN_2_PANEL)
    ok &= send_static_panel(3, SCREEN_3_PANEL)
    return ok


def render_static_panel(panel: str) -> bytes:
    from dashboard_renderer import (
        render_blank_panel,
        render_calendar_panel,
        render_clauddy_panel,
        render_clawd_panel,
        render_gengar_panel,
        render_openai_logo_panel,
    )

    panel = panel.lower()
    if panel == "openai":
        return render_openai_logo_panel(codex_waiting_input())
    if panel == "ops":
        return render_ops_center_panel()
    if panel == "health":
        return render_health_center_panel()
    if panel == "calendar":
        return render_calendar_center_panel()
    if panel == "clauddy":
        return render_clauddy_panel(clauddy_status(), LAST_CLAUDE_USAGE)
    if panel in ("status", "assistant", "clawd"):
        return render_clawd_panel(claude_waiting_input())
    if panel in ("center", "mascot", "gengar"):
        return render_gengar_panel()
    return render_blank_panel()


def render_ops_center_panel() -> bytes:
    from dashboard_renderer import render_ops_panel
    from market_data import get_quotes
    from resource_monitor import get_resources

    return render_ops_panel(
        get_quotes(max_items=int(os.getenv("OPS_MARKET_ROWS", "3"))),
        get_resources(),
        [],
    )


def render_health_center_panel() -> bytes:
    from dashboard_renderer import render_health_panel
    from service_health import get_health

    return render_health_panel(get_health(max_checks=int(os.getenv("HEALTH_MAX_CHECKS", "5"))))


def render_calendar_center_panel() -> bytes:
    from calendar_provider import get_next_events
    from dashboard_renderer import render_calendar_panel

    return render_calendar_panel(get_next_events(max_items=int(os.getenv("CALENDAR_MAX_EVENTS", "3"))))


def get_claude_usage() -> dict:
    from claude_scraper import get_usage

    print("[meter] Obteniendo usage de claude.ai...")
    return get_usage()


def get_codex_usage(verbose: bool = True) -> dict:
    from codex_scraper import get_usage

    if verbose:
        print("[meter] Obteniendo usage de Codex local...")
    return get_usage()


def print_claude_usage(usage: dict):
    print(f"  CLAUDE 5H AVAILABLE -> {available_pct_str(usage['session'])}")
    print(f"  CLAUDE WK AVAILABLE -> {available_pct_str(usage['week'])}")


def print_codex_usage(usage: dict):
    print(f"  CODEX 5H AVAILABLE   -> {available_pct_str(usage['primary'])}")
    print(f"  CODEX WK AVAILABLE   -> {available_pct_str(usage['secondary'])}")


def codex_display_signature(usage: dict) -> tuple:
    return (
        to_available_percent(usage.get("primary", -1.0)),
        to_available_percent(usage.get("secondary", -1.0)),
        usage.get("primary_reset"),
        usage.get("secondary_reset"),
        codex_waiting_input(),
        interaction_status("codex"),
    )


def run_once(provider: str = "both", verbose: bool = True, hold_secs: float = VIEW_HOLD_SECS):
    codex_changed = refresh_codex_interaction_state(beep=False)
    claude_changed = refresh_claude_interaction_state(beep=False)
    codex_should_beep = codex_changed and CODEX_WAITING_INPUT
    claude_should_beep = claude_changed and CLAUDE_WAITING_INPUT
    if provider == "both":
        provider_order = ["codex", "claude"]
    else:
        provider_order = [provider]

    sent_any = False
    ok = True
    limit_events: list[tuple[str, str, str]] = []

    print(f"[meter] Enviando al Times Gate ({DIVOOM_IP})...")
    for name in provider_order:
        if name == "codex":
            usage = get_codex_usage()
            sender = send_codex_usage
            printer = print_codex_usage
        else:
            usage = get_claude_usage()
            sender = send_claude_usage
            printer = print_claude_usage

        if verbose:
            printer(usage)

        if not usage_is_known(usage):
            print(f"[meter] {name} desconocido; no envio 0% al Times Gate.")
            continue

        ok &= sender(usage)
        limit_events.extend(collect_limit_alerts(name, usage))
        sent_any = True

    if not sent_any:
        print("[meter] Usage desconocido; no envio 0% al Times Gate.")
        print("[meter] Ejecuta --debug --provider codex/claude para ver el scraper o --test-display para probar el Divoom.")
        return False
    if provider == "both":
        ok &= send_static_panels()
    emit_pending_beeps(codex_should_beep, claude_should_beep)
    emit_limit_alerts(limit_events)
    emit_calendar_alerts(collect_calendar_event_alerts())
    return ok


def refresh_waiting_display_if_needed() -> bool:
    codex_changed = refresh_codex_interaction_state(beep=False)
    claude_changed = refresh_claude_interaction_state(beep=False)
    if not codex_changed and not claude_changed:
        return False
    codex_should_beep = codex_changed and CODEX_WAITING_INPUT
    claude_should_beep = claude_changed and CLAUDE_WAITING_INPUT
    ok = True
    if codex_changed and LAST_CODEX_USAGE and usage_is_known(LAST_CODEX_USAGE):
        ok &= send_codex_usage(LAST_CODEX_USAGE)
    if claude_changed and LAST_CLAUDE_USAGE and usage_is_known(LAST_CLAUDE_USAGE):
        ok &= send_claude_usage(LAST_CLAUDE_USAGE)
    ok &= send_static_panels()
    emit_pending_beeps(codex_should_beep, claude_should_beep)
    return ok


def refresh_codex_usage_display_if_needed() -> bool:
    global LAST_CODEX_USAGE

    if not env_flag("CODEX_USAGE_WATCH", True):
        return False

    usage = get_codex_usage(verbose=False)
    if not usage_is_known(usage):
        return False

    LAST_CODEX_USAGE = usage
    signature = codex_display_signature(usage)
    if signature == LAST_CODEX_DISPLAY_SIGNATURE:
        return False

    print("[meter] Codex usage changed; refreshing panel")
    ok = send_codex_usage(usage)
    emit_limit_alerts(collect_limit_alerts("codex", usage))
    return ok


def sleep_with_state_watch(total_secs: int):
    deadline = time.time() + max(0, total_secs)
    while True:
        remaining = deadline - time.time()
        if remaining <= 0:
            return
        time.sleep(min(max(1, STATE_REFRESH_SECS), remaining))
        try:
            refresh_waiting_display_if_needed()
            refresh_codex_usage_display_if_needed()
            emit_calendar_alerts(collect_calendar_event_alerts())
        except Exception as e:
            print(f"[meter] State watch error: {e}")


def main():
    parser = argparse.ArgumentParser(description="Claude/Codex Meter para Divoom Times Gate")
    parser.add_argument("--login", action="store_true",
                        help="Abre browser para guardar cookies de claude.ai")
    parser.add_argument("--debug", action="store_true",
                        help="Muestra que devuelven los scrapers (no envía al dispositivo)")
    parser.add_argument("--once", action="store_true",
                        help="Ejecuta una vez y termina")
    parser.add_argument("--ping", action="store_true",
                        help="Verifica que el Times Gate esté online")
    parser.add_argument("--preview", action="store_true",
                        help="Genera y guarda preview.png de la imagen (sin enviar)")
    parser.add_argument("--test-display", action="store_true",
                        help="Envia valores fijos al Times Gate sin consultar Claude/Codex")
    parser.add_argument("--provider", choices=("claude", "codex", "both"),
                        default=os.getenv("METER_PROVIDER", "both"),
                        help="Integracion a mostrar")
    parser.add_argument("--hold-secs", type=float, default=VIEW_HOLD_SECS,
                        help="Segundos entre vistas cuando provider=both")
    parser.add_argument("--ip",
                        help="Sobrescribe DIVOOM_IP para esta ejecucion")
    args = parser.parse_args()

    apply_network_overrides(args.ip)

    if args.login:
        from claude_scraper import save_cookies_interactive
        save_cookies_interactive()
        return

    if args.debug:
        if args.provider in ("claude", "both"):
            from claude_scraper import dump_raw_for_debug
            dump_raw_for_debug()
        if args.provider in ("codex", "both"):
            from codex_scraper import dump_raw_for_debug
            dump_raw_for_debug()
        return

    if args.ping:
        if not has_divoom_ip():
            return
        import divoom
        ok = divoom.ping(DIVOOM_IP)
        info = divoom.get_device_info(DIVOOM_IP)
        print(f"Times Gate {DIVOOM_IP}: {'online' if ok else 'sin respuesta'}")
        print(f"Info: {info}")
        return

    if args.preview:
        from renderer import render_frames
        frames = render_frames(session=0.72, week=0.45, design=0.30)
        frames[0].save("preview.png")
        # Guardar GIF animado también
        frames[0].save(
            "preview.gif",
            save_all=True,
            append_images=frames[1:],
            loop=0,
            duration=ANIM_SPEED_MS,
        )
        print("Guardado preview.png y preview.gif con valores de ejemplo (72% / 45% / 30%)")
        return

    if args.test_display:
        if not has_divoom_ip():
            return
        print(f"[meter] Enviando prueba al Times Gate ({DIVOOM_IP})...")
        ok = True
        if args.provider in ("claude", "both"):
            ok &= send_claude_usage({"session": 0.72, "week": 0.45, "design": -1.0, "sonnet": -1.0})
        if args.provider == "both" and args.hold_secs > 0:
            time.sleep(args.hold_secs)
        if args.provider in ("codex", "both"):
            ok &= send_codex_usage({"primary": 0.18, "secondary": 0.06, "context": -1.0})
        print("[meter] Prueba enviada" if ok else "[meter] Prueba fallida")
        return

    if args.once:
        if not has_divoom_ip():
            return
        run_once(provider=args.provider, hold_secs=args.hold_secs)
        return

    # Modo loop
    if not has_divoom_ip():
        return
    print(f"[meter] Iniciando loop {args.provider} cada {REFRESH_SECS}s. Ctrl+C para detener.")
    while True:
        try:
            run_once(provider=args.provider, hold_secs=args.hold_secs)
        except KeyboardInterrupt:
            print("\n[meter] Detenido.")
            break
        except Exception as e:
            print(f"[meter] Error: {e}")
        print(f"[meter] Próxima actualización en {REFRESH_SECS}s...")
        sleep_with_state_watch(REFRESH_SECS)


if __name__ == "__main__":
    main()
