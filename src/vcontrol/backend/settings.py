import json
import logging
import os
from dataclasses import asdict, dataclass, field

from vcontrol.backend.profiles import CONFIG_DIR
from vcontrol.backend.sysfs import atomic_write_json, clamp

logger = logging.getLogger(__name__)

SETTINGS_FILE = os.path.join(CONFIG_DIR, "settings.json")
THEMES = ("system", "light", "dark")


@dataclass
class LightingState:
    brightness: int = 255
    red: int = 255
    green: int = 255
    blue: int = 255


@dataclass
class AppSettings:
    theme: str = "system"
    lighting: LightingState | None = None
    _path: str = field(default=SETTINGS_FILE, repr=False, compare=False)

    def save(self) -> None:
        data: dict = {"theme": self.theme}
        if self.lighting is not None:
            data["lighting"] = asdict(self.lighting)
        atomic_write_json(self._path, data)


def load_settings(path: str | None = None) -> AppSettings:
    path = path or SETTINGS_FILE
    settings = AppSettings(_path=path)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return settings
    except (OSError, ValueError) as e:
        logger.error(f"Settings load error: {e}")
        return settings

    if not isinstance(data, dict):
        return settings

    theme = data.get("theme")
    if theme in THEMES:
        settings.theme = theme

    lighting = data.get("lighting")
    if isinstance(lighting, dict):
        settings.lighting = LightingState(
            brightness=clamp(lighting.get("brightness"), 0, 255, 255),
            red=clamp(lighting.get("red"), 0, 255, 255),
            green=clamp(lighting.get("green"), 0, 255, 255),
            blue=clamp(lighting.get("blue"), 0, 255, 255),
        )
    return settings

