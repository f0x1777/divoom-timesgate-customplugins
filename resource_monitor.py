from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time


NETWORK_SAMPLE_PATH = Path(os.getenv("NETWORK_SAMPLE_CACHE", "logs/network_sample.json"))


def _run(args: list[str], timeout: int = 3) -> str:
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
    return result.stdout


def _cpu_percent() -> float:
    try:
        output = _run(["ps", "-A", "-o", "%cpu="])
        total = sum(float(line.strip() or 0) for line in output.splitlines())
        cores = os.cpu_count() or 1
        return max(0.0, min(100.0, total / cores))
    except Exception:
        try:
            load = os.getloadavg()[0]
            cores = os.cpu_count() or 1
            return max(0.0, min(100.0, load / cores * 100.0))
        except Exception:
            return -1.0


def _memory_percent() -> float:
    try:
        total = int(_run(["sysctl", "-n", "hw.memsize"]).strip())
        vm_stat = _run(["vm_stat"])
        page_size_match = re.search(r"page size of (\d+) bytes", vm_stat)
        page_size = int(page_size_match.group(1)) if page_size_match else 4096
        pages: dict[str, int] = {}
        for line in vm_stat.splitlines():
            match = re.match(r"Pages ([^:]+):\s+([\d.]+)", line)
            if match:
                pages[match.group(1).lower()] = int(match.group(2).rstrip("."))
        used_pages = (
            pages.get("active", 0)
            + pages.get("wired down", 0)
            + pages.get("occupied by compressor", 0)
        )
        return max(0.0, min(100.0, used_pages * page_size / total * 100.0))
    except Exception:
        return -1.0


def _disk_percent() -> float:
    try:
        usage = shutil.disk_usage("/")
        return max(0.0, min(100.0, usage.used / usage.total * 100.0))
    except Exception:
        return -1.0


def _battery_percent() -> float:
    try:
        output = _run(["pmset", "-g", "batt"])
        match = re.search(r"(\d+)%", output)
        return float(match.group(1)) if match else -1.0
    except Exception:
        return -1.0


def _network_mbps() -> tuple[float, float]:
    try:
        current = _network_bytes()
        previous = _read_network_sample()
        _write_network_sample(current)
        if not previous:
            return -1.0, -1.0
        elapsed = max(0.001, current["timestamp"] - previous.get("timestamp", 0))
        ingress = max(0, current["ibytes"] - previous.get("ibytes", 0)) * 8 / elapsed / 1_000_000
        egress = max(0, current["obytes"] - previous.get("obytes", 0)) * 8 / elapsed / 1_000_000
        return round(ingress, 1), round(egress, 1)
    except Exception:
        return -1.0, -1.0


def _network_bytes() -> dict[str, float]:
    output = _run(["netstat", "-ibn"])
    ibytes = 0
    obytes = 0
    interfaces = _network_interfaces()
    for line in output.splitlines():
        parts = line.split()
        if len(parts) < 10 or parts[0] == "Name":
            continue
        name = parts[0].split("*", 1)[0]
        if interfaces and name not in interfaces:
            continue
        try:
            ibytes += int(parts[6])
            obytes += int(parts[9])
        except (ValueError, IndexError):
            continue
    return {"timestamp": time.time(), "ibytes": ibytes, "obytes": obytes}


def _network_interfaces() -> set[str]:
    raw = os.getenv("NETWORK_INTERFACES", "").strip()
    if raw:
        return {item.strip() for item in raw.split(",") if item.strip()}
    return {"en0", "en1"}


def _read_network_sample() -> dict[str, float] | None:
    if not NETWORK_SAMPLE_PATH.exists():
        return None
    try:
        data = json.loads(NETWORK_SAMPLE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _write_network_sample(sample: dict[str, float]):
    try:
        NETWORK_SAMPLE_PATH.parent.mkdir(parents=True, exist_ok=True)
        NETWORK_SAMPLE_PATH.write_text(json.dumps(sample), encoding="utf-8")
    except Exception as e:
        print(f"[resources] Network sample write skipped: {e}")


def get_resources() -> dict[str, float]:
    ingress, egress = _network_mbps()
    return {
        "cpu": round(_cpu_percent()),
        "memory": round(_memory_percent()),
        "disk": round(_disk_percent()),
        "battery": round(_battery_percent()),
        "net_in_mbps": ingress,
        "net_out_mbps": egress,
    }
