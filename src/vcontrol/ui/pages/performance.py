import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

from vcontrol.backend.profiles import get_manager
from vcontrol.backend.fan import get_controller

class FanPanel(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        self.set_margin_top(24)
        self.set_margin_bottom(24)
        
        self.profiles = get_manager()
        self.fan_ctrl = get_controller()
        self._current_profile = self.profiles.active_profile.name
        
        self.clamp = Adw.Clamp()
        self.clamp.set_maximum_size(600)
        self.clamp.set_tightening_threshold(400)
        
        clamp_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        
        dashboard_grid = Gtk.Grid(column_spacing=16, row_spacing=16)
        dashboard_grid.set_column_homogeneous(True)
        
        self.lbl_fan1 = self._create_dash_card("CPU Fanı", "0", "RPM", "val-rpm")
        self.lbl_fan2 = self._create_dash_card("GPU Fanı", "0", "RPM", "val-rpm")
        self.lbl_cpu = self._create_dash_card("İşlemci", "0", "°C", "val-cpu")
        self.lbl_gpu = self._create_dash_card("Ekran Kartı", "0", "°C", "val-gpu")
        
        dashboard_grid.attach(self.lbl_cpu['box'], 0, 0, 1, 1)
        dashboard_grid.attach(self.lbl_gpu['box'], 1, 0, 1, 1)
        dashboard_grid.attach(self.lbl_fan1['box'], 0, 1, 1, 1)
        dashboard_grid.attach(self.lbl_fan2['box'], 1, 1, 1, 1)
        
        clamp_box.append(dashboard_grid)

        lbl_modes = Gtk.Label(label="Termal Modlar")
        lbl_modes.set_xalign(0)
        lbl_modes.add_css_class("heading")
        clamp_box.append(lbl_modes)

        self.btn_grid = Gtk.Grid(column_spacing=16, row_spacing=16)
        self.btn_grid.set_column_homogeneous(True)
        
        self.buttons = {}
        col = 0
        for p in self.profiles.all_profiles():
            card = Gtk.Button()
            card.add_css_class("profile-card")
            if p.name == self._current_profile:
                card.add_css_class("active-profile")
                
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            icon = Gtk.Label(label=p.icon)
            icon.add_css_class("profile-icon")
            title = Gtk.Label(label=p.display_name)
            title.add_css_class("profile-title")
            desc = Gtk.Label(label="Ön Tanımlı Eğri")
            if p.is_manual:
                desc.set_label("Özel Fan Hızı")
            desc.add_css_class("profile-desc")
            
            box.append(icon)
            box.append(title)
            box.append(desc)
            card.set_child(box)
            
            card.connect("clicked", self._on_profile_clicked, p.name)
            self.buttons[p.name] = card
            
            self.btn_grid.attach(card, col % 3, col // 3, 1, 1)
            col += 1
            
        clamp_box.append(self.btn_grid)

        self.manual_group = Adw.PreferencesGroup(title="Manuel Kontrol")
        
        self.manual_row = Adw.ActionRow(title="Özel Fan Hızını Kullan", subtitle="Seçili modun otomatik eğrisini iptal edip sabit hız uygular")
        self.manual_switch = Gtk.Switch(valign=Gtk.Align.CENTER)
        self.manual_switch.connect("state-set", self._on_switch_toggled)
        self.manual_row.add_suffix(self.manual_switch)
        self.manual_group.add(self.manual_row)
        
        self.slider = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 20, 100, 1)
        self.slider.add_css_class("premium-slider")
        self.slider.set_hexpand(True)
        self.slider.set_margin_top(16)
        self.slider.set_margin_bottom(16)
        self.slider.set_margin_start(24)
        self.slider.set_margin_end(24)
        self.slider.add_mark(20, Gtk.PositionType.BOTTOM, "Sessiz")
        self.slider.add_mark(50, Gtk.PositionType.BOTTOM, "%50")
        self.slider.add_mark(100, Gtk.PositionType.BOTTOM, "Maksimum")
        self.slider.connect("value-changed", self._on_slider_changed)
        
        slider_row = Adw.PreferencesRow()
        slider_row.set_child(self.slider)
        self.manual_group.add(slider_row)
        
        clamp_box.append(self.manual_group)

        self.clamp.set_child(clamp_box)
        self.append(self.clamp)

        self._refresh_ui()
        
        GLib.timeout_add(1000, self._update_dashboard)

    def _create_dash_card(self, title, val, unit, color_class):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.add_css_class("dashboard-card")
        
        lbl_title = Gtk.Label(label=title)
        lbl_title.add_css_class("dashboard-title")
        lbl_title.set_xalign(0)
        
        val_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        lbl_val = Gtk.Label(label=val)
        lbl_val.add_css_class("dashboard-value")
        lbl_val.add_css_class(color_class)
        lbl_unit = Gtk.Label(label=unit)
        lbl_unit.add_css_class("dashboard-unit")
        lbl_unit.set_yalign(0.8)
        
        val_box.append(lbl_val)
        val_box.append(lbl_unit)
        
        box.append(lbl_title)
        box.append(val_box)
        
        return {"box": box, "val": lbl_val}

    def _update_dashboard(self):
        rpms = self.fan_ctrl.get_rpms()
        self.lbl_fan1['val'].set_label(str(rpms.get('fan1', 0)))
        self.lbl_fan2['val'].set_label(str(rpms.get('fan2', 0)))
        
        temps = self.fan_ctrl.get_temperatures()
        self.lbl_cpu['val'].set_label(str(temps.get('cpu', 0)))
        self.lbl_gpu['val'].set_label(str(temps.get('gpu', 0)))
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
        p = self.profiles.active_profile
        self.manual_switch.set_active(p.is_manual)
        self.slider.set_value(p.manual_speed)
        self.slider.set_sensitive(p.is_manual)

    def _on_switch_toggled(self, switch, state):
        self.slider.set_sensitive(state)
        p = self.profiles.active_profile
        self.profiles.update_manual(p.name, state, int(self.slider.get_value()))
        return False

    def _on_slider_changed(self, slider):
        val = int(slider.get_value())
        p = self.profiles.active_profile
        self.profiles.update_manual(p.name, self.manual_switch.get_active(), val)
