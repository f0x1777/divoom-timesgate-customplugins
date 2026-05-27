"""
Reads Codex usage from local session logs.

Codex writes token_count events under ~/.codex/sessions/**/*.jsonl. Those events
include account rate limit percentages without requiring auth token access.
"""

from __future__ import annotations

from datetime import datetime, timezone
import glob
import json
import os
from pathlib import Path
from typing import Any


CODEX_HOME = Path(os.getenv("CODEX_HOME", "~/.codex")).expanduser()


def _unknown(source: str = "") -> dict:
    return {
        "primary": -1.0,
        "secondary": -1.0,
        "context": -1.0,
        "source": source,
        "timestamp": "",
    }


def _parse_timestamp(value: str) -> float:
    if not value:
        return 0.0
    try:
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized).timestamp()
    except ValueError:
        return 0.0


def _pct_from_rate_limit(rate_limits: dict[str, Any], key: str) -> float:
    bucket = rate_limits.get(key)
    if not isinstance(bucket, dict):
        return -1.0
    used_percent = bucket.get("used_percent")
    if used_percent is None:
        return -1.0
    try:
        return round(float(used_percent) / 100.0, 4)
    except (TypeError, ValueError):
        return -1.0


def _reset_from_rate_limit(rate_limits: dict[str, Any], key: str) -> int | None:
    bucket = rate_limits.get(key)
    if not isinstance(bucket, dict):
        return None
    resets_at = bucket.get("resets_at")
    if resets_at is None:
        return None
    try:
        return int(resets_at)
    except (TypeError, ValueError):
        return None


def _window_from_rate_limit(rate_limits: dict[str, Any], key: str) -> int | None:
    bucket = rate_limits.get(key)
    if not isinstance(bucket, dict):
        return None
    window_minutes = bucket.get("window_minutes")
    if window_minutes is None:
        return None
    try:
        return int(window_minutes)
    except (TypeError, ValueError):
        return None


def _context_usage(info: dict[str, Any]) -> float:
    total = info.get("last_token_usage") or info.get("total_token_usage")
    window = info.get("model_context_window")
    if not isinstance(total, dict) or not window:
        return -1.0
    try:
        return round(float(total.get("total_tokens", 0)) / float(window), 4)
    except (TypeError, ValueError, ZeroDivisionError):
        return -1.0


def _available_from_used(value: float) -> float:
    return max(0.0, min(1.0, 1.0 - value)) if value >= 0 else -1.0


def _usage_from_token_count(event: dict[str, Any], source: str) -> dict | None:
    if event.get("type") != "event_msg":
        return None

    payload = event.get("payload")
    if not isinstance(payload, dict) or payload.get("type") != "token_count":
        return None

    rate_limits = payload.get("rate_limits")
    info = payload.get("info")
    if not isinstance(rate_limits, dict):
        return None
    if not isinstance(info, dict):
        info = {}

    return {
        "primary": _pct_from_rate_limit(rate_limits, "primary"),
        "secondary": _pct_from_rate_limit(rate_limits, "secondary"),
        "primary_reset": _reset_from_rate_limit(rate_limits, "primary"),
        "secondary_reset": _reset_from_rate_limit(rate_limits, "secondary"),
        "primary_window_minutes": _window_from_rate_limit(rate_limits, "primary"),
        "secondary_window_minutes": _window_from_rate_limit(rate_limits, "secondary"),
        "context": _context_usage(info),
        "source": source,
        "timestamp": event.get("timestamp", ""),
    }


def _candidate_files(codex_home: Path) -> list[Path]:
    patterns = [
        str(codex_home / "sessions" / "**" / "*.jsonl"),
        str(codex_home / "archived_sessions" / "*.jsonl"),
    ]
    files: list[Path] = []
    for pattern in patterns:
        files.extend(Path(p) for p in glob.glob(pattern, recursive=True))
    return sorted(files, key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)


def get_interaction_state(codex_home: Path | None = None, max_files: int = 20) -> dict:
    """Infer whether Codex is actively working or waiting for user input."""
    root = codex_home or CODEX_HOME
    latest: dict[str, Any] = {
        "waiting_input": False,
        "state": "unknown",
        "timestamp": "",
        "source": "",
    }
    latest_ts = 0.0

    try:
        for path in _candidate_files(root)[:max_files]:
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    if event.get("type") != "event_msg":
                        continue
                    payload = event.get("payload")
                    if not isinstance(payload, dict):
                        continue

                    payload_type = payload.get("type")
                    if payload_type not in ("task_started", "task_complete"):
                        continue

                    ts = _parse_timestamp(event.get("timestamp", ""))
                    if ts >= latest_ts:
                        latest_ts = ts
                        latest = {
                            "waiting_input": payload_type == "task_complete",
                            "state": "waiting_input" if payload_type == "task_complete" else "active",
                            "timestamp": event.get("timestamp", ""),
                            "source": str(path),
                        }
    except Exception as e:
        print(f"[codex] Interaction state error: {e}")

    return latest


def get_usage(codex_home: Path | None = None, max_files: int = 50) -> dict:
    """
    Returns Codex usage percentages as 0.0-1.0:
      primary   -> shorter rolling rate-limit window, usually 5h
      secondary -> longer rolling rate-limit window, usually weekly
      context   -> current thread context window usage when available
    """
    root = codex_home or CODEX_HOME
    latest = _unknown()
    latest_ts = 0.0

    try:
        for path in _candidate_files(root)[:max_files]:
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    usage = _usage_from_token_count(event, str(path))
                    if not usage:
                        continue

                    ts = _parse_timestamp(usage["timestamp"])
                    if ts >= latest_ts:
                        latest = usage
                        latest_ts = ts
    except Exception as e:
        print(f"[codex] Error: {e}")

    return latest


def dump_raw_for_debug():
    usage = get_usage()
    state = get_interaction_state()
    print("\n=== Codex Usage ===")
    for key in ("primary", "secondary", "context"):
        value = _available_from_used(usage[key])
        print(f"  {key:9s}: {value:.0%} available" if value >= 0 else f"  {key:9s}: desconocido")
    if usage.get("timestamp"):
        print(f"  timestamp: {usage['timestamp']}")
    print(f"  state    : {state['state']}")
    if state.get("timestamp"):
        print(f"  state_ts : {state['timestamp']}")
