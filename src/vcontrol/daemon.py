import time
import logging
import signal
import sys
from vcontrol.backend.watchdog import get_watchdog

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] Daemon: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

def handle_sigterm(signum, frame):
    logger.info("Servis durduruluyor...")
    get_watchdog().stop()
    sys.exit(0)

def main():
    logger.info("V-Control Arka Plan Servisi (Daemon) Başlatıldı.")
    signal.signal(signal.SIGTERM, handle_sigterm)
    signal.signal(signal.SIGINT, handle_sigterm)
    
    watchdog = get_watchdog()
    watchdog.start()
    
    # Ana thread'i sonsuz döngüde tut (GLib loop yerine basit sleep kullanıyoruz çünkü GLib gerekmeyebilir)
    # Watchdog kendi içinde timer thread'i başlatıyor, bu yüzden ana thread'i uyutuyoruz
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        handle_sigterm(None, None)

if __name__ == "__main__":
    main()
