

import logging
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from vcontrol.backend.rgb import RGBController, RGBStatus

logger = logging.getLogger(__name__)

class RGBPanel(Gtk.ScrolledWindow):

    def __init__(self, rgb: RGBController):
        super().__init__()
        self._rgb = rgb
        self._build_ui()

    def _build_ui(self):
        self.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        content.set_margin_top(24)
        content.set_margin_start(24)
        content.set_margin_end(24)
        content.set_margin_bottom(24)
        self.set_child(content)

        status_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        status_card.add_css_class("card")

        status = self._rgb.get_status()
        method_map = {
            "sysfs_led": "✅ sysfs LED (tam destek)",
            "wmi": "⚠️ WMI (deneysel)",
            "none": "❌ Desteklenmiyor",
        }
        method_lbl = Gtk.Label(label=f"Yöntem: {method_map.get(status.method, status.method)}")
        method_lbl.set_xalign(0)
        status_card.append(method_lbl)

        if not status.supported:
            info = Gtk.Label()
            info.set_markup(
                "<b>Bu kernel sürümünde HP Victus 16 RGB sysfs desteği henüz aktif değil.</b>\n\n"
                "Çözüm seçenekleri:\n"
                "• Daha yeni bir kernel sürümüne geçin\n"
                "• hp-wmi-fan-and-backlight-control DKMS modülünü kurun (AUR'da mevcut)\n\n"
                "WMI keşif sonuçlarını görmek için aşağıdaki butonu kullanın."
            )
            info.set_wrap(True)
            info.set_xalign(0)
            status_card.append(info)

            discover_btn = Gtk.Button(label="🔍 WMI Keşif Çalıştır")
            discover_btn.add_css_class("apply-btn")
            discover_btn.connect("clicked", self._on_discover)
            status_card.append(discover_btn)

            self._discover_output = Gtk.Label(label="")
            self._discover_output.set_wrap(True)
            self._discover_output.set_xalign(0)
            self._discover_output.add_css_class("overlay-subtitle")
            status_card.append(self._discover_output)

        content.append(status_card)

        if status.supported:
            content.append(self._build_brightness_section(status))

    def _build_brightness_section(self, status: RGBStatus) -> Gtk.Widget:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        card.add_css_class("card")

        title = Gtk.Label(label="Parlaklık")
        title.add_css_class("card-title")
        title.set_xalign(0)
        card.append(title)

        adj = Gtk.Adjustment(
            value=status.brightness,
            lower=0,
            upper=status.max_brightness,
            step_increment=1,
        )
        scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=adj)
        scale.set_hexpand(True)
        scale.set_value_pos(Gtk.PositionType.RIGHT)
        scale.set_digits(0)
        scale.connect("value-changed", self._on_brightness_changed)
        card.append(scale)

        return card

    def _on_brightness_changed(self, scale: Gtk.Scale):
        level = int(scale.get_value())
        self._rgb.set_brightness(level)

    def _on_discover(self, btn: Gtk.Button):
        result = self._rgb.discover_wmi()
        lines = [
            f"LED yolu: {result['led_path'] or 'Bulunamadı'}",
            f"WMI yolu: {result['wmi_path'] or 'Bulunamadı'}",
            f"HP GUID'leri: {result['hp_guids_found'] or 'Bulunamadı'}",
        ]
        self._discover_output.set_label("\n".join(lines))
