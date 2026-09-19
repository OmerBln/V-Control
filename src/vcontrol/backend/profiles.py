

import json
import os
import logging
from dataclasses import dataclass, asdict
from typing import Optional

logger = logging.getLogger(__name__)

CONFIG_DIR = os.path.expanduser("~/.config/v-control")
PROFILES_FILE = os.path.join(CONFIG_DIR, "profiles.json")

@dataclass
class FanProfile:
    name: str
    display_name: str
    icon: str
    is_manual: bool = False
    manual_speed: int = 50

BUILTIN_PROFILES = [
    FanProfile("Eco", "Eco Mod", "🍃"),
    FanProfile("Balanced", "Dengeli Mod", "⚖️"),
    FanProfile("Performance", "Performans Modu", "🚀"),
]

class ProfileManager:
    def __init__(self):
        self._profiles = {p.name: p for p in BUILTIN_PROFILES}
        self._active_name = "Balanced"
        self._load()

    def _load(self):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        if not os.path.exists(PROFILES_FILE):
            return
        try:
            with open(PROFILES_FILE) as f:
                data = json.load(f)
            self._active_name = data.get("active", "Balanced")
            for p_data in data.get("profiles", []):
                name = p_data.get("name")
                if name in self._profiles:
                    self._profiles[name].is_manual = p_data.get("is_manual", False)
                    self._profiles[name].manual_speed = p_data.get("manual_speed", 50)
        except Exception as e:
            logger.error(f"Profil yükleme hatası: {e}")

    def save(self):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        data = {
            "active": self._active_name,
            "profiles": [asdict(p) for p in self._profiles.values()],
        }
        try:
            with open(PROFILES_FILE, "w") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Profil kaydetme hatası: {e}")

    def all_profiles(self) -> list[FanProfile]:
        return [self._profiles["Eco"], self._profiles["Balanced"], self._profiles["Performance"]]

    def get_profile(self, name: str) -> Optional[FanProfile]:
        return self._profiles.get(name)

    @property
    def active_profile(self) -> FanProfile:
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

_manager = None

def get_manager() -> ProfileManager:
    global _manager
    if _manager is None:
        _manager = ProfileManager()
    return _manager
