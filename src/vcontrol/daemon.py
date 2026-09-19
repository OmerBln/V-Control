import time
import logging
import signal
import sys
from gi.repository import GLib
from vcontrol.backend.watchdog import get_watchdog

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] Daemon: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

loop = GLib.MainLoop()

def handle_sigterm(signum, frame):
    logger.info("Servis durduruluyor...")
    get_watchdog().stop()
    loop.quit()
    sys.exit(0)

def main():
    logger.info("V-Control Arka Plan Servisi (Daemon) Başlatıldı.")
    signal.signal(signal.SIGTERM, handle_sigterm)
    signal.signal(signal.SIGINT, handle_sigterm)
    
    watchdog = get_watchdog()
    watchdog.start()
    
    try:
        loop.run()
    except KeyboardInterrupt:
        handle_sigterm(None, None)

if __name__ == "__main__":
    main()
