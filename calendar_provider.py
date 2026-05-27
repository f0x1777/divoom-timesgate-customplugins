from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import time
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests


CACHE_PATH = Path(os.getenv("CALENDAR_CACHE", "logs/calendar_cache.json"))
CACHE_TTL_SECS = int(os.getenv("CALENDAR_CACHE_SECONDS", "300"))
LOOKAHEAD_HOURS = int(os.getenv("CALENDAR_LOOKAHEAD_HOURS", "48"))
PAST_EVENT_HOURS = int(os.getenv("CALENDAR_PAST_EVENT_HOURS", "1"))


def _read_cache() -> list[dict[str, Any]] | None:
    if CACHE_TTL_SECS <= 0 or not CACHE_PATH.exists():
        return None
    try:
        if time.time() - CACHE_PATH.stat().st_mtime > CACHE_TTL_SECS:
            return None
        data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    if data.get("version") != 2 or data.get("source_key") != _calendar_source_key():
        return None
    events = data.get("events")
    return events if isinstance(events, list) else None


def _write_cache(events: list[dict[str, Any]]):
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 2,
            "source_key": _calendar_source_key(),
            "events": events,
        }
        CACHE_PATH.write_text(json.dumps(payload), encoding="utf-8")
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


def _parse_datetime(value: str, tzid: str | None = None) -> datetime | None:
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
            elif tzid:
                try:
                    dt = dt.replace(tzinfo=ZoneInfo(tzid))
                except ZoneInfoNotFoundError:
                    pass
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
            start = _parse_datetime(start_raw, current.get("DTSTART_TZID")) if start_raw else None
            if start:
                events.append({
                    "uid": _clean_text(current.get("UID", "")),
                    "summary": _clean_text(summary),
                    "start": start.isoformat(),
                })
            current = None
            continue
        if current is None or ":" not in line:
            continue
        raw_key, value = line.split(":", 1)
        key, params = _parse_property_key(raw_key)
        if key in ("UID", "SUMMARY", "DTSTART"):
            current[key] = value
        if key == "DTSTART" and "TZID" in params:
            current["DTSTART_TZID"] = params["TZID"]
    return events


def _parse_property_key(raw_key: str) -> tuple[str, dict[str, str]]:
    parts = raw_key.split(";")
    params: dict[str, str] = {}
    for item in parts[1:]:
        if "=" not in item:
            continue
        name, value = item.split("=", 1)
        params[name.upper()] = value.strip('"')
    return parts[0], params


def _clean_text(value: str) -> str:
    value = value.replace("\\,", ",").replace("\\n", " ").replace("\\;", ";")
    return re.sub(r"\s+", " ", value).strip()


def _calendar_urls() -> list[str]:
    urls: list[str] = []

    single = os.getenv("CALENDAR_ICS_URL", "").strip()
    if single:
        urls.append(single)

    combined = os.getenv("CALENDAR_ICS_URLS", "").strip()
    if combined:
        for item in re.split(r"[\n,]", combined):
            url = item.strip()
            if url:
                urls.append(url)

    for idx in range(1, 10):
        url = os.getenv(f"CALENDAR_ICS_URL_{idx}", "").strip()
        if url:
            urls.append(url)

    deduped: list[str] = []
    seen: set[str] = set()
    for url in urls:
        normalized = _normalize_calendar_url(url)
        if normalized not in seen:
            deduped.append(normalized)
            seen.add(normalized)
    return deduped


def _calendar_source_key() -> str:
    material = "\n".join(_calendar_urls())
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _normalize_calendar_url(url: str) -> str:
    if url.lower().startswith("webcal://"):
        return "https://" + url[len("webcal://") :]
    return url


def get_next_events(max_items: int = 1) -> list[dict[str, Any]]:
    events = _load_events()
    if not events:
        return []

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
    return upcoming[:max_items]


def get_due_events(window_seconds: int = 90, max_items: int = 3) -> list[dict[str, Any]]:
    events = _load_events()
    if not events:
        return []

    now = datetime.now().astimezone()
    since = now - timedelta(seconds=max(1, window_seconds))
    due = []
    for event in events:
        try:
            start = datetime.fromisoformat(event["start"]).astimezone()
        except Exception:
            continue
        if since <= start <= now:
            due.append(event)
    due.sort(key=lambda item: item["start"])
    return due[:max_items]


def _load_events() -> list[dict[str, Any]]:
    cached = _read_cache()
    if cached is not None:
        return cached

    events = _fetch_events()
    if events:
        _write_cache(_calendar_window(events))
        return _calendar_window(events)

    stale = _read_stale_cache()
    return stale or []


def _fetch_events() -> list[dict[str, Any]]:
    urls = _calendar_urls()
    if not urls:
        return []

    events: list[dict[str, Any]] = []
    errors: list[str] = []
    for url in urls:
        try:
            response = requests.get(url, timeout=8)
            response.raise_for_status()
            events.extend(_parse_ics(response.text))
        except Exception as e:
            errors.append(type(e).__name__)

    if errors and not events:
        print(f"[calendar] Error: {', '.join(errors)}")
    elif errors:
        print(f"[calendar] Partial errors: {', '.join(errors)}")
    return events


def _calendar_window(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    now = datetime.now().astimezone()
    since = now - timedelta(hours=max(1, PAST_EVENT_HOURS))
    until = now + timedelta(hours=LOOKAHEAD_HOURS)
    window = []
    seen: set[str] = set()
    for event in events:
        try:
            start = datetime.fromisoformat(event["start"]).astimezone()
        except Exception:
            continue
        if since <= start <= until:
            key = _event_dedupe_key(event)
            if key in seen:
                continue
            seen.add(key)
            window.append(event)
    window.sort(key=lambda item: item["start"])
    return window


def _event_dedupe_key(event: dict[str, Any]) -> str:
    uid = str(event.get("uid") or "").strip()
    start = str(event.get("start") or "").strip()
    if uid:
        return f"uid:{uid}:{start}"
    summary = _clean_text(str(event.get("summary") or "")).casefold()
    return f"fallback:{start}:{summary}"


def _read_stale_cache() -> list[dict[str, Any]] | None:
    if not CACHE_PATH.exists():
        return None
    try:
        data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    if data.get("version") != 2 or data.get("source_key") != _calendar_source_key():
        return None
    events = data.get("events")
    return events if isinstance(events, list) else None
