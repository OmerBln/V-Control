import logging
import os
import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gtk

from vcontrol.backend.settings import load_settings
from vcontrol.ui.util import apply_theme, load_css

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def _register_icon_paths() -> None:
    display = Gdk.Display.get_default()
    if display is None:
        return
    icon_theme = Gtk.IconTheme.get_for_display(display)
    candidates = [
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "icons")),
        os.path.expanduser("~/.local/share/icons"),
        "/usr/local/share/icons",
        "/usr/share/icons",
    ]
    for path in candidates:
        if os.path.isdir(path):
            icon_theme.add_search_path(path)
    Gtk.Window.set_default_icon_name("v-control")


class HPVictusApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="com.vcontrol.app")
        self._window = None

    def do_activate(self):
        _register_icon_paths()
        if self._window is None:
            load_css()
            apply_theme(load_settings().theme)
            from vcontrol.ui.window import MainWindow

            self._window = MainWindow(app=self)
        self._window.present()

    def do_startup(self):
        Adw.Application.do_startup(self)
        logger.info("V-Control starting...")


def main():
    app = HPVictusApp()
    exit_code = app.run(sys.argv)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
