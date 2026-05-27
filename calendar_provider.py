from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import time
from typing import Any

import requests


CACHE_PATH = Path(os.getenv("CALENDAR_CACHE", "logs/calendar_cache.json"))
CACHE_TTL_SECS = int(os.getenv("CALENDAR_CACHE_SECONDS", "300"))
LOOKAHEAD_HOURS = int(os.getenv("CALENDAR_LOOKAHEAD_HOURS", "48"))


def _read_cache() -> list[dict[str, Any]] | None:
    if CACHE_TTL_SECS <= 0 or not CACHE_PATH.exists():
        return None
    try:
        if time.time() - CACHE_PATH.stat().st_mtime > CACHE_TTL_SECS:
            return None
        data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, list) else None


def _write_cache(events: list[dict[str, Any]]):
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(json.dumps(events), encoding="utf-8")
    except Exception as e:
        print(f"[calendar] Cache write skipped: {e}")


def _unfold_ics(text: str) -> list[str]:
    lines: list[str] = []
    for raw in text.splitlines():
        if raw.startswith((" ", "\t")) and lines:
            lines[-1] += raw[1:]
        else:
            lines.append(raw.rstrip())
    return lines


def _parse_datetime(value: str) -> datetime | None:
    value = value.strip()
    formats = [
        ("%Y%m%dT%H%M%SZ", timezone.utc),
        ("%Y%m%dT%H%M%S", None),
        ("%Y%m%d", None),
    ]
    for fmt, tz in formats:
        try:
            dt = datetime.strptime(value, fmt)
            if tz is not None:
                dt = dt.replace(tzinfo=tz)
            return dt.astimezone() if dt.tzinfo else dt
        except ValueError:
            continue
    return None


def _parse_ics(text: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    current: dict[str, str] | None = None
    for line in _unfold_ics(text):
        if line == "BEGIN:VEVENT":
            current = {}
            continue
        if line == "END:VEVENT" and current is not None:
            summary = current.get("SUMMARY", "Calendar event")
            start_raw = current.get("DTSTART")
            start = _parse_datetime(start_raw) if start_raw else None
            if start:
                events.append({"summary": _clean_text(summary), "start": start.isoformat()})
            current = None
            continue
        if current is None or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.split(";", 1)[0]
        if key in ("SUMMARY", "DTSTART"):
            current[key] = value
    return events


def _clean_text(value: str) -> str:
    value = value.replace("\\,", ",").replace("\\n", " ").replace("\\;", ";")
    return re.sub(r"\s+", " ", value).strip()


def get_next_events(max_items: int = 1) -> list[dict[str, Any]]:
    cached = _read_cache()
    if cached is not None:
        return cached[:max_items]

    url = os.getenv("CALENDAR_ICS_URL", "").strip()
    if not url:
        return []

    try:
        response = requests.get(url, timeout=8)
        response.raise_for_status()
        events = _parse_ics(response.text)
    except Exception as e:
        print(f"[calendar] Error: {e}")
        stale = _read_stale_cache()
        return (stale or [])[:max_items]

    now = datetime.now().astimezone()
    until = now + timedelta(hours=LOOKAHEAD_HOURS)
    upcoming = []
    for event in events:
        try:
            start = datetime.fromisoformat(event["start"]).astimezone()
        except Exception:
            continue
        if now <= start <= until:
            upcoming.append(event)
    upcoming.sort(key=lambda item: item["start"])
    _write_cache(upcoming)
    return upcoming[:max_items]


def _read_stale_cache() -> list[dict[str, Any]] | None:
    if not CACHE_PATH.exists():
        return None
    try:
        data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, list) else None
