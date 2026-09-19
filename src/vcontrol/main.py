

import logging
import os
import sys

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gtk, Gdk, GLib

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

def load_css():
    
    css_path = os.path.join(os.path.dirname(__file__), "ui", "style.css")
    if not os.path.exists(css_path):
        logger.warning(f"CSS dosyası bulunamadı: {css_path}")
        return
    provider = Gtk.CssProvider()
    provider.load_from_path(css_path)
    Gtk.StyleContext.add_provider_for_display(
        Gdk.Display.get_default(),
        provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
    )
    logger.info("CSS yüklendi.")

class HPVictusApp(Gtk.Application):

    def __init__(self):
        super().__init__(application_id="com.vcontrol.app")
        self._window = None

    def do_activate(self):
        if self._window is None:
            load_css()
            from vcontrol.ui.window import MainWindow
            self._window = MainWindow(app=self)
        self._window.present()

    def do_startup(self):
        Gtk.Application.do_startup(self)
        logger.info("V-Control başlatılıyor...")

def main():
    
    app = HPVictusApp()
    exit_code = app.run(sys.argv)
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
