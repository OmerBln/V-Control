import json
import logging
import os
import shutil
import subprocess
import time

from vcontrol.backend.profiles import CONFIG_DIR

logger = logging.getLogger(__name__)

SERVICE_NAME = "v-control-daemon.service"
HEARTBEAT_INTERVAL_S = 2
HEARTBEAT_MAX_AGE_S = 3 * HEARTBEAT_INTERVAL_S


def heartbeat_path() -> str:
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
    base = runtime_dir if runtime_dir and os.path.isdir(runtime_dir) else CONFIG_DIR
    return os.path.join(base, "v-control-daemon.json")


def write_heartbeat(path: str | None = None) -> None:
    path = path or heartbeat_path()
    tmp_path = f"{path}.tmp"
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump({"pid": os.getpid(), "time": time.time()}, f)
        os.replace(tmp_path, path)
    except OSError as e:
        logger.debug(f"Heartbeat write failed: {e}")


def clear_heartbeat(path: str | None = None) -> None:
    try:
        os.remove(path or heartbeat_path())
    except OSError:
        pass


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def is_daemon_alive(path: str | None = None, now: float | None = None) -> bool:
    try:
        with open(path or heartbeat_path(), encoding="utf-8") as f:
            data = json.load(f)
        pid = int(data["pid"])
        stamp = float(data["time"])
    except (OSError, ValueError, KeyError, TypeError):
        return False
    now = time.time() if now is None else now
    return (now - stamp) <= HEARTBEAT_MAX_AGE_S and _pid_alive(pid)


def _systemctl(*args: str) -> subprocess.CompletedProcess | None:
    if shutil.which("systemctl") is None:
        return None
    try:
        return subprocess.run(
            ["systemctl", "--user", *args],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError) as e:
        logger.error(f"systemctl {' '.join(args)} failed: {e}")
        return None


def service_installed() -> bool:
    result = _systemctl("cat", SERVICE_NAME)
    return result is not None and result.returncode == 0


def service_enabled() -> bool:
    result = _systemctl("is-enabled", SERVICE_NAME)
    return result is not None and result.stdout.strip() == "enabled"


def start_service() -> bool:
    result = _systemctl("start", SERVICE_NAME)
    return result is not None and result.returncode == 0


def stop_service() -> bool:
    result = _systemctl("stop", SERVICE_NAME)
    return result is not None and result.returncode == 0


def set_service_enabled(enabled: bool) -> bool:
    result = _systemctl("enable" if enabled else "disable", SERVICE_NAME)
    return result is not None and result.returncode == 0

