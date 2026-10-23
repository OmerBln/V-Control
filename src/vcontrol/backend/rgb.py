import glob
import logging
import os
import subprocess
from dataclasses import dataclass

logger = logging.getLogger(__name__)

HP_LIGHTING_GUIDS = [
    "14EA9746-CE1F-4098-A0E0-7045CB4DA745",
    "322F2028-0F84-4901-988E-015176049E2D",
]

LEDS_BASE = "/sys/class/leds"
WMI_BASE = "/sys/bus/wmi/devices"


@dataclass
class RGBStatus:
    brightness: int = 255
    max_brightness: int = 255
    red: int = 255
    green: int = 255
    blue: int = 255
    method: str = "none"
    supported: bool = False
    has_color: bool = False
    zones: int = 1


class RGBController:
    def __init__(self):
        self._led_path: str | None = self._find_led_path()
        self._zone_paths: list[str] = self._find_zone_paths()
        self._wmi_path: str | None = self._find_wmi_path()
        self._method = self._detect_method()
        self._has_color = self._check_color_support()
        logger.info(
            f"RGB controller initialized — method: {self._method}, "
            f"color: {self._has_color}, zones: {len(self._zone_paths) or 1}"
        )

    def _find_led_path(self) -> str | None:
        candidates = [
            os.path.join(LEDS_BASE, "hp::kbd_backlight"),
            os.path.join(LEDS_BASE, "hpmc::kbd_backlight"),
        ]
        for path in candidates:
            if os.path.isdir(path):
                return path

        matches = glob.glob(os.path.join(LEDS_BASE, "*kbd_backlight*"))
        if matches:
            return matches[0]
        return None

    def _find_zone_paths(self) -> list[str]:
        zones = sorted(glob.glob(os.path.join(LEDS_BASE, "hp::lightbar-*")))
        return zones

    def _find_wmi_path(self) -> str | None:
        for guid in HP_LIGHTING_GUIDS:
            path = os.path.join(WMI_BASE, f"{guid}-15")
            if os.path.isdir(path):
                return path
            matches = glob.glob(os.path.join(WMI_BASE, f"{guid}*"))
            if matches:
                return matches[0]
        return None

    def _detect_method(self) -> str:
        if self._led_path or self._zone_paths:
            return "sysfs_led"
        if self._wmi_path:
            return "wmi"
        return "none"

    def _check_color_support(self) -> bool:
        if self._led_path and os.path.exists(os.path.join(self._led_path, "multi_intensity")):
            return True
        return bool(self._zone_paths and os.path.exists(os.path.join(self._zone_paths[0], "multi_intensity")))

    @property
    def supported(self) -> bool:
        return self._method != "none"

    @property
    def has_color(self) -> bool:
        return self._has_color

    @property
    def method(self) -> str:
        return self._method

    def get_status(self) -> RGBStatus:
        if self._method == "sysfs_led":
            return self._read_sysfs()
        return RGBStatus(method=self._method, supported=self.supported)

    def _read_sysfs(self) -> RGBStatus:
        target = self._led_path or (self._zone_paths[0] if self._zone_paths else None)
        if not target:
            return RGBStatus(method=self._method, supported=False)

        brightness = 255
        max_brightness = 255
        red, green, blue = 255, 255, 255

        try:
            with open(os.path.join(target, "brightness")) as f:
                brightness = int(f.read().strip())
            with open(os.path.join(target, "max_brightness")) as f:
                max_brightness = int(f.read().strip())
        except (OSError, ValueError) as e:
            logger.debug(f"LED brightness read failed: {e}")

        multi_path = os.path.join(target, "multi_intensity")
        if os.path.exists(multi_path):
            try:
                with open(multi_path) as f:
                    parts = f.read().strip().split()
                    if len(parts) >= 3:
                        red = int(parts[0])
                        green = int(parts[1])
                        blue = int(parts[2])
            except (OSError, ValueError) as e:
                logger.debug(f"LED multi_intensity read failed: {e}")

        return RGBStatus(
            brightness=brightness,
            max_brightness=max_brightness,
            red=red,
            green=green,
            blue=blue,
            method="sysfs_led",
            supported=True,
            has_color=self._has_color,
            zones=len(self._zone_paths) or 1,
        )

    def set_brightness(self, level: int) -> bool:
        if not self.supported:
            return False

        level = max(0, min(255, int(level)))
        success = True
        targets = [self._led_path] if self._led_path else []
        targets.extend(self._zone_paths)

        for target in set(filter(None, targets)):
            ok = self._write_sysfs(os.path.join(target, "brightness"), str(level))
            if not ok:
                success = False
        return success

    def set_color(self, red: int, green: int, blue: int, zone: int = -1) -> bool:
        if not self._has_color:
            return False

        r = max(0, min(255, int(red)))
        g = max(0, min(255, int(green)))
        b = max(0, min(255, int(blue)))
        val_str = f"{r} {g} {b}"

        targets = []
        if zone >= 0 and zone < len(self._zone_paths):
            targets.append(self._zone_paths[zone])
        else:
            if self._led_path:
                targets.append(self._led_path)
            targets.extend(self._zone_paths)

        success = True
        for target in set(filter(None, targets)):
            ok = self._write_sysfs(os.path.join(target, "multi_intensity"), val_str)
            if not ok:
                success = False
        return success

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
        except Exception as e:  # noqa: BLE001
            logger.error(f"LED write error ({path}): {e}")
        return False

    def discover_wmi(self) -> dict:
        result = {
            "led_path": self._led_path,
            "zone_paths": self._zone_paths,
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


_controller: RGBController | None = None


def get_controller() -> RGBController:
    global _controller
    if _controller is None:
        _controller = RGBController()
    return _controller
