import os
import glob
import time
import logging
from dataclasses import dataclass, field
from collections import deque
from typing import Optional

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


def _find_hwmon_by_name(name: str) -> Optional[str]:
    for path in glob.glob(f"{HWMON_BASE}/hwmon*"):
        name_file = os.path.join(path, "name")
        try:
            with open(name_file) as f:
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


def read_cpu_temp() -> float:
    hwmon = _find_hwmon_by_name("coretemp")
    if not hwmon:
        hwmon = _find_hwmon_by_name("acpitz")
        if not hwmon:
            return 0.0
        return _read_millidegree(os.path.join(hwmon, "temp1_input"))

    for label_file in glob.glob(os.path.join(hwmon, "temp*_label")):
        try:
            with open(label_file) as f:
                label = f.read().strip()
            if "Package" in label or "Tdie" in label:
                input_file = label_file.replace("_label", "_input")
                return _read_millidegree(input_file)
        except OSError:
            continue

    first = glob.glob(os.path.join(hwmon, "temp1_input"))
    if first:
        return _read_millidegree(first[0])
    return 0.0


def read_gpu_temp() -> float:
    for driver in ("nvidia", "nouveau", "amdgpu", "radeon"):
        hwmon = _find_hwmon_by_name(driver)
        if hwmon:
            temp = _read_millidegree(os.path.join(hwmon, "temp1_input"))
            if temp > 0:
                return temp
    return 0.0


def read_nvme_temp() -> float:
    hwmon = _find_hwmon_by_name("nvme")
    if not hwmon:
        return 0.0
    return _read_millidegree(os.path.join(hwmon, "temp1_input"))


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
