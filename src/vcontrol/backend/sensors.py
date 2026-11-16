import logging
import os
import time
from collections import deque
from dataclasses import dataclass, field

import psutil

from vcontrol.backend.fan import get_controller
from vcontrol.backend.sysfs import find_hwmon_by_name, read_millideg

logger = logging.getLogger(__name__)

HWMON_BASE = "/sys/class/hwmon"
HISTORY_SIZE = 150
_RESOLVE_RETRY_S = 30.0
_path_cache: dict[str, str] = {}
_next_resolve: dict[str, float] = {}

# Prime psutil's delta counter once so the first UI tick reports real CPU load.
try:
    psutil.cpu_percent(interval=None)
except Exception:  # noqa: BLE001
    pass


@dataclass
class SensorReading:
    cpu_temp: float = 0.0
    gpu_temp: float = 0.0
    nvme_temp: float = 0.0
    cpu_freq_ghz: float = 0.0
    timestamp: float = field(default_factory=time.time)


class SensorHistory:
    def __init__(self, maxlen: int = HISTORY_SIZE):
        self._data: deque[SensorReading] = deque(maxlen=maxlen)

    def append(self, reading: SensorReading) -> None:
        self._data.append(reading)

    def __len__(self) -> int:
        return len(self._data)


def _resolve_nvme_temp_path() -> str | None:
    hwmon = find_hwmon_by_name("nvme", HWMON_BASE)
    return os.path.join(hwmon, "temp1_input") if hwmon else None


def _read_cached(key: str, resolver) -> float:
    path = _path_cache.get(key)
    if path is None:
        # Sensor may appear later (module load, hotplug); retry with a backoff
        # instead of caching its absence forever.
        now = time.monotonic()
        if now < _next_resolve.get(key, 0.0):
            return 0.0
        path = resolver()
        if not path:
            _next_resolve[key] = now + _RESOLVE_RETRY_S
            return 0.0
        _path_cache[key] = path
    temp = read_millideg(path)
    if temp is not None and temp > 0:
        return float(temp)
    _path_cache.pop(key, None)
    return 0.0


def read_nvme_temp() -> float:
    return _read_cached("nvme", _resolve_nvme_temp_path)


def read_cpu_freq_ghz() -> float:
    try:
        freq = psutil.cpu_freq()
    except (OSError, RuntimeError, AttributeError):
        return 0.0
    if freq is None or freq.current <= 0:
        return 0.0
    return freq.current / 1000.0


def read_all() -> SensorReading:
    temps = get_controller().get_temperatures()
    return SensorReading(
        cpu_temp=float(temps["cpu"]),
        gpu_temp=float(temps["gpu"]),
        nvme_temp=read_nvme_temp(),
        cpu_freq_ghz=read_cpu_freq_ghz(),
    )


_history = SensorHistory()


def get_history() -> SensorHistory:
    return _history


def update_history() -> SensorReading:
    reading = read_all()
    _history.append(reading)
    return reading
