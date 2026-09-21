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

        # Cache pwm1_enable state to avoid a sysfs read on every write
        self._pwm_enable_cache: str = ""

        # Cache resolved GPU hwmon path (avoid rescanning every tick)
        self._gpu_hwmon: str | None = self._find_gpu_hwmon()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _find_gpu_hwmon(self) -> str | None:
        """Find the GPU hwmon sysfs path once at startup."""
        hwmon_base = "/sys/class/hwmon"
        for hwmon in sorted(glob.glob(f"{hwmon_base}/hwmon*")):
            try:
                name = open(os.path.join(hwmon, "name")).read().strip()
            except OSError:
                continue
            if name in ("nvidia", "nouveau", "amdgpu", "radeon"):
                temp_path = os.path.join(hwmon, "temp1_input")
                if os.path.exists(temp_path):
                    logger.info(f"GPU hwmon found via sysfs: {hwmon} ({name})")
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
                logger.error(f"Permission denied (sudoers rule missing?): {path}")
        except Exception as e:
            logger.error(f"Sysfs write error ({path}): {e}")
        return False

    def _read_sysfs(self, path: str, default: str = "") -> str:
        try:
            with open(path) as f:
                return f.read().strip()
        except Exception:
            return default

    # ------------------------------------------------------------------
    # Fan speed control
    # ------------------------------------------------------------------

    def set_fan_speed(self, percent: int) -> bool:
        if not self.available:
            return False

        # Ensure manual PWM mode — only write when state actually changed
        current_mode = self._read_sysfs(self.pwm1_enable)
        if current_mode != "1":
            ok = self._write_sysfs(self.pwm1_enable, "1")
            if ok:
                self._pwm_enable_cache = "1"
        else:
            self._pwm_enable_cache = "1"

        pwm_val = max(0, min(255, int(round(percent / 100.0 * 255.0))))
        pwm_str = str(pwm_val)

        ok1 = self._write_sysfs(self.pwm1, pwm_str)

        ok2 = True
        if os.path.exists(self.pwm2):
            ok2 = self._write_sysfs(self.pwm2, pwm_str)

        return ok1 and ok2

    def set_auto(self) -> bool:
        if not self.available:
            return False
        ok = self._write_sysfs(self.pwm1_enable, "2")
        if ok:
            self._pwm_enable_cache = "2"
        return ok

    # ------------------------------------------------------------------
    # Sensor readings  (sysfs-first, subprocess only as last resort)
    # ------------------------------------------------------------------

    def get_temperatures(self) -> dict:
        """Read CPU and GPU temperatures from sysfs (no subprocess per tick)."""
        return {"cpu": self._read_cpu_temp(), "gpu": self._read_gpu_temp()}

    def _read_cpu_temp(self) -> int:
        hwmon_base = "/sys/class/hwmon"
        for target_name in ("coretemp", "k10temp", "zenpower", "acpitz"):
            for hwmon in sorted(glob.glob(f"{hwmon_base}/hwmon*")):
                try:
                    name = open(os.path.join(hwmon, "name")).read().strip()
                except OSError:
                    continue
                if name != target_name:
                    continue
                # Prefer "Package id 0" / "Tdie" label for accurate total temp
                for label_file in sorted(glob.glob(os.path.join(hwmon, "temp*_label"))):
                    try:
                        label = open(label_file).read().strip()
                        if "Package" in label or "Tdie" in label:
                            input_file = label_file.replace("_label", "_input")
                            return int(open(input_file).read().strip()) // 1000
                    except OSError:
                        continue
                # Fallback: first temp1_input in this hwmon
                first = sorted(glob.glob(os.path.join(hwmon, "temp1_input")))
                if first:
                    try:
                        return int(open(first[0]).read().strip()) // 1000
                    except Exception:
                        pass
        return 0

    def _read_gpu_temp(self) -> int:
        # Primary: cached sysfs path — zero subprocess overhead
        if self._gpu_hwmon:
            try:
                val = int(open(os.path.join(self._gpu_hwmon, "temp1_input")).read().strip())
                return val // 1000
            except Exception:
                pass

        # Last resort: nvidia-smi (only when sysfs path is unavailable)
        try:
            out = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader"],
                text=True,
                timeout=2,
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
            f1_path = os.path.join(self.hwmon, "fan1_input")
            f2_path = os.path.join(self.hwmon, "fan2_input")
            if os.path.exists(f1_path):
                fan1 = int(open(f1_path).read().strip())
            if os.path.exists(f2_path):
                fan2 = int(open(f2_path).read().strip())
        except Exception:
            pass
        return {"fan1": fan1, "fan2": fan2}


_controller = None


def get_controller() -> FanController:
    global _controller
    if _controller is None:
        _controller = FanController()
    return _controller
