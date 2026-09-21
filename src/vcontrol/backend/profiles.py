import json
import os
import logging
import time
from dataclasses import dataclass, asdict
from typing import Optional

logger = logging.getLogger(__name__)

CONFIG_DIR = os.path.expanduser("~/.config/v-control")
PROFILES_FILE = os.path.join(CONFIG_DIR, "profiles.json")

# Minimum interval between disk re-reads (seconds)
_LOAD_INTERVAL_S = 5.0


@dataclass
class FanProfile:
    name: str
    display_name: str
    icon: str
    is_manual: bool = False
    manual_speed: int = 50
    hysteresis: int = 4


BUILTIN_PROFILES = [
    FanProfile("Eco", "Eco Mod", "🍃", hysteresis=4),
    FanProfile("Balanced", "Dengeli Mod", "⚖️", hysteresis=4),
    FanProfile("Performance", "Performans Modu", "🚀", hysteresis=4),
]


class ProfileManager:
    def __init__(self):
        self._profiles = {p.name: p for p in BUILTIN_PROFILES}
        self._active_name = "Balanced"
        self._last_mtime = 0
        self._last_load_time: float = 0.0
        self._load()

    def _load(self):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        if not os.path.exists(PROFILES_FILE):
            return

        # Rate-limit disk access: only re-check after _LOAD_INTERVAL_S seconds
        now = time.monotonic()
        if now - self._last_load_time < _LOAD_INTERVAL_S:
            return
        self._last_load_time = now

        try:
            mtime = os.path.getmtime(PROFILES_FILE)
            if mtime <= self._last_mtime:
                return
            self._last_mtime = mtime

            with open(PROFILES_FILE, encoding="utf-8") as f:
                data = json.load(f)
            self._active_name = data.get("active", "Balanced")
            for p_data in data.get("profiles", []):
                name = p_data.get("name")
                if name in self._profiles:
                    self._profiles[name].is_manual = p_data.get("is_manual", False)
                    self._profiles[name].manual_speed = p_data.get("manual_speed", 50)
                    self._profiles[name].hysteresis = p_data.get("hysteresis", 4)
        except Exception as e:
            logger.error(f"Profile load error: {e}")

    def save(self):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        data = {
            "active": self._active_name,
            "profiles": [asdict(p) for p in self._profiles.values()],
        }
        try:
            with open(PROFILES_FILE, "w") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            # Update mtime cache so we don't re-read what we just wrote
            self._last_mtime = os.path.getmtime(PROFILES_FILE)
            self._last_load_time = time.monotonic()
        except Exception as e:
            logger.error(f"Profile save error: {e}")

    def all_profiles(self) -> list[FanProfile]:
        return [self._profiles["Eco"], self._profiles["Balanced"], self._profiles["Performance"]]

    def get_profile(self, name: str) -> Optional[FanProfile]:
        return self._profiles.get(name)

    @property
    def active_profile(self) -> FanProfile:
        self._load()
        return self._profiles.get(self._active_name, self._profiles["Balanced"])

    def set_active(self, name: str):
        if name in self._profiles:
            self._active_name = name
            self.save()

    def update_manual(self, name: str, is_manual: bool, speed: int):
        if name in self._profiles:
            self._profiles[name].is_manual = is_manual
            self._profiles[name].manual_speed = speed
            self.save()

    def update_hysteresis(self, name: str, hysteresis: int):
        if name in self._profiles:
            self._profiles[name].hysteresis = max(1, min(10, hysteresis))
            self.save()


_manager = None


def get_manager() -> ProfileManager:
    global _manager
    if _manager is None:
        _manager = ProfileManager()
    return _manager
