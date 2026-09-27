import logging
import os
import glob
import subprocess

logger = logging.getLogger(__name__)


class FanController:
    def __init__(self):
        hwmon_paths = glob.glob("/sys/devices/platform/hp-wmi/hwmon/hwmon*")
        if hwmon_paths:
            self.hwmon = hwmon_paths[0]
            self.pwm1 = os.path.join(self.hwmon, "pwm1")
            self.pwm2 = os.path.join(self.hwmon, "pwm2")
            self.pwm1_enable = os.path.join(self.hwmon, "pwm1_enable")
            self.available = os.path.exists(self.pwm1)
        else:
            self.hwmon = None
            self.available = False

        self._pwm_enable_cache: str = ""
        self._gpu_hwmon: str | None = self._find_gpu_hwmon()

    def _find_gpu_hwmon(self) -> str | None:
        for hwmon in sorted(glob.glob("/sys/class/hwmon/hwmon*")):
            try:
                name = open(os.path.join(hwmon, "name")).read().strip()
            except OSError:
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
        if os.path.exists(self.pwm2):
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
        for target_name in ("coretemp", "k10temp", "zenpower", "acpitz"):
            for hwmon in sorted(glob.glob("/sys/class/hwmon/hwmon*")):
                try:
                    name = open(os.path.join(hwmon, "name")).read().strip()
                except OSError:
                    continue
                if name != target_name:
                    continue
                for label_file in sorted(glob.glob(os.path.join(hwmon, "temp*_label"))):
                    try:
                        label = open(label_file).read().strip()
                        if "Package" in label or "Tdie" in label:
                            return int(open(label_file.replace("_label", "_input")).read().strip()) // 1000
                    except OSError:
                        continue
                first = sorted(glob.glob(os.path.join(hwmon, "temp1_input")))
                if first:
                    try:
                        return int(open(first[0]).read().strip()) // 1000
                    except Exception:
                        pass
        return 0

    def _read_gpu_temp(self) -> int:
        if self._gpu_hwmon:
            try:
                return int(open(os.path.join(self._gpu_hwmon, "temp1_input")).read().strip()) // 1000
            except Exception:
                pass
        try:
            out = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader"],
                text=True, timeout=2,
            )
            return int(out.strip())
        except Exception:
            pass
        return 0

    def get_rpms(self) -> dict:
        if not self.available or not self.hwmon:
            return {"fan1": 0, "fan2": 0}
        fan1, fan2 = 0, 0
        try:
            f1 = os.path.join(self.hwmon, "fan1_input")
            f2 = os.path.join(self.hwmon, "fan2_input")
            if os.path.exists(f1):
                fan1 = int(open(f1).read().strip())
            if os.path.exists(f2):
                fan2 = int(open(f2).read().strip())
        except Exception:
            pass
        return {"fan1": fan1, "fan2": fan2}


_controller = None


def get_controller() -> FanController:
    global _controller
    if _controller is None:
        _controller = FanController()
    return _controller
