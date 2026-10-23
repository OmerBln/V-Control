import logging
import signal

from gi.repository import GLib

from vcontrol.backend.watchdog import get_watchdog

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] Daemon: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def main():
    logger.info("V-Control Background Service started.")
    loop = GLib.MainLoop()

    def on_signal() -> bool:
        logger.info("Service stopping...")
        loop.quit()
        return GLib.SOURCE_REMOVE

    GLib.unix_signal_add(GLib.PRIORITY_HIGH, signal.SIGTERM, on_signal)
    GLib.unix_signal_add(GLib.PRIORITY_HIGH, signal.SIGINT, on_signal)

    watchdog = get_watchdog()
    watchdog.start()
    try:
        loop.run()
    finally:
        watchdog.stop()


if __name__ == "__main__":
    main()
