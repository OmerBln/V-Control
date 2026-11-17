import logging

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gtk

from vcontrol.ui.pages.lighting import LightingPage
from vcontrol.ui.pages.performance import FanPanel
from vcontrol.ui.pages.system_vitals import SystemVitalsPage
from vcontrol.ui.settings_panel import SettingsPanel

logger = logging.getLogger(__name__)


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application):
        super().__init__(application=app)
        self.add_css_class("main-window")
        self.set_title("V-Control")
        self.set_default_size(1060, 720)
        self.set_size_request(360, 480)
        self._build_ui()

        key_ctrl = Gtk.EventControllerKey.new()
        key_ctrl.connect("key-pressed", self._on_key_pressed)
        self.add_controller(key_ctrl)

    def _build_ui(self) -> None:
        self.split_view = Adw.NavigationSplitView()
        self.split_view.set_min_sidebar_width(210)
        self.split_view.set_max_sidebar_width(250)

        sidebar_page = Adw.NavigationPage.new(self._build_sidebar(), "V-Control")
        self.content_page = Adw.NavigationPage.new(self._build_content_area(), "Cihaz Kontrolü")

        self.split_view.set_sidebar(sidebar_page)
        self.split_view.set_content(self.content_page)
        self.split_view.connect("notify::collapsed", self._on_collapsed_changed)
        self.set_content(self.split_view)

        # Collapse sidebar automatically on narrow windows
        bp = Adw.Breakpoint.new(Adw.BreakpointCondition.parse("max-width: 760sp"))
        bp.add_setter(self.split_view, "collapsed", True)
        self.add_breakpoint(bp)

        self.nav_list.select_row(self._rows["victus"])
        self._sync_header_and_bar()

    def _build_sidebar(self) -> Gtk.Widget:
        toolbar_view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.set_show_end_title_buttons(False)

        brand_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        brand_title = Gtk.Label(label="V-Control", xalign=0)
        brand_title.add_css_class("sidebar-logo-title")
        brand_sub = Gtk.Label(label="HP VICTUS EDITION", xalign=0)
        brand_sub.add_css_class("sidebar-logo-sub")
        brand_box.append(brand_title)
        brand_box.append(brand_sub)
        header.set_title_widget(brand_box)
        toolbar_view.add_top_bar(header)

        self.nav_list = Gtk.ListBox()
        self.nav_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.nav_list.add_css_class("navigation-sidebar")
        self.nav_list.connect("row-selected", self._on_nav_row_selected)

        self._rows: dict[str, Gtk.ListBoxRow] = {}
        self._add_nav_row("victus", "💻", "Cihaz Kontrolü")
        self._add_nav_row("settings", "⚙️", "Ayarlar")

        toolbar_view.set_content(self.nav_list)
        return toolbar_view

    def _add_nav_row(self, page_id: str, icon: str, title: str) -> None:
        row = Gtk.ListBoxRow()
        row.page_id = page_id  # type: ignore[attr-defined]
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(8)
        box.set_margin_end(8)

        icon_lbl = Gtk.Label(label=icon)
        title_lbl = Gtk.Label(label=title, xalign=0, hexpand=True)
        box.append(icon_lbl)
        box.append(title_lbl)
        row.set_child(box)
        self.nav_list.append(row)
        self._rows[page_id] = row

    def _build_content_area(self) -> Gtk.Widget:
        toolbar_view = Adw.ToolbarView()
        self.content_header = Adw.HeaderBar()

        self.fan_panel = FanPanel()
        self.vitals_page = SystemVitalsPage()
        self.lighting_page = LightingPage()

        self.victus_stack = Adw.ViewStack()
        self.victus_stack.add_titled_with_icon(
            self.fan_panel, "performance", "Performans", "speedometer-symbolic"
        )
        self.victus_stack.add_titled_with_icon(
            self.vitals_page, "vitals", "Sistem İzleme", "utilities-system-monitor-symbolic"
        )
        self.victus_stack.add_titled_with_icon(
            self.lighting_page, "lighting", "Aydınlatma", "display-brightness-symbolic"
        )

        self.view_switcher = Adw.ViewSwitcher()
        self.view_switcher.set_stack(self.victus_stack)
        self.view_switcher.set_policy(Adw.ViewSwitcherPolicy.WIDE)

        self.victus_title = Adw.WindowTitle(title="Cihaz Kontrolü", subtitle="HP Victus 16")
        self.settings_title = Adw.WindowTitle(title="Ayarlar", subtitle="Görünüm ve servis yönetimi")
        self.content_header.set_title_widget(self.view_switcher)

        self.switcher_bar = Adw.ViewSwitcherBar()
        self.switcher_bar.set_stack(self.victus_stack)

        self.main_stack = Gtk.Stack()
        self.main_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.main_stack.set_hexpand(True)
        self.main_stack.set_vexpand(True)
        self.main_stack.add_named(self.victus_stack, "victus")
        self.main_stack.add_named(SettingsPanel(parent_window=self), "settings")

        toolbar_view.add_top_bar(self.content_header)
        toolbar_view.set_content(self.main_stack)
        toolbar_view.add_bottom_bar(self.switcher_bar)
        return toolbar_view

    def _sync_header_and_bar(self) -> None:
        page_id = self.main_stack.get_visible_child_name() or "victus"
        collapsed = self.split_view.get_collapsed()
        if page_id == "victus":
            self.content_page.set_title("Cihaz Kontrolü")
            self.content_header.set_title_widget(
                self.victus_title if collapsed else self.view_switcher
            )
            self.switcher_bar.set_reveal(collapsed)
        else:
            self.content_page.set_title("Ayarlar")
            self.content_header.set_title_widget(self.settings_title)
            self.switcher_bar.set_reveal(False)

    def _on_collapsed_changed(self, _split_view: Adw.NavigationSplitView, _pspec) -> None:
        self._sync_header_and_bar()

    def _on_nav_row_selected(self, _listbox: Gtk.ListBox, row: Gtk.ListBoxRow | None) -> None:
        if row is None:
            return
        page_id = getattr(row, "page_id", "victus")
        self.main_stack.set_visible_child_name(page_id)
        self._sync_header_and_bar()
        self.split_view.set_show_content(True)

    def _switch_victus_tab(self, tab_name: str) -> None:
        self.nav_list.select_row(self._rows["victus"])
        self.victus_stack.set_visible_child_name(tab_name)

    def _on_key_pressed(self, _ctrl, keyval, _keycode, state) -> bool:
        if not (state & Gdk.ModifierType.CONTROL_MASK):
            return False
        if keyval in (Gdk.KEY_1, Gdk.KEY_KP_1):
            self._switch_victus_tab("performance")
            return True
        if keyval in (Gdk.KEY_2, Gdk.KEY_KP_2):
            self._switch_victus_tab("vitals")
            return True
        if keyval in (Gdk.KEY_3, Gdk.KEY_KP_3):
            self._switch_victus_tab("lighting")
            return True
        if keyval == Gdk.KEY_comma:
            self.nav_list.select_row(self._rows["settings"])
            return True
        if keyval in (Gdk.KEY_q, Gdk.KEY_Q, Gdk.KEY_w, Gdk.KEY_W):
            self.close()
            return True
        return False

    def do_close_request(self) -> bool:
        self.fan_panel.flush_pending()
        self.lighting_page.panel.flush_pending()
        return False
