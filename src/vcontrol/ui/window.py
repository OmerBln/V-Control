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

        self.main_stack.add_named(self._build_victus_page(), "victus")
        self.main_stack.add_named(SettingsPanel(), "settings")

        root.append(self._build_sidebar())
        root.append(self.main_stack)

    def _build_sidebar(self) -> Gtk.Widget:
        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        sidebar.add_css_class("sidebar")

        # Logo
        logo_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        logo_box.add_css_class("sidebar-logo")

        title = Gtk.Label(label="V-Control")
        title.add_css_class("sidebar-logo-title")
        title.set_xalign(0)

        sub = Gtk.Label(label="HP Victus Edition")
        sub.add_css_class("sidebar-logo-sub")
        sub.set_xalign(0)

        logo_box.append(title)
        logo_box.append(sub)
        sidebar.append(logo_box)

        # Nav
        nav_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        nav_box.set_margin_top(12)
        nav_box.set_margin_bottom(12)

        self._nav_buttons = {}

        def add_nav(page_id, icon, label):
            btn = Gtk.Button()
            inner = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            inner.set_margin_start(4)
            inner.append(Gtk.Label(label=icon))
            inner.append(Gtk.Label(label=label))
            btn.set_child(inner)
            btn.add_css_class("nav-btn")
            btn.connect("clicked", self._on_nav, page_id)
            self._nav_buttons[page_id] = btn
            nav_box.append(btn)

        add_nav("victus", "💻", "Cihaz Kontrolü")

        sep_lbl = Gtk.Label(label="Sistem")
        sep_lbl.add_css_class("sidebar-category")
        sep_lbl.set_xalign(0)
        sep_lbl.set_margin_top(12)
        sep_lbl.set_margin_start(20)
        sep_lbl.set_margin_bottom(4)
        nav_box.append(sep_lbl)

        add_nav("settings", "⚙️", "Ayarlar")

        sidebar.append(nav_box)

        self._nav_buttons["victus"].add_css_class("active")
        self.main_stack.set_visible_child_name("victus")

        return sidebar

    def _on_nav(self, btn, page_id):
        self.main_stack.set_visible_child_name(page_id)
        for k, b in self._nav_buttons.items():
            b.remove_css_class("active")
            if k == page_id:
                b.add_css_class("active")

    def _build_victus_page(self) -> Gtk.Widget:
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        vbox.add_css_class("victus-page")

        tab_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        tab_bar.add_css_class("top-tab-bar")

        self.victus_stack = Gtk.Stack()
        self.victus_stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.victus_stack.set_vexpand(True)

        self._tab_buttons = {}

        def add_tab(tab_id, label, widget):
            self.victus_stack.add_named(widget, tab_id)
            btn = Gtk.Button(label=label)
            btn.add_css_class("top-tab-btn")
            btn.connect("clicked", self._on_tab, tab_id)
            self._tab_buttons[tab_id] = btn
            tab_bar.append(btn)

        add_tab("performance", "Performans", FanPanel())
        add_tab("vitals", "Sistem İzleme", SystemVitalsPage())
        add_tab("lighting", "Aydınlatma", LightingPage())

        self._tab_buttons["performance"].add_css_class("active")
        self.victus_stack.set_visible_child_name("performance")

        vbox.append(tab_bar)
        vbox.append(self.victus_stack)
        return vbox

    def _on_tab(self, btn, tab_id):
        self.victus_stack.set_visible_child_name(tab_id)
        for k, b in self._tab_buttons.items():
            b.remove_css_class("active")
            if k == tab_id:
                b.add_css_class("active")

    def do_close_request(self) -> bool:
        return False
