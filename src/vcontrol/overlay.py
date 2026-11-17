import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)


def main():
    from vcontrol.ui.quick_overlay import main as overlay_main

    overlay_main()


if __name__ == "__main__":
    main()
