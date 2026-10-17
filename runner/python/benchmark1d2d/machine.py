"""The machine a result was computed on, for the score card's ``run`` record.

Run times mean nothing without the hardware and software behind them (SPEC
and MLPerf both require a system description with every result). ``specs()``
describes this machine with what the standard library can find on Linux,
Windows and macOS, plus ``psutil`` when it is installed; nothing here needs
privileges or network access. ``BENCH_MACHINE_LABEL`` names a machine
(for example "lab workstation") when its owner wants it shown.
"""

from __future__ import annotations

import os
import platform
import re
import subprocess
import sys
from functools import lru_cache


def _cpu_model() -> str:
    system = platform.system()
    try:
        if system == "Linux":
            with open("/proc/cpuinfo", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    if line.lower().startswith("model name"):
                        return line.split(":", 1)[1].strip()
        elif system == "Windows":
            import winreg  # type: ignore

            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as k:
                return str(winreg.QueryValueEx(k, "ProcessorNameString")[0]).strip()
        elif system == "Darwin":
            out = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True, timeout=5)
            if out.stdout.strip():
                return out.stdout.strip()
    except Exception:  # noqa: BLE001 - a description, never a failure
        pass
    return platform.processor() or platform.machine() or "unknown"


def _memory_gb() -> float | None:
    try:
        import psutil  # type: ignore

        return round(psutil.virtual_memory().total / 2**30, 1)
    except Exception:  # noqa: BLE001
        pass
    try:
        if platform.system() == "Linux":
            with open("/proc/meminfo", encoding="utf-8") as fh:
                m = re.search(r"MemTotal:\s+(\d+)\s+kB", fh.read())
                if m:
                    return round(int(m.group(1)) / 2**20, 1)
        if platform.system() == "Windows":
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong),
                            ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong),
                            ("ullAvailPageFile", ctypes.c_ulonglong), ("ullTotalVirtual", ctypes.c_ulonglong),
                            ("ullAvailVirtual", ctypes.c_ulonglong), ("sullAvailExtendedVirtual", ctypes.c_ulonglong)]

            st = MEMORYSTATUSEX()
            st.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st))  # type: ignore[attr-defined]
            return round(st.ullTotalPhys / 2**30, 1)
        if platform.system() == "Darwin":
            out = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=5)
            return round(int(out.stdout.strip()) / 2**30, 1)
    except Exception:  # noqa: BLE001
        pass
    return None


def _physical_cores() -> int | None:
    try:
        import psutil  # type: ignore

        return psutil.cpu_count(logical=False)
    except Exception:  # noqa: BLE001
        pass
    try:
        if platform.system() == "Linux":
            with open("/proc/cpuinfo", encoding="utf-8") as fh:
                pairs = set()
                phys = core = None
                for line in fh:
                    if line.startswith("physical id"):
                        phys = line.split(":")[1].strip()
                    elif line.startswith("core id"):
                        core = line.split(":")[1].strip()
                    elif not line.strip() and core is not None:
                        pairs.add((phys, core))
                        phys = core = None
                return len(pairs) or None
    except Exception:  # noqa: BLE001
        pass
    return None


def _runner() -> str:
    if os.environ.get("GITHUB_ACTIONS") == "true":
        env = os.environ.get("RUNNER_ENVIRONMENT", "github-hosted")
        image = os.environ.get("ImageOS") or os.environ.get("RUNNER_OS", "")
        return f"GitHub Actions ({env}{', ' + image if image else ''})"
    return os.environ.get("BENCH_MACHINE_LABEL") or "own machine"


@lru_cache(maxsize=1)
def specs() -> dict:
    """A short description of this machine: processor, cores, memory, OS, runner, Python."""
    rec = {
        "cpu": _cpu_model(),
        "cores_logical": os.cpu_count(),
        "cores_physical": _physical_cores(),
        "memory_gb": _memory_gb(),
        "os": f"{platform.system()} {platform.release()}".strip(),
        "arch": platform.machine(),
        "runner": _runner(),
        "python": sys.version.split()[0],
    }
    if os.environ.get("BENCH_MACHINE_LABEL"):
        rec["label"] = os.environ["BENCH_MACHINE_LABEL"]
    return {k: v for k, v in rec.items() if v not in (None, "")}


def summary(m: dict | None) -> str:
    """One line: 'AMD EPYC 7763, 4 cores, 16 GB, Linux 6.8 (GitHub Actions)'."""
    if not m:
        return ""
    cores = m.get("cores_physical") or m.get("cores_logical")
    bits = [m.get("cpu", "")]
    if cores:
        bits.append(f"{cores} cores")
    if m.get("memory_gb"):
        bits.append(f"{m['memory_gb']:g} GB")
    if m.get("os"):
        bits.append(m["os"])
    s = ", ".join(b for b in bits if b)
    return s + (f" ({m['runner']})" if m.get("runner") else "")
