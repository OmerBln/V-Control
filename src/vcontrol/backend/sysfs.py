import glob
import json
import logging
import os
import subprocess

logger = logging.getLogger(__name__)


def clamp(value, lo: int, hi: int, default: int) -> int:
    """Safely convert `value` to int and clamp it within `[lo, hi]`."""
    try:
        return max(lo, min(hi, int(value)))
    except (TypeError, ValueError):
        return default


def read_sysfs(path: str, default: str = "") -> str:
    """Read a sysfs file as stripped text, returning `default` on failure."""
    try:
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    except (OSError, ValueError):
        return default


def read_millideg(path: str) -> int | None:
    """Read a sysfs millidegree temperature file as whole °C, or `None` on failure."""
    try:
        with open(path, encoding="utf-8") as f:
            return int(f.read().strip()) // 1000
    except (OSError, ValueError):
        return None


def write_sysfs(path: str, value: str) -> bool:
    """Write `value` to a sysfs file with a `sudo -n tee` fallback on PermissionError."""
    try:
        with open(path, "w", encoding="utf-8") as f:
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
                timeout=3,
            )
            return True
        except (OSError, subprocess.SubprocessError):
            logger.error(f"Permission denied: {path}")
    # Deliberate catch-all: callers inside watchdog timers must never crash.
    except Exception as e:  # noqa: BLE001
        logger.error(f"Sysfs write error ({path}): {e}")
    return False


def find_hwmon_by_name(name: str, base: str = "/sys/class/hwmon") -> str | None:
    """Return the first hwmon directory under `base` whose `name` matches `name`."""
    for path in sorted(glob.glob(os.path.join(base, "hwmon*"))):
        if read_sysfs(os.path.join(path, "name")) == name:
            return path
    return None


def atomic_write_json(path: str, data: dict, indent: int | None = 2) -> bool:
    """Atomically serialize `data` as JSON to `path` via a temporary file."""
    directory = os.path.dirname(path)
    tmp_path = f"{path}.tmp"
    try:
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)
        os.replace(tmp_path, path)
        return True
    except (OSError, TypeError, ValueError) as e:
        logger.error(f"JSON write error ({path}): {e}")
        return False

