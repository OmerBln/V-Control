import json
import logging
import os
from dataclasses import asdict, dataclass, field

from vcontrol.backend.profiles import CONFIG_DIR

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
        data = {"theme": self.theme}
        if self.lighting is not None:
            data["lighting"] = asdict(self.lighting)
        directory = os.path.dirname(self._path)
        tmp_path = f"{self._path}.tmp"
        try:
            os.makedirs(directory, exist_ok=True)
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp_path, self._path)
        except OSError as e:
            logger.error(f"Settings save error: {e}")


def _clamp_byte(value, default: int) -> int:
    try:
        return max(0, min(255, int(value)))
    except (TypeError, ValueError):
        return default


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
            brightness=_clamp_byte(lighting.get("brightness"), 255),
            red=_clamp_byte(lighting.get("red"), 255),
            green=_clamp_byte(lighting.get("green"), 255),
            blue=_clamp_byte(lighting.get("blue"), 255),
        )
    return settings

