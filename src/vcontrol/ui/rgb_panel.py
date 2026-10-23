import logging

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
from gi.repository import Adw, Gdk, Gtk

from vcontrol.backend.rgb import RGBController, get_controller

logger = logging.getLogger(__name__)

PRESET_COLORS = [
    ("Kırmızı", 255, 0, 0, "#ff3b30"),
    ("Yeşil", 0, 255, 0, "#34c759"),
    ("Mavi", 0, 122, 255, "#007aff"),
    ("Cyan", 0, 255, 255, "#32ade6"),
    ("Magenta", 255, 0, 255, "#af52de"),
    ("Sarı", 255, 204, 0, "#ffcc00"),
    ("Turuncu", 255, 149, 0, "#ff9500"),
    ("Victus Mavi", 83, 124, 184, "#537cb8"),
    ("Beyaz", 255, 255, 255, "#ffffff"),
]


class RGBPanel(Gtk.ScrolledWindow):
    def __init__(self, rgb: RGBController | None = None):
        super().__init__()
        self.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._rgb = rgb or get_controller()
        self._updating = False
        self._build_ui()

    def _build_ui(self):
        clamp = Adw.Clamp()
        clamp.set_maximum_size(640)
        clamp.set_margin_top(28)
        clamp.set_margin_bottom(28)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        status = self._rgb.get_status()

        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        title_lbl = Gtk.Label(label="Klavye Aydınlatması")
        title_lbl.add_css_class("heading")
        title_lbl.set_xalign(0)

        method_text = "HP WMI / sysfs LED Destekleniyor" if status.supported else "Desteklenmiyor"
        sub_lbl = Gtk.Label(label=f"Yöntem: {status.method} — {method_text}")
        sub_lbl.add_css_class("caption")
        sub_lbl.set_xalign(0)

        title_box.append(title_lbl)
        title_box.append(sub_lbl)
        content.append(title_box)

        if not status.supported:
            info_group = Adw.PreferencesGroup()
            row = Adw.ActionRow(
                title="Donanım Desteği Bulunamadı",
                subtitle="Bu kernel sürümünde klavye LED aygıtı aktif değil.",
            )
            info_group.add(row)
            content.append(info_group)
        else:
            bright_group = Adw.PreferencesGroup(title="Parlaklık")
            bright_row = Adw.ActionRow(title="Klavye Arka Işığı")

            self._bright_scale = Gtk.Scale.new_with_range(
                Gtk.Orientation.HORIZONTAL, 0, status.max_brightness, 1
            )
            self._bright_scale.set_value(status.brightness)
            self._bright_scale.set_hexpand(True)
            self._bright_scale.set_size_request(200, -1)
            self._bright_scale.connect("value-changed", self._on_brightness_changed)

            bright_row.add_suffix(self._bright_scale)
            bright_group.add(bright_row)
            content.append(bright_group)

            if status.has_color:
                color_group = Adw.PreferencesGroup(
                    title="RGB Renk Ayarı",
                    description="Klavyenizin aydınlatma rengini seçin",
                )

                preview_row = Adw.ActionRow(title="Seçili Renk")

                self._color_preview = Gtk.Box()
                self._color_preview.set_size_request(40, 24)
                self._color_preview.set_valign(Gtk.Align.CENTER)
                self._color_preview.add_css_class("card")
                self._update_preview_css(status.red, status.green, status.blue)

                rgba = Gdk.RGBA()
                rgba.red = status.red / 255.0
                rgba.green = status.green / 255.0
                rgba.blue = status.blue / 255.0
                rgba.alpha = 1.0

                self._color_btn = Gtk.ColorDialogButton()
                dialog = Gtk.ColorDialog.new()
                dialog.set_with_alpha(False)
                self._color_btn.set_dialog(dialog)
                self._color_btn.set_rgba(rgba)
                self._color_btn.set_valign(Gtk.Align.CENTER)
                self._color_btn.connect("notify::rgba", self._on_custom_color_selected)

                preview_row.add_suffix(self._color_preview)
                preview_row.add_suffix(self._color_btn)
                color_group.add(preview_row)

                preset_box = Gtk.FlowBox()
                preset_box.set_selection_mode(Gtk.SelectionMode.NONE)
                preset_box.set_max_children_per_line(5)
                preset_box.set_row_spacing(8)
                preset_box.set_column_spacing(8)
                preset_box.set_margin_top(8)

                for name, r, g, b, hex_code in PRESET_COLORS:
                    btn = Gtk.Button()
                    btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
                    dot = Gtk.Box()
                    dot.set_size_request(14, 14)
                    provider = Gtk.CssProvider()
                    provider.load_from_string(f"box {{ background-color: {hex_code}; border-radius: 7px; }}")
                    dot.get_style_context().add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

                    lbl = Gtk.Label(label=name)
                    btn_box.append(dot)
                    btn_box.append(lbl)
                    btn.set_child(btn_box)
                    btn.connect("clicked", self._on_preset_clicked, r, g, b)
                    preset_box.append(btn)

                preset_row = Adw.PreferencesRow()
                preset_row.set_child(preset_box)
                color_group.add(preset_row)

                content.append(color_group)

        clamp.set_child(content)
        self.set_child(clamp)

    def _update_preview_css(self, r: int, g: int, b: int):
        provider = Gtk.CssProvider()
        provider.load_from_string(
            f"box {{ background-color: rgb({r}, {g}, {b}); border-radius: 6px; "
            f"border: 1px solid rgba(255,255,255,0.2); }}"
        )
        self._color_preview.get_style_context().add_provider(
            provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def _on_brightness_changed(self, scale: Gtk.Scale):
        if self._updating:
            return
        level = int(scale.get_value())
        self._rgb.set_brightness(level)

    def _on_preset_clicked(self, btn, r: int, g: int, b: int):
        self._updating = True
        rgba = Gdk.RGBA()
        rgba.red = r / 255.0
        rgba.green = g / 255.0
        rgba.blue = b / 255.0
        rgba.alpha = 1.0
        self._color_btn.set_rgba(rgba)
        self._update_preview_css(r, g, b)
        self._rgb.set_color(r, g, b)
        self._updating = False

    def _on_custom_color_selected(self, btn, pspec):
        if self._updating:
            return
        rgba = btn.get_rgba()
        r = int(rgba.red * 255.0)
        g = int(rgba.green * 255.0)
        b = int(rgba.blue * 255.0)
        self._update_preview_css(r, g, b)
        self._rgb.set_color(r, g, b)
