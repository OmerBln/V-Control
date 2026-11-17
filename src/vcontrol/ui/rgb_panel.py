import logging
import math

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
from gi.repository import Adw, Gdk, Gtk

from vcontrol.backend.rgb import RGBController, get_controller
from vcontrol.backend.settings import LightingState, load_settings
from vcontrol.ui.util import Debouncer

logger = logging.getLogger(__name__)

PRESET_COLORS = [
    ("Victus Mavi", 83, 124, 184),
    ("Cyan", 0, 212, 255),
    ("Mavi", 0, 122, 255),
    ("Yeşil", 52, 199, 89),
    ("Sarı", 255, 204, 0),
    ("Turuncu", 255, 149, 0),
    ("Kırmızı", 255, 59, 48),
    ("Mor", 175, 82, 222),
    ("Beyaz", 255, 255, 255),
]


class _ColorChip(Gtk.DrawingArea):
    """Circular colour swatch drawn with Cairo (no per-update CssProvider leak)."""

    def __init__(self, r: int, g: int, b: int, size: int = 28):
        super().__init__()
        self._rgb = (r, g, b)
        self._selected = False
        self.set_content_width(size)
        self.set_content_height(size)
        self.set_valign(Gtk.Align.CENTER)
        self.set_draw_func(self._draw)

    @property
    def rgb(self) -> tuple[int, int, int]:
        return self._rgb

    def set_rgb(self, r: int, g: int, b: int) -> None:
        if self._rgb != (r, g, b):
            self._rgb = (r, g, b)
            self.queue_draw()

    def set_selected(self, selected: bool) -> None:
        if self._selected != selected:
            self._selected = selected
            self.queue_draw()

    def _draw(self, _area, cr, w, h):
        r, g, b = (c / 255.0 for c in self._rgb)
        cx, cy = w / 2.0, h / 2.0
        radius = min(w, h) / 2.0 - 3.5

        cr.set_source_rgb(r, g, b)
        cr.arc(cx, cy, radius, 0, 2 * math.pi)
        cr.fill()

        cr.set_source_rgba(1, 1, 1, 0.22)
        cr.set_line_width(1.0)
        cr.arc(cx, cy, radius, 0, 2 * math.pi)
        cr.stroke()

        if self._selected:
            fg = self.get_color()
            cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.95)
            cr.set_line_width(2.2)
            cr.arc(cx, cy, radius + 2.5, 0, 2 * math.pi)
            cr.stroke()


class RGBPanel(Gtk.ScrolledWindow):
    def __init__(self, rgb: RGBController | None = None):
        super().__init__()
        self.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.set_hexpand(True)
        self.set_vexpand(True)
        self._rgb = rgb or get_controller()
        self._updating = False
        self._selected_zone = -1
        self._current_rgb = (255, 255, 255)
        self._current_brightness = 255
        self._max_brightness = 255
        self._last_nonzero_brightness = 255
        self._chips: list[tuple[_ColorChip, tuple[int, int, int]]] = []
        self._bright_debouncer = Debouncer(150, self._commit_brightness)
        self._color_debouncer = Debouncer(150, self._commit_color)
        self._build_ui()

    def flush_pending(self) -> None:
        self._bright_debouncer.flush()
        self._color_debouncer.flush()

    @staticmethod
    def _color_subtitle(r: int, g: int, b: int) -> str:
        return f"Renk paletinden ton seçin · #{r:02X}{g:02X}{b:02X}"

    def _update_bright_label(self, level: int) -> None:
        pct = round(level / max(1, self._max_brightness) * 100)
        self._bright_pct_lbl.set_label(f"%{pct}")

    def _build_ui(self) -> None:
        clamp = Adw.Clamp()
        clamp.set_maximum_size(680)
        clamp.set_tightening_threshold(420)
        clamp.set_margin_top(24)
        clamp.set_margin_bottom(28)
        clamp.set_margin_start(16)
        clamp.set_margin_end(16)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        status = self._rgb.get_status()
        self._max_brightness = max(1, status.max_brightness)
        self._current_brightness = status.brightness
        self._last_nonzero_brightness = (
            status.brightness if status.brightness > 0 else self._max_brightness
        )
        self._current_rgb = (status.red, status.green, status.blue)

        if not status.supported:
            status_page = Adw.StatusPage(
                icon_name="keyboard-brightness-symbolic",
                title="Klavye Aydınlatma Desteği Bulunamadı",
                description="Bu cihazda veya mevcut çekirdek sürümünde HP WMI / sysfs klavye LED sürücüsü aktif değil.",
            )
            content.append(status_page)
        else:
            bright_group = Adw.PreferencesGroup(
                title="Arka Işık Parlaklığı",
                description=f"Donanım yöntemi: {status.method}",
            )

            power_row = Adw.ActionRow(
                title="Klavye Aydınlatması",
                subtitle="Arka ışığı hızlıca açıp kapatır",
            )
            self._power_switch = Gtk.Switch(valign=Gtk.Align.CENTER)
            self._power_switch.set_active(status.brightness > 0)
            self._power_switch.connect("state-set", self._on_power_toggled)
            power_row.add_suffix(self._power_switch)
            bright_group.add(power_row)

            bright_row = Adw.ActionRow(title="Parlaklık Seviyesi")

            self._bright_scale = Gtk.Scale.new_with_range(
                Gtk.Orientation.HORIZONTAL, 0, self._max_brightness, 1
            )
            self._bright_scale.set_value(status.brightness)
            self._bright_scale.set_hexpand(True)
            self._bright_scale.set_size_request(200, -1)
            self._bright_scale.connect("value-changed", self._on_brightness_changed)

            self._bright_pct_lbl = Gtk.Label(xalign=1, valign=Gtk.Align.CENTER)
            self._bright_pct_lbl.set_width_chars(5)
            self._bright_pct_lbl.add_css_class("graph-legend-value")
            self._update_bright_label(status.brightness)

            bright_row.add_suffix(self._bright_scale)
            bright_row.add_suffix(self._bright_pct_lbl)
            bright_group.add(bright_row)
            content.append(bright_group)

            if status.has_color:
                color_group = Adw.PreferencesGroup(
                    title="RGB Renk Seçimi",
                    description="Klavye aydınlatma rengini ve bölgesini özelleştirin",
                )

                if status.zones > 1:
                    zone_labels = ["Tüm Bölgeler"] + [f"Bölge {i + 1}" for i in range(status.zones)]
                    zone_row = Adw.ComboRow(
                        title="Aydınlatma Bölgesi",
                        subtitle="Rengin uygulanacağı klavye bölgesi",
                        model=Gtk.StringList.new(zone_labels),
                    )
                    zone_row.connect("notify::selected", self._on_zone_changed)
                    color_group.add(zone_row)

                self._preview_row = Adw.ActionRow(
                    title="Özel Renk",
                    subtitle=self._color_subtitle(status.red, status.green, status.blue),
                )

                self._color_preview = _ColorChip(status.red, status.green, status.blue, size=26)

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

                self._preview_row.add_suffix(self._color_preview)
                self._preview_row.add_suffix(self._color_btn)
                color_group.add(self._preview_row)

                preset_box = Gtk.FlowBox()
                preset_box.set_selection_mode(Gtk.SelectionMode.NONE)
                preset_box.set_max_children_per_line(9)
                preset_box.set_row_spacing(10)
                preset_box.set_column_spacing(10)
                preset_box.set_margin_top(12)
                preset_box.set_margin_bottom(12)
                preset_box.set_margin_start(12)
                preset_box.set_margin_end(12)

                for name, r, g, b in PRESET_COLORS:
                    btn = Gtk.Button()
                    btn.add_css_class("color-swatch-btn")
                    btn.set_tooltip_text(name)
                    chip = _ColorChip(r, g, b, size=32)
                    btn.set_child(chip)
                    btn.connect("clicked", self._on_preset_clicked, r, g, b)
                    preset_box.append(btn)
                    self._chips.append((chip, (r, g, b)))

                self._sync_chip_selection(status.red, status.green, status.blue)

                preset_row = Adw.PreferencesRow()
                preset_row.set_child(preset_box)
                color_group.add(preset_row)

                content.append(color_group)

        clamp.set_child(content)
        self.set_child(clamp)

    def _sync_chip_selection(self, r: int, g: int, b: int) -> None:
        for chip, rgb in self._chips:
            chip.set_selected(rgb == (r, g, b))

    def _persist_lighting(self) -> None:
        settings = load_settings()
        r, g, b = self._current_rgb
        settings.lighting = LightingState(
            brightness=self._current_brightness,
            red=r,
            green=g,
            blue=b,
        )
        settings.save()

    def _on_zone_changed(self, combo_row: Adw.ComboRow, _pspec) -> None:
        idx = int(combo_row.get_selected())
        self._selected_zone = -1 if idx == 0 else idx - 1

    def _on_power_toggled(self, _switch: Gtk.Switch, state: bool) -> bool:
        if self._updating:
            return False
        if state:
            target = self._last_nonzero_brightness or self._max_brightness
        else:
            if self._current_brightness > 0:
                self._last_nonzero_brightness = self._current_brightness
            target = 0
        self._updating = True
        self._bright_scale.set_value(target)
        self._updating = False
        self._current_brightness = target
        self._update_bright_label(target)
        self._bright_debouncer(target)
        return False

    def _on_brightness_changed(self, scale: Gtk.Scale) -> None:
        if self._updating:
            return
        level = int(scale.get_value())
        self._current_brightness = level
        if level > 0:
            self._last_nonzero_brightness = level
        self._updating = True
        self._power_switch.set_active(level > 0)
        self._updating = False
        self._update_bright_label(level)
        self._bright_debouncer(level)

    def _commit_brightness(self, level: int) -> None:
        self._rgb.set_brightness(level)
        self._persist_lighting()

    def _on_preset_clicked(self, _btn: Gtk.Button, r: int, g: int, b: int) -> None:
        self._updating = True
        rgba = Gdk.RGBA()
        rgba.red = r / 255.0
        rgba.green = g / 255.0
        rgba.blue = b / 255.0
        rgba.alpha = 1.0
        self._color_btn.set_rgba(rgba)
        self._color_preview.set_rgb(r, g, b)
        self._preview_row.set_subtitle(self._color_subtitle(r, g, b))
        self._sync_chip_selection(r, g, b)
        self._current_rgb = (r, g, b)
        self._updating = False
        self._color_debouncer(r, g, b, self._selected_zone)

    def _on_custom_color_selected(self, btn: Gtk.ColorDialogButton, _pspec) -> None:
        if self._updating:
            return
        rgba = btn.get_rgba()
        r = round(rgba.red * 255.0)
        g = round(rgba.green * 255.0)
        b = round(rgba.blue * 255.0)
        self._color_preview.set_rgb(r, g, b)
        self._preview_row.set_subtitle(self._color_subtitle(r, g, b))
        self._sync_chip_selection(r, g, b)
        self._current_rgb = (r, g, b)
        self._color_debouncer(r, g, b, self._selected_zone)

    def _commit_color(self, r: int, g: int, b: int, zone: int) -> None:
        self._rgb.set_color(r, g, b, zone=zone)
        self._persist_lighting()
