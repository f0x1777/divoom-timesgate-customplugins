from __future__ import annotations

import csv
import json
import os
from io import StringIO
from pathlib import Path
import time
from typing import Any

import requests


CACHE_PATH = Path(os.getenv("MARKET_CACHE", "logs/market_cache.json"))
CACHE_TTL_SECS = int(os.getenv("MARKET_CACHE_SECONDS", "60"))
DEFAULT_ASSETS = "BTC:crypto:bitcoin,ETH:crypto:ethereum,SPY:stooq:spy.us"


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


def _write_cache(quotes: list[dict[str, Any]]):
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(json.dumps(quotes), encoding="utf-8")
    except Exception as e:
        print(f"[market] Cache write skipped: {e}")


def _parse_assets(raw: str | None = None) -> list[tuple[str, str, str]]:
    assets: list[tuple[str, str, str]] = []
    for item in (raw or os.getenv("MARKET_ASSETS", DEFAULT_ASSETS)).split(","):
        parts = [part.strip() for part in item.split(":")]
        if len(parts) == 3 and all(parts):
            assets.append((parts[0].upper(), parts[1].lower(), parts[2]))
    return assets


def _crypto_quotes(assets: list[tuple[str, str, str]]) -> list[dict[str, Any]]:
    crypto = [(label, symbol) for label, kind, symbol in assets if kind == "crypto"]
    if not crypto:
        return []

    ids = ",".join(symbol for _, symbol in crypto)
    response = requests.get(
        "https://api.coingecko.com/api/v3/simple/price",
        params={
            "ids": ids,
            "vs_currencies": "usd",
            "include_24hr_change": "true",
        },
        timeout=8,
    )
    response.raise_for_status()
    data = response.json()

    quotes = []
    for label, symbol in crypto:
        row = data.get(symbol, {})
        if "usd" in row:
            quotes.append({
                "label": label,
                "price": float(row["usd"]),
                "change_pct": float(row.get("usd_24h_change", 0.0)),
                "source": "coingecko",
            })
    return quotes


def _stooq_quote(label: str, symbol: str) -> dict[str, Any] | None:
    response = requests.get(
        "https://stooq.com/q/l/",
        params={"s": symbol, "f": "sd2t2ohlcv", "h": "", "e": "csv"},
        timeout=8,
    )
    response.raise_for_status()
    rows = list(csv.DictReader(StringIO(response.text)))
    if not rows:
        return None
    row = rows[0]
    close = _float(row.get("Close"))
    open_price = _float(row.get("Open"))
    if close is None:
        return None
    change_pct = ((close - open_price) / open_price * 100.0) if open_price else 0.0
    return {
        "label": label,
        "price": close,
        "change_pct": change_pct,
        "source": "stooq",
    }


def _float(value: Any) -> float | None:
    try:
        if value in (None, "", "N/D"):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def get_quotes(max_items: int = 3) -> list[dict[str, Any]]:
    cached = _read_cache()
    if cached is not None:
        return cached[:max_items]

    assets = _parse_assets()
    quotes: list[dict[str, Any]] = []
    try:
        quotes.extend(_crypto_quotes(assets))
        for label, kind, symbol in assets:
            if kind == "stooq":
                quote = _stooq_quote(label, symbol)
                if quote:
                    quotes.append(quote)
    except Exception as e:
        print(f"[market] Error: {e}")
        stale = _read_stale_cache()
        if stale is not None:
            return stale[:max_items]

    ordered = []
    for label, _, _ in assets:
        match = next((quote for quote in quotes if quote.get("label") == label), None)
        if match:
            ordered.append(match)
    _write_cache(ordered)
    return ordered[:max_items]


def _read_stale_cache() -> list[dict[str, Any]] | None:
    if not CACHE_PATH.exists():
        return None
    try:
        data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, list) else None
