import logging
import signal

from gi.repository import GLib

from vcontrol.backend.daemon_status import (
    HEARTBEAT_INTERVAL_S,
    clear_heartbeat,
    write_heartbeat,
)
from vcontrol.backend.settings import load_settings
from vcontrol.backend.watchdog import get_watchdog

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] Daemon: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def restore_lighting() -> None:
    lighting = load_settings().lighting
    if lighting is None:
        return
    from vcontrol.backend.rgb import get_controller

    rgb = get_controller()
    if not rgb.supported:
        return
    rgb.set_brightness(lighting.brightness)
    if rgb.has_color:
        rgb.set_color(lighting.red, lighting.green, lighting.blue)
    logger.info("Saved keyboard lighting restored.")


def main():
    logger.info("V-Control Background Service started.")
    loop = GLib.MainLoop()

    def on_signal() -> bool:
        logger.info("Service stopping...")
        loop.quit()
        return GLib.SOURCE_REMOVE

    def on_heartbeat() -> bool:
        write_heartbeat()
        return GLib.SOURCE_CONTINUE

    GLib.unix_signal_add(GLib.PRIORITY_HIGH, signal.SIGTERM, on_signal)
    GLib.unix_signal_add(GLib.PRIORITY_HIGH, signal.SIGINT, on_signal)

    try:
        restore_lighting()
    except Exception:  # noqa: BLE001 - lighting must never block fan control
        logger.exception("Lighting restore failed")

    write_heartbeat()
    GLib.timeout_add_seconds(HEARTBEAT_INTERVAL_S, on_heartbeat)

    watchdog = get_watchdog()
    watchdog.start()
    try:
        loop.run()
    finally:
        watchdog.stop()
        clear_heartbeat()


if __name__ == "__main__":
    main()
