import logging
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, GLib, Adw

logger = logging.getLogger(__name__)

from vcontrol.ui.pages.system_vitals import SystemVitalsPage
from vcontrol.ui.pages.performance import FanPanel
from vcontrol.ui.pages.lighting import LightingPage
from vcontrol.ui.settings_panel import SettingsPanel


class MainWindow(Gtk.ApplicationWindow):
    def __init__(self, app: Gtk.Application):
        super().__init__(application=app)
        self.add_css_class("main-window")
        self.set_title("V-Control")
        self.set_default_size(1050, 700)

        self._build_ui()

    def _build_ui(self):
        root = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.set_child(root)

        self.main_stack = Gtk.Stack()
        self.main_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.main_stack.set_hexpand(True)
        self.main_stack.set_vexpand(True)

        self.main_stack.add_named(self._build_home_page(), "home")
        self.main_stack.add_named(self._build_victus_page(), "victus")
        self.main_stack.add_named(SettingsPanel(), "settings")

        root.append(self._build_sidebar())
        root.append(self.main_stack)

    def _build_sidebar(self) -> Gtk.Widget:
        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        sidebar.add_css_class("sidebar")

        logo_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        logo_box.add_css_class("sidebar-logo")
        img = Gtk.Image.new_from_icon_name("computer-symbolic")
        img.set_pixel_size(24)
        lbl = Gtk.Label(label="OMEN Gaming Hub\n(Victus Edition)")
        lbl.add_css_class("sidebar-logo-text")
        logo_box.append(img)
        logo_box.append(lbl)
        sidebar.append(logo_box)

        self._nav_buttons = {}

        def add_item(id_name, icon, label, css_class="nav-btn"):
            btn = Gtk.Button()
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            box.append(Gtk.Label(label=icon))
            box.append(Gtk.Label(label=label))
            btn.set_child(box)
            btn.add_css_class(css_class)
            btn.connect("clicked", self._on_sidebar_nav, id_name)
            self._nav_buttons[id_name] = btn
            sidebar.append(btn)

        add_item("home", "🏠", "HOME")

        cat_lbl = Gtk.Label(label="VICTUS Laptop")
        cat_lbl.add_css_class("sidebar-category")
        cat_lbl.set_xalign(0)
        cat_lbl.set_margin_top(16)
        cat_lbl.set_margin_start(16)
        sidebar.append(cat_lbl)

        add_item("victus", "💻", "Victus Cihazım")
        add_item("settings", "⚙️", "Ayarlar")

        self._nav_buttons["victus"].add_css_class("active")
        self.main_stack.set_visible_child_name("victus")

        return sidebar

    def _on_sidebar_nav(self, btn, page_name):
        self.main_stack.set_visible_child_name(page_name)
        for k, b in self._nav_buttons.items():
            b.remove_css_class("active")
            if k == page_name:
                b.add_css_class("active")

    def _build_home_page(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        lbl = Gtk.Label(label="Home Page - Boş")
        lbl.set_vexpand(True)
        box.append(lbl)
        return box

    def _build_victus_page(self) -> Gtk.Widget:
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        vbox.add_css_class("victus-page")

        tab_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        tab_bar.add_css_class("top-tab-bar")

        self.victus_stack = Gtk.Stack()
        self.victus_stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.victus_stack.set_vexpand(True)

        self._tab_buttons = {}

        def add_tab(id_name, label, widget):
            self.victus_stack.add_named(widget, id_name)
            btn = Gtk.Button(label=label)
            btn.add_css_class("top-tab-btn")
            btn.connect("clicked", self._on_top_tab_nav, id_name)
            self._tab_buttons[id_name] = btn
            tab_bar.append(btn)

        add_tab("vitals", "System Vitals", SystemVitalsPage())
        add_tab("lighting", "Lighting", LightingPage())
        add_tab("performance", "Performance Control", FanPanel())

        self._tab_buttons["performance"].add_css_class("active")
        self.victus_stack.set_visible_child_name("performance")

        vbox.append(tab_bar)
        vbox.append(self.victus_stack)

        return vbox

    def _on_top_tab_nav(self, btn, page_name):
        self.victus_stack.set_visible_child_name(page_name)
        for k, b in self._tab_buttons.items():
            b.remove_css_class("active")
            if k == page_name:
                b.add_css_class("active")

    def do_close_request(self) -> bool:
        # Return False to allow the window to close normally
        return False
