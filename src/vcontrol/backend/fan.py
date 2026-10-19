import logging
import os
import glob
import subprocess
import time

logger = logging.getLogger(__name__)

_CPU_HWMON_NAMES = ("coretemp", "k10temp", "zenpower", "acpitz")
_NVSMI_CACHE_TTL_S = 1.5
_NVSMI_RETRY_BACKOFF_S = 10.0


def _read_hwmon_name(hwmon: str) -> str | None:
    try:
        with open(os.path.join(hwmon, "name")) as f:
            return f.read().strip()
    except OSError:
        return None


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

        self._pwm_enable_cache: str = ""
        self._gpu_hwmon: str | None = self._find_gpu_hwmon()
        self._cpu_temp_path: str | None = self._find_cpu_temp_path()
        self._nvsmi_value: int = 0
        self._nvsmi_next_query: float = 0.0

    def _find_cpu_temp_path(self) -> str | None:
        hwmons = sorted(glob.glob("/sys/class/hwmon/hwmon*"))
        names = {h: _read_hwmon_name(h) for h in hwmons}
        for target_name in _CPU_HWMON_NAMES:
            for hwmon in hwmons:
                if names[hwmon] != target_name:
                    continue
                for label_file in sorted(glob.glob(os.path.join(hwmon, "temp*_label"))):
                    try:
                        with open(label_file) as f:
                            label = f.read().strip()
                    except OSError:
                        continue
                    if "Package" in label or "Tdie" in label:
                        return label_file.replace("_label", "_input")
                first = os.path.join(hwmon, "temp1_input")
                if os.path.exists(first):
                    return first
        return None

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
            if name in ("nvidia", "nouveau", "amdgpu", "radeon"):
                if os.path.exists(os.path.join(hwmon, "temp1_input")):
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
            except Exception:
                logger.error(f"Permission denied: {path}")
        except Exception as e:
            logger.error(f"Sysfs write error ({path}): {e}")
        return False

    def _read_sysfs(self, path: str, default: str = "") -> str:
        try:
            with open(path) as f:
                return f.read().strip()
        except Exception:
            return default

    def set_fan_speed(self, percent: int) -> bool:
        if not self.available:
            return False

        current_mode = self._read_sysfs(self.pwm1_enable)
        if current_mode != "1":
            ok = self._write_sysfs(self.pwm1_enable, "1")
            if ok:
                self._pwm_enable_cache = "1"
        else:
            self._pwm_enable_cache = "1"

        pwm_val = max(0, min(255, int(round(percent / 100.0 * 255.0))))
        ok1 = self._write_sysfs(self.pwm1, str(pwm_val))
        ok2 = True
        if self._has_pwm2:
            ok2 = self._write_sysfs(self.pwm2, str(pwm_val))
        return ok1 and ok2

    def set_auto(self) -> bool:
        if not self.available:
            return False
        ok = self._write_sysfs(self.pwm1_enable, "2")
        if ok:
            self._pwm_enable_cache = "2"
        return ok

    def get_temperatures(self) -> dict:
        return {"cpu": self._read_cpu_temp(), "gpu": self._read_gpu_temp()}

    def _read_cpu_temp(self) -> int:
        if self._cpu_temp_path:
            val = self._read_millideg_int(self._cpu_temp_path)
            if val is not None:
                return val
        # Path missing or stale (hwmon renumbered): re-resolve once
        self._cpu_temp_path = self._find_cpu_temp_path()
        if self._cpu_temp_path:
            val = self._read_millideg_int(self._cpu_temp_path)
            if val is not None:
                return val
        return 0

    def _read_gpu_temp(self) -> int:
        if self._gpu_hwmon:
            val = self._read_millideg_int(os.path.join(self._gpu_hwmon, "temp1_input"))
            if val is not None:
                return val
        now = time.monotonic()
        if now < self._nvsmi_next_query:
            return self._nvsmi_value
        try:
            out = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader"],
                text=True, timeout=2,
            )
            self._nvsmi_value = int(out.strip())
            self._nvsmi_next_query = now + _NVSMI_CACHE_TTL_S
        except Exception:
            self._nvsmi_value = 0
            self._nvsmi_next_query = now + _NVSMI_RETRY_BACKOFF_S
        return self._nvsmi_value

    def get_rpms(self) -> dict:
        if not self.available or not self.hwmon:
            return {"fan1": 0, "fan2": 0}
        fan1, fan2 = 0, 0
        try:
            if self._fan1_input:
                with open(self._fan1_input) as f:
                    fan1 = int(f.read().strip())
            if self._fan2_input:
                with open(self._fan2_input) as f:
                    fan2 = int(f.read().strip())
        except Exception:
            pass
        return {"fan1": fan1, "fan2": fan2}


_controller = None


def get_controller() -> FanController:
    global _controller
    if _controller is None:
        _controller = FanController()
    return _controller
