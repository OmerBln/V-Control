

import os
import glob
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

HP_LIGHTING_GUIDS = [
    "14EA9746-CE1F-4098-A0E0-7045CB4DA745",
    "322F2028-0F84-4901-988E-015176049E2D",
]

LEDS_BASE = "/sys/class/leds"
WMI_BASE = "/sys/bus/wmi/devices"

@dataclass
class RGBStatus:
    
    brightness: int = 0
    max_brightness: int = 3
    red: int = 255
    green: int = 255
    blue: int = 255
    method: str = "none"
    supported: bool = False

class RGBController:

    def __init__(self):
        self._led_path: Optional[str] = self._find_led_path()
        self._wmi_path: Optional[str] = self._find_wmi_path()
        self._method = self._detect_method()
        logger.info(f"RGB kontrolcüsü başlatıldı — yöntem: {self._method}")

    def _find_led_path(self) -> Optional[str]:
        
        candidates = [
            os.path.join(LEDS_BASE, "hp::kbd_backlight"),
            os.path.join(LEDS_BASE, "hpmc::kbd_backlight"),
        ]
        for path in candidates:
            if os.path.isdir(path):
                logger.info(f"LED sysfs bulundu: {path}")
                return path

        matches = glob.glob(os.path.join(LEDS_BASE, "*kbd_backlight*"))
        if matches:
            logger.info(f"LED sysfs bulundu (wildcard): {matches[0]}")
            return matches[0]
        return None

    def _find_wmi_path(self) -> Optional[str]:
        
        for guid in HP_LIGHTING_GUIDS:
            path = os.path.join(WMI_BASE, f"{guid}-15")
            if os.path.isdir(path):
                return path
            matches = glob.glob(os.path.join(WMI_BASE, f"{guid}*"))
            if matches:
                return matches[0]
        return None

    def _detect_method(self) -> str:
        if self._led_path:
            return "sysfs_led"
        if self._wmi_path:
            return "wmi"
        return "none"

    @property
    def supported(self) -> bool:
        return self._method != "none"

    @property
    def method(self) -> str:
        return self._method

    def get_status(self) -> RGBStatus:
        
        if self._method == "sysfs_led":
            return self._read_sysfs()
        return RGBStatus(method=self._method, supported=self.supported)

    def _read_sysfs(self) -> RGBStatus:
        
        brightness = 0
        max_brightness = 3
        try:
            with open(os.path.join(self._led_path, "brightness")) as f:
                brightness = int(f.read().strip())
            with open(os.path.join(self._led_path, "max_brightness")) as f:
                max_brightness = int(f.read().strip())
        except (OSError, ValueError) as e:
            logger.warning(f"LED okuma hatası: {e}")

        return RGBStatus(
            brightness=brightness,
            max_brightness=max_brightness,
            method="sysfs_led",
            supported=True,
        )

    def set_brightness(self, level: int) -> bool:
        
        if not self.supported:
            logger.warning("RGB desteklenmiyor — parlaklık ayarlanamıyor.")
            return False

        if self._method == "sysfs_led":
            return self._write_sysfs("brightness", level)
        return False

    def _write_sysfs(self, attr: str, value: int) -> bool:
        try:
            path = os.path.join(self._led_path, attr)
            with open(path, "w") as f:
                f.write(str(value))
            return True
        except OSError as e:
            logger.error(f"LED yazma hatası [{attr}={value}]: {e}")
            return False

    def discover_wmi(self) -> dict:
        
        result = {
            "led_path": self._led_path,
            "wmi_path": self._wmi_path,
            "method": self._method,
            "hp_guids_found": [],
        }
        for device in glob.glob(os.path.join(WMI_BASE, "*")):
            device_id = os.path.basename(device)
            for guid in HP_LIGHTING_GUIDS:
                if guid.upper() in device_id.upper():
                    result["hp_guids_found"].append(device_id)
        return result

_controller: Optional[RGBController] = None

def get_controller() -> RGBController:
    global _controller
    if _controller is None:
        _controller = RGBController()
    return _controller
