import json
import logging
import os
import time
from dataclasses import asdict, dataclass, replace

from vcontrol.backend.sysfs import atomic_write_json, clamp

logger = logging.getLogger(__name__)

CONFIG_DIR = os.path.expanduser("~/.config/v-control")
PROFILES_FILE = os.path.join(CONFIG_DIR, "profiles.json")
_LOAD_INTERVAL_S = 0.5


@dataclass
class FanProfile:
    name: str
    display_name: str
    icon: str
    short_name: str = ""
    is_manual: bool = False
    manual_speed: int = 50
    hysteresis: int = 4


BUILTIN_PROFILES = [
    FanProfile("Eco", "Eco Mod", "🍃", short_name="Eco", hysteresis=6),
    FanProfile("Balanced", "Dengeli Mod", "⚖️", short_name="Dengeli", hysteresis=4),
    FanProfile("Performance", "Performans Modu", "🚀", short_name="Performans", hysteresis=4),
]
_BUILTIN_MAP = {p.name: p for p in BUILTIN_PROFILES}


class ProfileManager:
    def __init__(self) -> None:
        self._profiles = {p.name: replace(p) for p in BUILTIN_PROFILES}
        self._active_name = "Balanced"
        self._max_fan: bool = False
        self._last_mtime: float = 0.0
        self._last_load_time: float = 0.0
        self._load()

    def _load(self):
        now = time.monotonic()
        if now - self._last_load_time < _LOAD_INTERVAL_S:
            return
        self._last_load_time = now

        try:
            mtime = os.path.getmtime(PROFILES_FILE)
        except OSError:
            return
        if mtime <= self._last_mtime:
            return

        try:
            with open(PROFILES_FILE, encoding="utf-8") as f:
                data = json.load(f)
            active = data.get("active", "Balanced")
            if active in self._profiles:
                self._active_name = active
            self._max_fan = bool(data.get("max_fan", False))
            for p_data in data.get("profiles", []):
                name = p_data.get("name")
                if name in self._profiles:
                    prof = self._profiles[name]
                    prof.is_manual = bool(p_data.get("is_manual", False))
                    prof.manual_speed = clamp(p_data.get("manual_speed", 50), 30, 100, 50)
                    prof.hysteresis = clamp(p_data.get("hysteresis", 4), 1, 10, 4)
            self._last_mtime = mtime
        except (OSError, ValueError, TypeError, AttributeError) as e:
            self._last_mtime = mtime
            logger.error(f"Profile load error: {e}")

    def save(self):
        data = {
            "active": self._active_name,
            "max_fan": self._max_fan,
            "profiles": [asdict(p) for p in self._profiles.values()],
        }
        if atomic_write_json(PROFILES_FILE, data):
            try:
                self._last_mtime = os.path.getmtime(PROFILES_FILE)
            except OSError:
                pass
            self._last_load_time = time.monotonic()

    def all_profiles(self) -> list[FanProfile]:
        return [self._profiles["Eco"], self._profiles["Balanced"], self._profiles["Performance"]]

    def get_profile(self, name: str) -> FanProfile | None:
        return self._profiles.get(name)

    @property
    def active_profile(self) -> FanProfile:
        self._load()
        return self._profiles.get(self._active_name, self._profiles["Balanced"])

    @property
    def max_fan(self) -> bool:
        self._load()
        return self._max_fan

    def set_max_fan(self, enabled: bool) -> None:
        self._max_fan = bool(enabled)
        self.save()

    def set_active(self, name: str):
        if name in self._profiles:
            self._active_name = name
            self.save()

    def update_manual(self, name: str, is_manual: bool, speed: int):
        if name in self._profiles:
            self._profiles[name].is_manual = is_manual
            self._profiles[name].manual_speed = clamp(speed, 30, 100, 50)
            self.save()

    def update_hysteresis(self, name: str, hysteresis: int):
        if name in self._profiles:
            self._profiles[name].hysteresis = clamp(hysteresis, 1, 10, 4)
            self.save()

    def reset_profile(self, name: str) -> None:
        default = _BUILTIN_MAP.get(name)
        if default is not None:
            self._profiles[name] = replace(default)
            self._max_fan = False
            self.save()


_manager = None


def get_manager() -> ProfileManager:
    global _manager
    if _manager is None:
        _manager = ProfileManager()
    return _manager
