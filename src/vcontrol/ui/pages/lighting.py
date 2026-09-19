import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw

class LightingPage(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        lbl = Gtk.Label(label="RGB Aydınlatma Kontrolü (Yakında Eklenecek)")
        lbl.set_vexpand(True)
        self.append(lbl)
