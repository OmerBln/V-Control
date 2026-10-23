import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk

from vcontrol.ui.rgb_panel import RGBPanel


class LightingPage(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.panel = RGBPanel()
        self.append(self.panel)
