import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw

class SettingsPanel(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        self.set_margin_top(24)
        self.set_margin_bottom(24)
        
        clamp = Adw.Clamp()
        clamp.set_maximum_size(600)
        clamp.set_tightening_threshold(400)
        
        clamp_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        
        theme_group = Adw.PreferencesGroup(title="Görünüm Ayarları", description="Uygulama temasını belirleyin")
        
        theme_row = Adw.ActionRow(title="Tema Seçimi")
        
        model = Gtk.StringList.new(["Sistem Varsayılanı", "Açık Tema", "Koyu Tema"])
        self.theme_dropdown = Gtk.DropDown.new(model=model)
        self.theme_dropdown.set_valign(Gtk.Align.CENTER)
        
        style_mgr = Adw.StyleManager.get_default()
        current_scheme = style_mgr.get_color_scheme()
        if current_scheme == Adw.ColorScheme.FORCE_LIGHT:
            self.theme_dropdown.set_selected(1)
        elif current_scheme == Adw.ColorScheme.FORCE_DARK:
            self.theme_dropdown.set_selected(2)
        else:
            self.theme_dropdown.set_selected(0)
            
        self.theme_dropdown.connect("notify::selected", self._on_theme_changed)
        
        theme_row.add_suffix(self.theme_dropdown)
        theme_group.add(theme_row)
        
        clamp_box.append(theme_group)
        clamp.set_child(clamp_box)
        
        self.append(clamp)

    def _on_theme_changed(self, dropdown, pspec):
        selected = dropdown.get_selected()
        style_mgr = Adw.StyleManager.get_default()
        if selected == 1:
            style_mgr.set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)
        elif selected == 2:
            style_mgr.set_color_scheme(Adw.ColorScheme.FORCE_DARK)
        else:
            style_mgr.set_color_scheme(Adw.ColorScheme.DEFAULT)
