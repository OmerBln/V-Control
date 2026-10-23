import glob
import logging
import os
import subprocess
import time

from vcontrol.backend.thermal_filter import ThermalFilter

logger = logging.getLogger(__name__)

_CPU_HWMON_NAMES = ("coretemp", "k10temp", "zenpower", "acpitz")
_NVSMI_CACHE_TTL_S = 1.5
_NVSMI_RETRY_BACKOFF_S = 10.0
_NVIDIA_VENDOR_ID = "0x10de"
_DISPLAY_WINDOW_S = 5.0


def _read_hwmon_name(hwmon: str) -> str | None:
    try:
        with open(os.path.join(hwmon, "name")) as f:
            return f.read().strip()
    except OSError:
        return None


def _find_nvidia_gpu_pci_devices() -> list[str]:
    devices = []
    for dev in glob.glob("/sys/bus/pci/devices/*"):
        try:
            with open(os.path.join(dev, "vendor")) as f:
                vendor = f.read().strip()
            with open(os.path.join(dev, "class")) as f:
                pci_class = f.read().strip()
        except OSError:
            continue
        if vendor == _NVIDIA_VENDOR_ID and pci_class.startswith("0x03"):
            devices.append(dev)
    return devices


class FanController:
    def __init__(self):
        hwmon_paths = glob.glob("/sys/devices/platform/hp-wmi/hwmon/hwmon*")
        if hwmon_paths:
            self.hwmon = hwmon_paths[0]
            self.pwm1 = os.path.join(self.hwmon, "pwm1")
            self.pwm2 = os.path.join(self.hwmon, "pwm2")
            self.pwm1_enable = os.path.join(self.hwmon, "pwm1_enable")
            self.available = os.path.exists(self.pwm1)
            self._has_pwm2 = os.path.exists(self.pwm2)
            f1 = os.path.join(self.hwmon, "fan1_input")
            f2 = os.path.join(self.hwmon, "fan2_input")
            self._fan1_input = f1 if os.path.exists(f1) else None
            self._fan2_input = f2 if os.path.exists(f2) else None
        else:
            self.hwmon = None
            self.available = False
            self._has_pwm2 = False
            self._fan1_input = None
            self._fan2_input = None

        self._gpu_hwmon: str | None = self._find_gpu_hwmon()
        self._nvidia_pci: list[str] = _find_nvidia_gpu_pci_devices()
        self._cpu_temp_path: str | None = None
        self._cpu_core_paths: list[str] = []
        self._cpu_pkg_path: str | None = None
        self._find_cpu_sensors()
        self._nvsmi_value: int = 0
        self._nvsmi_next_query: float = 0.0
        self._display_cpu_filter = ThermalFilter(_DISPLAY_WINDOW_S)

    def _find_cpu_sensors(self) -> None:
        self._cpu_core_paths = []
        self._cpu_pkg_path = None
        self._cpu_temp_path = None

        hwmons = sorted(glob.glob("/sys/class/hwmon/hwmon*"))
        names = {h: _read_hwmon_name(h) for h in hwmons}
        for target_name in _CPU_HWMON_NAMES:
            for hwmon in hwmons:
                if names[hwmon] != target_name:
                    continue
                cores = []
                pkg = None
                for label_file in sorted(glob.glob(os.path.join(hwmon, "temp*_label"))):
                    try:
                        with open(label_file) as f:
                            label = f.read().strip()
                    except OSError:
                        continue
                    input_file = label_file.replace("_label", "_input")
                    if not os.path.exists(input_file):
                        continue
                    if "Package" in label or "Tdie" in label:
                        pkg = input_file
                    elif "Core" in label or "Tctl" not in label:
                        cores.append(input_file)

                if cores:
                    self._cpu_core_paths = cores
                    self._cpu_pkg_path = pkg or cores[0]
                    self._cpu_temp_path = self._cpu_pkg_path
                    logger.info(
                        f"CPU sensors resolved: {len(cores)} cores, "
                        f"pkg={os.path.basename(self._cpu_pkg_path)} ({target_name})"
                    )
                    return
                if pkg:
                    self._cpu_pkg_path = pkg
                    self._cpu_temp_path = pkg
                    return

                first = os.path.join(hwmon, "temp1_input")
                if os.path.exists(first):
                    self._cpu_temp_path = first
                    return

    @staticmethod
    def _read_millideg_int(path: str) -> int | None:
        try:
            with open(path) as f:
                return int(f.read().strip()) // 1000
        except (OSError, ValueError):
            return None

    def _find_gpu_hwmon(self) -> str | None:
        for hwmon in sorted(glob.glob("/sys/class/hwmon/hwmon*")):
            name = _read_hwmon_name(hwmon)
            if name is None:
                continue
            if name in ("nvidia", "nouveau", "amdgpu", "radeon") and os.path.exists(
                os.path.join(hwmon, "temp1_input")
            ):
                logger.info(f"GPU hwmon: {hwmon} ({name})")
                return hwmon
        return None

    def _write_sysfs(self, path: str, value: str) -> bool:
        try:
            with open(path, "w") as f:
                f.write(value)
            return True
        except PermissionError:
            try:
                subprocess.run(
                    ["sudo", "-n", "tee", path],
                    input=value.encode(),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=True,
                )
                return True
            except (OSError, subprocess.SubprocessError):
                logger.error(f"Permission denied: {path}")
        # Deliberate catch-all: this runs inside the watchdog timer callback and an
        # escaping exception would stop fan control entirely.
        except Exception as e:  # noqa: BLE001
            logger.error(f"Sysfs write error ({path}): {e}")
        return False

    def _read_sysfs(self, path: str, default: str = "") -> str:
        try:
            with open(path) as f:
                return f.read().strip()
        except (OSError, ValueError):
            return default

    def set_fan_speed(self, percent: int) -> bool:
        if not self.available:
            return False

        if not self.is_manual_mode() and not self._write_sysfs(self.pwm1_enable, "1"):
            return False

        pwm_val = max(0, min(255, round(percent / 100.0 * 255.0)))
        ok1 = self._write_sysfs(self.pwm1, str(pwm_val))
        ok2 = True
        if self._has_pwm2:
            ok2 = self._write_sysfs(self.pwm2, str(pwm_val))
        return ok1 and ok2

    def set_auto(self) -> bool:
        if not self.available:
            return False
        return self._write_sysfs(self.pwm1_enable, "2")

    def is_manual_mode(self) -> bool:
        if not self.available:
            return False
        return self._read_sysfs(self.pwm1_enable) == "1"

    def get_temperatures(self) -> dict:
        self._display_cpu_filter.add(self.read_cpu_temp_raw())
        return {
            "cpu": round(self._display_cpu_filter.value()),
            "gpu": self.read_gpu_temp(),
        }

    def read_cpu_temp_raw(self) -> int:
        if self._cpu_core_paths:
            core_vals = []
            for cp in self._cpu_core_paths:
                val = self._read_millideg_int(cp)
                if val is not None and val > 0:
                    core_vals.append(val)
            if core_vals:
                avg_core = sum(core_vals) / len(core_vals)
                pkg_val = self._read_millideg_int(self._cpu_pkg_path) if self._cpu_pkg_path else max(core_vals)
                if pkg_val is None or pkg_val <= 0:
                    pkg_val = max(core_vals)
                return round(0.7 * avg_core + 0.3 * pkg_val)

        if self._cpu_temp_path:
            val = self._read_millideg_int(self._cpu_temp_path)
            if val is not None and val > 0:
                return val

        self._find_cpu_sensors()
        if self._cpu_core_paths:
            return self.read_cpu_temp_raw()
        if self._cpu_temp_path:
            val = self._read_millideg_int(self._cpu_temp_path)
            if val is not None:
                return val
        return 0

    def _dgpu_suspended(self) -> bool:
        for dev in self._nvidia_pci:
            if self._read_sysfs(os.path.join(dev, "power", "runtime_status")) == "suspended":
                return True
        return False

    def read_gpu_temp(self) -> int:
        if self._gpu_hwmon:
            val = self._read_millideg_int(os.path.join(self._gpu_hwmon, "temp1_input"))
            if val is not None:
                return val
        if self._dgpu_suspended():
            self._nvsmi_value = 0
            self._nvsmi_next_query = 0.0
            return 0
        now = time.monotonic()
        if now < self._nvsmi_next_query:
            return self._nvsmi_value
        try:
            out = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader"],
                text=True, timeout=2,
            )
            self._nvsmi_value = int(out.strip().splitlines()[0])
            self._nvsmi_next_query = now + _NVSMI_CACHE_TTL_S
        except (OSError, subprocess.SubprocessError, ValueError):
            self._nvsmi_value = 0
            self._nvsmi_next_query = now + _NVSMI_RETRY_BACKOFF_S
        return self._nvsmi_value

    def get_rpms(self) -> dict:
        if not self.available or not self.hwmon:
            return {"fan1": 0, "fan2": 0}
        return {"fan1": self._read_rpm(self._fan1_input), "fan2": self._read_rpm(self._fan2_input)}

    @staticmethod
    def _read_rpm(path: str | None) -> int:
        if not path:
            return 0
        try:
            with open(path) as f:
                return int(f.read().strip())
        except (OSError, ValueError) as e:
            logger.debug(f"RPM read failed ({path}): {e}")
            return 0


_controller = None


def get_controller() -> FanController:
    global _controller
    if _controller is None:
        _controller = FanController()
    return _controller
