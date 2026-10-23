import glob
import logging
import os
import time
from collections import deque
from dataclasses import dataclass, field

from vcontrol.backend.fan import get_controller

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


def _resolve_nvme_temp_path() -> str | None:
    hwmon = _find_hwmon_by_name("nvme")
    return os.path.join(hwmon, "temp1_input") if hwmon else None


_RESOLVE_RETRY_S = 30.0
_path_cache: dict[str, str] = {}
_next_resolve: dict[str, float] = {}


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
    temp = _read_millidegree(path)
    if temp > 0:
        return temp
    _path_cache.pop(key, None)
    return 0.0


def read_cpu_temp() -> float:
    return float(get_controller().get_temperatures()["cpu"])


def read_gpu_temp() -> float:
    return float(get_controller().read_gpu_temp())


def read_nvme_temp() -> float:
    return _read_cached("nvme", _resolve_nvme_temp_path)


def read_all() -> SensorReading:
    temps = get_controller().get_temperatures()
    return SensorReading(
        cpu_temp=float(temps["cpu"]),
        gpu_temp=float(temps["gpu"]),
        nvme_temp=read_nvme_temp(),
    )


_history = SensorHistory()


def get_history() -> SensorHistory:
    return _history


def update_history() -> SensorReading:
    reading = read_all()
    _history.append(reading)
    return reading
