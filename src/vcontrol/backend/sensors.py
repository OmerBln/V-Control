import glob
import logging
import os
import time
from collections import deque
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

HWMON_BASE = "/sys/class/hwmon"
HISTORY_SIZE = 150


@dataclass
class SensorReading:
    cpu_temp: float = 0.0
    gpu_temp: float = 0.0
    nvme_temp: float = 0.0
    timestamp: float = field(default_factory=time.time)


class SensorHistory:
    def __init__(self, maxlen: int = HISTORY_SIZE):
        self._data: deque[SensorReading] = deque(maxlen=maxlen)

    def append(self, reading: SensorReading):
        self._data.append(reading)

    def get_cpu_temps(self) -> list[float]:
        return [r.cpu_temp for r in self._data]

    def get_gpu_temps(self) -> list[float]:
        return [r.gpu_temp for r in self._data]

    def __len__(self) -> int:
        return len(self._data)


def _find_hwmon_by_name(name: str) -> str | None:
    for path in glob.glob(f"{HWMON_BASE}/hwmon*"):
        try:
            with open(os.path.join(path, "name")) as f:
                if f.read().strip() == name:
                    return path
        except OSError:
            continue
    return None


def _read_millidegree(path: str) -> float:
    try:
        with open(path) as f:
            return int(f.read().strip()) / 1000.0
    except (OSError, ValueError):
        return 0.0


def _resolve_cpu_temp_path() -> str | None:
    for target_name in ("coretemp", "k10temp", "zenpower", "acpitz"):
        hwmon = _find_hwmon_by_name(target_name)
        if not hwmon:
            continue

        for label_file in glob.glob(os.path.join(hwmon, "temp*_label")):
            try:
                with open(label_file) as f:
                    label = f.read().strip()
                if "Package" in label or "Tdie" in label:
                    return label_file.replace("_label", "_input")
            except OSError:
                continue

        first = os.path.join(hwmon, "temp1_input")
        if os.path.exists(first):
            return first
    return None


def _resolve_gpu_temp_path() -> str | None:
    for driver in ("nvidia", "nouveau", "amdgpu", "radeon"):
        hwmon = _find_hwmon_by_name(driver)
        if hwmon:
            path = os.path.join(hwmon, "temp1_input")
            if os.path.exists(path):
                return path
    return None


def _resolve_nvme_temp_path() -> str | None:
    hwmon = _find_hwmon_by_name("nvme")
    return os.path.join(hwmon, "temp1_input") if hwmon else None


_UNRESOLVED = object()
_path_cache: dict = {}


def _read_cached(key: str, resolver) -> float:
    path = _path_cache.get(key, _UNRESOLVED)
    if path is _UNRESOLVED:
        path = _path_cache[key] = resolver()
    if path:
        temp = _read_millidegree(path)
        if temp > 0:
            return temp
        # Stale path (hwmon renumbered): force re-resolve on next call
        _path_cache.pop(key, None)
    return 0.0


def read_cpu_temp() -> float:
    return _read_cached("cpu", _resolve_cpu_temp_path)


def read_gpu_temp() -> float:
    temp = _read_cached("gpu", _resolve_gpu_temp_path)
    if temp > 0:
        return temp
    # Shares FanController's throttled nvidia-smi cache to avoid duplicate spawns
    from vcontrol.backend.fan import get_controller
    return float(get_controller()._read_gpu_temp())


def read_nvme_temp() -> float:
    return _read_cached("nvme", _resolve_nvme_temp_path)


def read_all() -> SensorReading:
    return SensorReading(
        cpu_temp=read_cpu_temp(),
        gpu_temp=read_gpu_temp(),
        nvme_temp=read_nvme_temp(),
    )


_history = SensorHistory()


def get_history() -> SensorHistory:
    return _history


def update_history() -> SensorReading:
    reading = read_all()
    _history.append(reading)
    return reading
