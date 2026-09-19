
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
            self.available = False

    def _write_sysfs(self, path: str, value: str) -> bool:
        try:
            with open(path, "w") as f:
                f.write(value)
            return True
        except PermissionError:
            try:
                subprocess.run(["sudo", "-n", "tee", path], input=value.encode(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                return True
            except Exception:
                logger.error(f"Erişim engellendi (sudo eksik olabilir): {path}")
        except Exception as e:
            logger.error(f"Sysfs yazma hatası ({path}): {e}")
        return False

    def set_fan_speed(self, percent: int) -> bool:
        if not self.available:
            return False
        
        try:
            current_mode = open(self.pwm1_enable).read().strip()
            if current_mode != "1":
                self._write_sysfs(self.pwm1_enable, "1")
        except Exception:
            pass
            
        pwm_val = int(round(percent / 100.0 * 255.0))
        pwm_val = max(0, min(255, pwm_val))
        
        ok1 = self._write_sysfs(self.pwm1, str(pwm_val))
        
        ok2 = True
        if os.path.exists(self.pwm2):
            ok2 = self._write_sysfs(self.pwm2, str(pwm_val))
            
        return ok1 and ok2

    def set_auto(self) -> bool:
        if not self.available:
            return False
        return self._write_sysfs(self.pwm1_enable, "2")
            
    def get_temperatures(self) -> dict:
        temp_cpu = 0
        temp_gpu = 0
        
        try:
            for hwmon in os.listdir('/sys/class/hwmon'):
                name = open(f'/sys/class/hwmon/{hwmon}/name').read().strip()
                if name in ('coretemp', 'k10temp', 'zenpower'):
                    temp_input = open(f'/sys/class/hwmon/{hwmon}/temp1_input').read()
                    temp_cpu = int(temp_input) // 1000
                    break
        except Exception:
            pass
            
        try:
            out = subprocess.check_output(['nvidia-smi', '--query-gpu=temperature.gpu', '--format=csv,noheader'], text=True)
            temp_gpu = int(out.strip())
        except Exception:
            pass
            
        return {"cpu": temp_cpu, "gpu": temp_gpu}

    def get_rpms(self) -> dict:
        fan1, fan2 = 0, 0
        try:
            if self.hwmon:
                f1_path = os.path.join(self.hwmon, 'fan1_input')
                f2_path = os.path.join(self.hwmon, 'fan2_input')
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
