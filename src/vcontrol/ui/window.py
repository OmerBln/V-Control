import logging

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

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

    def _build_ui(self) -> None:
        self.split_view = Adw.NavigationSplitView()
        self.split_view.set_min_sidebar_width(210)
        self.split_view.set_max_sidebar_width(250)

        sidebar_page = Adw.NavigationPage.new(self._build_sidebar(), "V-Control")
        self.content_page = Adw.NavigationPage.new(self._build_content_area(), "Cihaz Kontrolü")

        self.split_view.set_sidebar(sidebar_page)
        self.split_view.set_content(self.content_page)
        self.set_content(self.split_view)

        # Collapse sidebar automatically on narrow windows
        bp = Adw.Breakpoint.new(Adw.BreakpointCondition.parse("max-width: 760sp"))
        bp.add_setter(self.split_view, "collapsed", True)
        self.add_breakpoint(bp)

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

        self.victus_stack = Adw.ViewStack()
        self.victus_stack.add_titled_with_icon(
            FanPanel(), "performance", "Performans", "speedometer-symbolic"
        )
        self.victus_stack.add_titled_with_icon(
            SystemVitalsPage(), "vitals", "Sistem İzleme", "utilities-system-monitor-symbolic"
        )
        self.victus_stack.add_titled_with_icon(
            LightingPage(), "lighting", "Aydınlatma", "display-brightness-symbolic"
        )

        self.view_switcher = Adw.ViewSwitcher()
        self.view_switcher.set_stack(self.victus_stack)
        self.view_switcher.set_policy(Adw.ViewSwitcherPolicy.WIDE)

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

        self.nav_list.select_row(self._rows["victus"])
        return toolbar_view

    def _on_nav_row_selected(self, _listbox: Gtk.ListBox, row: Gtk.ListBoxRow | None) -> None:
        if row is None:
            return
        page_id = getattr(row, "page_id", "victus")
        self.main_stack.set_visible_child_name(page_id)
        if page_id == "victus":
            self.content_header.set_title_widget(self.view_switcher)
            self.content_page.set_title("Cihaz Kontrolü")
        else:
            self.content_header.set_title_widget(self.settings_title)
            self.content_page.set_title("Ayarlar")
        self.split_view.set_show_content(True)

    def do_close_request(self) -> bool:
        return False
