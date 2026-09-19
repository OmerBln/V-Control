

import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

def main():
    from vcontrol.ui.quick_overlay import OverlayApp
    app = OverlayApp()
    exit_code = app.run(sys.argv)
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
