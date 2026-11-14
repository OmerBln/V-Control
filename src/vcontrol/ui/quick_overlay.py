import logging
import sys

import gi
import psutil

gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, GLib, Gtk

from vcontrol.backend.fan import get_controller
from vcontrol.backend.profiles import get_manager
from vcontrol.ui.util import Debouncer, load_css, set_temp_class

logger = logging.getLogger(__name__)

UPDATE_INTERVAL_MS = 1000


class QuickOverlay(Gtk.Window):
    def __init__(self, app):
        super().__init__(application=app)

        self.set_title("V-Control Overlay")
        self.set_decorated(False)
        self.set_resizable(False)
        self.add_css_class("omen-overlay-window")
        self.set_default_size(520, 300)

        self._fan = get_controller()
        self._profiles = get_manager()
        self._update_timer: int | None = None
        self._updating = False
        self._last_prof_state: tuple[str, bool, int] | None = None
        self._slider_debouncer = Debouncer(150, self._commit_slider)

        self._build_ui()

        ev_ctrl = Gtk.EventControllerKey.new()
        ev_ctrl.connect("key-pressed", self._on_key_pressed)
        self.add_controller(ev_ctrl)

    def _build_ui(self) -> None:
        main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        main_box.set_margin_top(20)
        main_box.set_margin_bottom(20)
        main_box.set_margin_start(20)
        main_box.set_margin_end(20)

        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        sidebar.add_css_class("omen-sidebar")
        sidebar.set_valign(Gtk.Align.START)

        self.btn_vitals = Gtk.ToggleButton(label="📊")
        self.btn_vitals.add_css_class("omen-sidebar-btn")
        self.btn_vitals.set_tooltip_text("Sistem Durumu")

        self.btn_fan = Gtk.ToggleButton(label="🌪️")
        self.btn_fan.add_css_class("omen-sidebar-btn")
        self.btn_fan.set_tooltip_text("Fan Kontrolü")

        self.btn_fan.set_group(self.btn_vitals)
        self.btn_vitals.connect("toggled", self._on_tab_changed, "vitals")
        self.btn_fan.connect("toggled", self._on_tab_changed, "fan")

        btn_close = Gtk.Button(label="✕")
        btn_close.add_css_class("omen-sidebar-btn")
        btn_close.set_tooltip_text("Kapat (Esc)")
        btn_close.set_vexpand(True)
        btn_close.set_valign(Gtk.Align.END)
        btn_close.connect("clicked", lambda _x: self.close())

        sidebar.append(self.btn_fan)
        sidebar.append(self.btn_vitals)
        sidebar.append(btn_close)

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)

        self.vitals_panel = self._build_vitals_panel()
        self.fan_panel = self._build_fan_panel()

        self.stack.add_named(self.fan_panel, "fan")
        self.stack.add_named(self.vitals_panel, "vitals")

        self.revealer = Gtk.Revealer()
        self.revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_RIGHT)
        self.revealer.set_child(self.stack)
        self.revealer.set_reveal_child(True)

        main_box.append(sidebar)
        main_box.append(self.revealer)
        self.set_child(main_box)

        self.btn_fan.set_active(True)

    def _build_vitals_panel(self) -> Gtk.Widget:
        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        panel.add_css_class("omen-popout")
        panel.set_valign(Gtk.Align.START)

        grid = Gtk.Grid(column_spacing=12, row_spacing=12)
        grid.set_column_homogeneous(True)

        self.lbl_cpu = self._create_card("CPU SICAKLIĞI", "0", "°C")
        self.lbl_gpu = self._create_card("GPU SICAKLIĞI", "0", "°C")
        self.lbl_ram = self._create_card("BELLEK (RAM)", "0", "%")
        self.lbl_fan1 = self._create_card("SOL FAN", "0", "RPM")
        self.lbl_fan2 = self._create_card("SAĞ FAN", "0", "RPM")

        grid.attach(self.lbl_cpu["box"], 0, 0, 1, 1)
        grid.attach(self.lbl_gpu["box"], 1, 0, 1, 1)
        grid.attach(self.lbl_ram["box"], 0, 1, 1, 1)
        grid.attach(self.lbl_fan1["box"], 1, 1, 1, 1)
        grid.attach(self.lbl_fan2["box"], 0, 2, 2, 1)

        panel.append(grid)
        return panel

    def _build_fan_panel(self) -> Gtk.Widget:
        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        panel.add_css_class("omen-popout")
        panel.set_valign(Gtk.Align.START)

        mode_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.mode_buttons: dict[str, Gtk.Button] = {}

        for p in self._profiles.all_profiles():
            label_text = p.short_name or p.display_name
            btn = Gtk.Button(label=f"{p.icon} {label_text}")
            btn.add_css_class("omen-mode-btn")
            btn.connect("clicked", self._on_mode_clicked, p.name)
            self.mode_buttons[p.name] = btn
            mode_box.append(btn)

        panel.append(mode_box)

        manual_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        manual_box.set_margin_top(8)

        lbl_auto = Gtk.Label(label="OTOMATİK")
        lbl_auto.add_css_class("omen-card-title")

        self.manual_switch = Gtk.Switch(valign=Gtk.Align.CENTER)
        self.manual_switch.connect("state-set", self._on_manual_toggled)

        lbl_man = Gtk.Label(label="MANUEL")
        lbl_man.add_css_class("omen-card-title")

        self.lbl_speed_pct = Gtk.Label(label="%50", hexpand=True, xalign=1)
        self.lbl_speed_pct.add_css_class("omen-card-title")

        manual_box.append(lbl_auto)
        manual_box.append(self.manual_switch)
        manual_box.append(lbl_man)
        manual_box.append(self.lbl_speed_pct)
        panel.append(manual_box)

        self.slider = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 30, 100, 1)
        self.slider.add_css_class("omen-slider")
        self.slider.connect("value-changed", self._on_slider_changed)
        panel.append(self.slider)

        self._refresh_fan_ui()
        return panel

    def _create_card(self, title: str, val: str, unit: str) -> dict:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.add_css_class("omen-card")

        t = Gtk.Label(label=title, xalign=0)
        t.add_css_class("omen-card-title")

        v_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        v = Gtk.Label(label=val)
        v.add_css_class("omen-card-value")
        u = Gtk.Label(label=unit, yalign=0.8)
        u.add_css_class("omen-card-unit")

        v_box.append(v)
        v_box.append(u)
        box.append(t)
        box.append(v_box)
        return {"box": box, "val": v}

    def _on_tab_changed(self, btn: Gtk.ToggleButton, name: str) -> None:
        if btn.get_active():
            self.revealer.set_reveal_child(True)
            self.stack.set_visible_child_name(name)

    def _on_mode_clicked(self, _btn: Gtk.Button, name: str) -> None:
        self._slider_debouncer.flush()
        self._profiles.set_active(name)
        self._refresh_fan_ui()

    def _on_manual_toggled(self, _switch: Gtk.Switch, state: bool) -> bool:
        if self._updating:
            return False
        self.slider.set_sensitive(state)
        p = self._profiles.active_profile
        self._profiles.update_manual(p.name, state, int(self.slider.get_value()))
        return False

    def _on_slider_changed(self, slider: Gtk.Scale) -> None:
        if self._updating:
            return
        val = int(slider.get_value())
        self.lbl_speed_pct.set_label(f"%{val}")
        self._slider_debouncer(self._profiles.active_profile.name, self.manual_switch.get_active(), val)

    def _commit_slider(self, profile_name: str, is_manual: bool, speed: int) -> None:
        self._profiles.update_manual(profile_name, is_manual, speed)

    def _refresh_fan_ui(self) -> None:
        self._updating = True
        p = self._profiles.active_profile
        for name, btn in self.mode_buttons.items():
            if name == p.name:
                btn.add_css_class("active-mode")
            else:
                btn.remove_css_class("active-mode")

        self.slider.set_value(p.manual_speed)
        self.lbl_speed_pct.set_label(f"%{int(p.manual_speed)}")
        self.manual_switch.set_active(p.is_manual)
        self.slider.set_sensitive(p.is_manual)
        self._updating = False

    def _on_key_pressed(self, _ctrl, keyval, _keycode, _state) -> bool:
        if keyval == Gdk.KEY_Escape:
            self.close()
            return True
        return False

    def start_updates(self) -> None:
        self._update_now()
        self._update_timer = GLib.timeout_add(UPDATE_INTERVAL_MS, self._update_now)

    def stop_updates(self) -> None:
        self._slider_debouncer.flush()
        if self._update_timer:
            GLib.source_remove(self._update_timer)
            self._update_timer = None

    def _update_now(self) -> bool:
        try:
            if not self.get_root():
                return False

            p = self._profiles.active_profile
            state = (p.name, p.is_manual, p.manual_speed)
            if not self._slider_debouncer.pending and self._last_prof_state != state:
                self._last_prof_state = state
                self._refresh_fan_ui()

            temps = self._fan.get_temperatures()
            rpms = self._fan.get_rpms()
            ram_pct = psutil.virtual_memory().percent
            cpu = int(temps.get("cpu", 0))
            gpu = int(temps.get("gpu", 0))

            self.lbl_cpu["val"].set_label(str(cpu))
            self.lbl_gpu["val"].set_label(str(gpu))
            self.lbl_ram["val"].set_label(f"{ram_pct:.1f}")
            self.lbl_fan1["val"].set_label(str(rpms.get("fan1", 0)))
            self.lbl_fan2["val"].set_label(str(rpms.get("fan2", 0)))

            set_temp_class(self.lbl_cpu["val"], cpu)
            set_temp_class(self.lbl_gpu["val"], gpu)
        except Exception as e:  # noqa: BLE001
            logger.error(f"Overlay güncelleme hatası: {e}")
        return True

    def do_close_request(self) -> bool:
        self.stop_updates()
        app = self.get_application()
        if app:
            app.quit()
        return False


class OverlayApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.vcontrol.overlay")
        self._window: QuickOverlay | None = None

    def do_activate(self):
        if self._window is not None and self._window.is_visible():
            self._window.close()
            self.quit()
            return

        load_css()
        self._window = QuickOverlay(app=self)
        self._window.present()
        self._window.start_updates()


def main():
    app = OverlayApp()
    app.run(sys.argv)


if __name__ == "__main__":
    main()
