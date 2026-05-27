from __future__ import annotations

import os
import re
import shutil
import subprocess


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


def get_resources() -> dict[str, float]:
    return {
        "cpu": round(_cpu_percent()),
        "memory": round(_memory_percent()),
        "disk": round(_disk_percent()),
        "battery": round(_battery_percent()),
    }
