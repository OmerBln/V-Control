import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

from vcontrol.backend.profiles import get_manager
from vcontrol.backend.fan import get_controller


def _temp_class(temp: int) -> str:
    if temp >= 85:
        return "temp-critical"
    if temp >= 70:
        return "temp-hot"
    if temp >= 55:
        return "temp-warm"
    return "temp-cool"


class FanPanel(Gtk.ScrolledWindow):
    def __init__(self):
        super().__init__()
        self.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.profiles = get_manager()
        self.fan_ctrl = get_controller()
        self._current_profile = self.profiles.active_profile.name
        self._last_cpu = 0
        self._last_gpu = 0
        self._updating = False

        clamp = Adw.Clamp()
        clamp.set_maximum_size(640)
        clamp.set_tightening_threshold(400)
        clamp.set_margin_top(28)
        clamp.set_margin_bottom(28)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=28)

        # ── Dashboard ──────────────────────────────────────────
        dashboard_grid = Gtk.Grid(column_spacing=14, row_spacing=14)
        dashboard_grid.set_column_homogeneous(True)

        self.lbl_cpu  = self._make_metric_card("🌡", "CPU", "0", "°C", "temp-cool")
        self.lbl_gpu  = self._make_metric_card("⚡", "GPU", "0", "°C", "val-gpu")
        self.lbl_fan1 = self._make_metric_card("🌀", "Fan 1", "0", "RPM", "val-rpm")
        self.lbl_fan2 = self._make_metric_card("🌀", "Fan 2", "0", "RPM", "val-rpm")

        dashboard_grid.attach(self.lbl_cpu["box"],  0, 0, 1, 1)
        dashboard_grid.attach(self.lbl_gpu["box"],  1, 0, 1, 1)
        dashboard_grid.attach(self.lbl_fan1["box"], 0, 1, 1, 1)
        dashboard_grid.attach(self.lbl_fan2["box"], 1, 1, 1, 1)
        root.append(dashboard_grid)

        # ── Profile selector ───────────────────────────────────
        sec_lbl = Gtk.Label(label="Termal Mod")
        sec_lbl.set_xalign(0)
        sec_lbl.add_css_class("heading")
        root.append(sec_lbl)

        profile_grid = Gtk.Grid(column_spacing=12, row_spacing=12)
        profile_grid.set_column_homogeneous(True)

        self.buttons = {}
        for col, p in enumerate(self.profiles.all_profiles()):
            card = self._make_profile_card(p)
            profile_grid.attach(card, col, 0, 1, 1)
        root.append(profile_grid)

        # ── Manual control ─────────────────────────────────────
        manual_group = Adw.PreferencesGroup(title="Manuel Kontrol")

        manual_row = Adw.ActionRow(
            title="Özel Fan Hızı",
            subtitle="Otomatik eğriyi devre dışı bırakır",
        )
        self.manual_switch = Gtk.Switch(valign=Gtk.Align.CENTER)
        self.manual_switch.connect("state-set", self._on_switch_toggled)
        manual_row.add_suffix(self.manual_switch)
        manual_group.add(manual_row)

        # Speed readout row
        readout_row = Adw.ActionRow(title="Hedef Hız")
        self._speed_val = Gtk.Label(label="50")
        self._speed_val.add_css_class("speed-readout")
        self._speed_unit = Gtk.Label(label="%")
        self._speed_unit.add_css_class("speed-readout-unit")
        self._speed_unit.set_valign(Gtk.Align.END)
        self._speed_unit.set_margin_bottom(6)
        speed_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        speed_box.set_valign(Gtk.Align.CENTER)
        speed_box.append(self._speed_val)
        speed_box.append(self._speed_unit)
        readout_row.add_suffix(speed_box)
        manual_group.add(readout_row)

        self.slider = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 20, 100, 1)
        self.slider.add_css_class("premium-slider")
        self.slider.set_hexpand(True)
        self.slider.set_margin_top(8)
        self.slider.set_margin_bottom(16)
        self.slider.set_margin_start(24)
        self.slider.set_margin_end(24)
        self.slider.add_mark(20,  Gtk.PositionType.BOTTOM, "20%")
        self.slider.add_mark(50,  Gtk.PositionType.BOTTOM, "50%")
        self.slider.add_mark(100, Gtk.PositionType.BOTTOM, "100%")
        self.slider.connect("value-changed", self._on_slider_changed)

        slider_row = Adw.PreferencesRow()
        slider_row.set_child(self.slider)
        manual_group.add(slider_row)
        root.append(manual_group)

        clamp.set_child(root)
        self.set_child(clamp)

        self._refresh_ui()
        GLib.timeout_add(1000, self._update_dashboard)

    # ── Builders ───────────────────────────────────────────────

    def _make_metric_card(self, icon: str, title: str, val: str, unit: str, color_class: str) -> dict:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.add_css_class("dashboard-card")

        icon_lbl = Gtk.Label(label=icon)
        icon_lbl.add_css_class("dashboard-card-icon")
        icon_lbl.set_xalign(0)

        title_lbl = Gtk.Label(label=title)
        title_lbl.add_css_class("dashboard-title")
        title_lbl.set_xalign(0)

        val_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        val_lbl = Gtk.Label(label=val)
        val_lbl.add_css_class("dashboard-value")
        val_lbl.add_css_class(color_class)
        unit_lbl = Gtk.Label(label=unit)
        unit_lbl.add_css_class("dashboard-unit")
        unit_lbl.set_valign(Gtk.Align.END)
        unit_lbl.set_margin_bottom(4)

        val_box.append(val_lbl)
        val_box.append(unit_lbl)

        box.append(icon_lbl)
        box.append(title_lbl)
        box.append(val_box)

        return {"box": box, "val": val_lbl, "color_class": color_class}

    def _make_profile_card(self, profile) -> Gtk.Button:
        card = Gtk.Button()
        card.add_css_class("profile-card")
        if profile.name == self._current_profile:
            card.add_css_class("active-profile")

        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        inner.set_halign(Gtk.Align.CENTER)

        icon = Gtk.Label(label=profile.icon)
        icon.add_css_class("profile-icon")

        title = Gtk.Label(label=profile.display_name)
        title.add_css_class("profile-title")

        desc_text = "Özel Hız" if profile.is_manual else "Otomatik Eğri"
        desc = Gtk.Label(label=desc_text)
        desc.add_css_class("profile-desc")

        inner.append(icon)
        inner.append(title)
        inner.append(desc)
        card.set_child(inner)
        card.connect("clicked", self._on_profile_clicked, profile.name)
        self.buttons[profile.name] = card
        return card

    # ── Callbacks ──────────────────────────────────────────────

    def _update_dashboard(self) -> bool:
        rpms = self.fan_ctrl.get_rpms()
        self.lbl_fan1["val"].set_label(str(rpms.get("fan1", 0)))
        self.lbl_fan2["val"].set_label(str(rpms.get("fan2", 0)))

        temps = self.fan_ctrl.get_temperatures()
        cpu = temps.get("cpu", 0)
        gpu = temps.get("gpu", 0)

        self.lbl_cpu["val"].set_label(str(cpu))
        self.lbl_gpu["val"].set_label(str(gpu))

        # Update CPU colour based on temperature
        if cpu != self._last_cpu:
            for cls in ("temp-cool", "temp-warm", "temp-hot", "temp-critical"):
                self.lbl_cpu["val"].remove_css_class(cls)
            self.lbl_cpu["val"].add_css_class(_temp_class(cpu))
            self._last_cpu = cpu

        if gpu != self._last_gpu:
            for cls in ("temp-cool", "temp-warm", "temp-hot", "temp-critical", "val-gpu"):
                self.lbl_gpu["val"].remove_css_class(cls)
            self.lbl_gpu["val"].add_css_class(_temp_class(gpu))
            self._last_gpu = gpu

        return True

    def _on_profile_clicked(self, btn, name):
        self.profiles.set_active(name)
        self._current_profile = name
        for n, b in self.buttons.items():
            b.remove_css_class("active-profile")
            if n == name:
                b.add_css_class("active-profile")
        self._refresh_ui()

    def _refresh_ui(self):
        self._updating = True
        p = self.profiles.active_profile
        self.slider.set_value(p.manual_speed)
        self.manual_switch.set_active(p.is_manual)
        self.slider.set_sensitive(p.is_manual)
        self._speed_val.set_label(str(int(p.manual_speed)))
        self._updating = False

    def _on_switch_toggled(self, switch, state):
        if self._updating:
            return False
        self.slider.set_sensitive(state)
        p = self.profiles.active_profile
        self.profiles.update_manual(p.name, state, int(self.slider.get_value()))
        return False

    def _on_slider_changed(self, slider):
        if self._updating:
            return
        val = int(slider.get_value())
        self._speed_val.set_label(str(val))
        p = self.profiles.active_profile
        self.profiles.update_manual(p.name, self.manual_switch.get_active(), val)
