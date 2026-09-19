

import logging
import os
import sys
from typing import Optional

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gtk, Gdk, GLib, Pango

logger = logging.getLogger(__name__)

_SRC_DIR = os.path.join(os.path.dirname(__file__), "..", "..")
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from vcontrol.backend.fan import get_controller as get_fan, FanStatus, PP_DISPLAY
from vcontrol.backend.sensors import read_all as _read_all

UPDATE_INTERVAL_MS = 2000

QUICK_PROFILES = [
    ("low-power",   "🤫", "Sessiz"),
    ("balanced",    "⚖️",  "Dengeli"),
    ("performance", "🚀", "Performans"),
]

def load_css():
    css_path = os.path.join(os.path.dirname(__file__), "style.css")
    if not os.path.exists(css_path):
        return
    provider = Gtk.CssProvider()
    provider.load_from_path(css_path)
    Gtk.StyleContext.add_provider_for_display(
        Gdk.Display.get_default(),
        provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
    )

class QuickOverlay(Gtk.ApplicationWindow):

    def __init__(self, app: Gtk.Application):
        super().__init__(application=app)
        self._fan = get_fan()
        self._pp_buttons: dict[str, Gtk.Button] = {}
        self._update_timer: Optional[int] = None
        

        self.set_title("V-Control — Quick Layout")
        self.set_default_size(360, -1)
        self.set_resizable(False)
        self.add_css_class("overlay-window")
        self.set_decorated(False)

        self._build_ui()

        focus_ctrl = Gtk.EventControllerFocus()
        focus_ctrl.connect("leave", self._on_focus_leave)
        self.add_controller(focus_ctrl)

        key_ctrl = Gtk.EventControllerKey()
        key_ctrl.connect("key-pressed", self._on_key_pressed)
        self.add_controller(key_ctrl)

    def _setup_watchdog(self):
        def _apply():
            current = self._fan.get_status().platform_profile
            return self._fan.set_platform_profile(current)

        self._watchdog = get_watchdog()
        if self._fan.profile_control_available:
            self._watchdog.start()

    def _build_ui(self):
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_child(root)
        root.append(self._build_header())
        root.append(self._build_body())
        root.append(self._build_footer())

    def _build_header(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        box.add_css_class("overlay-header")

        icon = Gtk.Label(label="🎮")
        icon.set_yalign(0.5)

        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        title = Gtk.Label(label="V-Control")
        title.add_css_class("overlay-title")
        title.set_xalign(0)
        sub = Gtk.Label(label="Quick Layout")
        sub.add_css_class("overlay-subtitle")
        sub.set_xalign(0)
        title_box.append(title)
        title_box.append(sub)

        self._header_status = Gtk.Label(label="Yükleniyor…")
        self._header_status.add_css_class("overlay-subtitle")
        self._header_status.set_hexpand(True)
        self._header_status.set_halign(Gtk.Align.END)

        close_btn = Gtk.Button(label="✕")
        close_btn.add_css_class("flat")
        close_btn.connect("clicked", lambda _: self.close())

        box.append(icon)
        box.append(title_box)
        box.append(self._header_status)
        box.append(close_btn)
        return box

    def _build_body(self) -> Gtk.Widget:
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        body.add_css_class("overlay-body")
        body.append(self._build_profile_section())
        body.append(self._build_rpm_pin_section())
        body.append(self._build_live_section())
        return body

    def _build_profile_section(self) -> Gtk.Widget:
        section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)

        label = Gtk.Label(label="Fan Profili")
        label.add_css_class("overlay-section-label")
        label.set_xalign(0)
        section.append(label)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)

        for pp_name, icon, display in QUICK_PROFILES:
            btn = Gtk.Button()
            inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
            inner.set_margin_top(6)
            inner.set_margin_bottom(6)
            inner.append(Gtk.Label(label=icon))
            name_lbl = Gtk.Label(label=display)
            name_lbl.set_ellipsize(Pango.EllipsizeMode.END)
            inner.append(name_lbl)
            btn.set_child(inner)
            btn.add_css_class("profile-btn")
            btn.set_hexpand(True)
            btn.set_tooltip_text(f"{display} fan profilini uygula")
            btn.connect("clicked", self._on_profile_clicked, pp_name)
            self._pp_buttons[pp_name] = btn
            btn_row.append(btn)

        section.append(btn_row)

        self._profile_status = Gtk.Label(label="")
        self._profile_status.add_css_class("overlay-subtitle")
        self._profile_status.set_xalign(0)
        section.append(self._profile_status)

        self._refresh_buttons()
        return section

    def _build_rpm_pin_section(self) -> Gtk.Widget:
        section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)

        label = Gtk.Label(label="RPM Hedefi → Otomatik Profil Seç")
        label.add_css_class("overlay-section-label")
        label.set_xalign(0)
        section.append(label)

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        adj = Gtk.Adjustment(value=2500, lower=1000, upper=5000,
                             step_increment=100, page_increment=500)
        self._rpm_spin = Gtk.SpinButton(adjustment=adj, climb_rate=1.0, digits=0)
        self._rpm_spin.add_css_class("rpm-spinbox")
        self._rpm_spin.set_hexpand(True)
        self._rpm_spin.set_tooltip_text(
            "≥3500 RPM → Performans\n2000-3499 → Dengeli\n<2000 → Sessiz"
        )

        apply_btn = Gtk.Button(label="Uygula")
        apply_btn.add_css_class("apply-btn")
        apply_btn.connect("clicked", self._on_rpm_apply)

        row.append(self._rpm_spin)
        row.append(apply_btn)
        section.append(row)
        return section

    def _build_live_section(self) -> Gtk.Widget:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)

        cards = [
            ("CPU Fan",      "_cpu_rpm_lbl",  "RPM"),
            ("GPU Fan",      "_gpu_rpm_lbl",  "RPM"),
            ("CPU Sıcaklık", "_cpu_temp_lbl", "°C"),
        ]

        for title, attr, unit in cards:
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            box.add_css_class("card")
            box.set_hexpand(True)

            t = Gtk.Label(label=title)
            t.add_css_class("card-title")
            t.set_xalign(0)

            v = Gtk.Label(label="—")
            v.add_css_class("rpm-label")
            v.set_xalign(0)
            setattr(self, attr, v)

            u = Gtk.Label(label=unit)
            u.add_css_class("rpm-unit")
            u.set_xalign(0)

            box.append(t)
            box.append(v)
            box.append(u)
            row.append(box)

        return row

    def _build_footer(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        box.set_margin_start(20)
        box.set_margin_end(20)
        box.set_margin_bottom(12)

        self._active_label = Gtk.Label(label="")
        self._active_label.add_css_class("overlay-subtitle")
        self._active_label.set_hexpand(True)
        self._active_label.set_xalign(0)

        open_btn = Gtk.Button(label="Tam Uygulama →")
        open_btn.add_css_class("flat")
        open_btn.connect("clicked", self._open_main_app)

        box.append(self._active_label)
        box.append(open_btn)
        return box

    def _on_profile_clicked(self, btn: Gtk.Button, pp_name: str):
        ok = self._fan.set_platform_profile(pp_name)
        display = PP_DISPLAY.get(pp_name, pp_name)
        if ok:
            self._profile_status.set_label(f"✅ {display}")
            self._active_label.set_label(f"Profil: {display}")
            self._refresh_buttons(pp_name)
        else:
            self._profile_status.set_label("❌ İzin hatası — sudo gerekli")

    def _on_rpm_apply(self, btn: Gtk.Button):
        rpm = int(self._rpm_spin.get_value())
        ok = self._fan.set_rpm_target(rpm)
        current = self._fan.get_status().platform_profile
        display = PP_DISPLAY.get(current, current)
        if ok:
            self._active_label.set_label(f"{rpm} RPM → {display}")
            self._refresh_buttons(current)
        else:
            self._active_label.set_label("❌ Uygulama başarısız")

    def _on_focus_leave(self, ctrl):
        GLib.timeout_add(200, self.close)

    def _on_key_pressed(self, ctrl, keyval, keycode, state):
        if keyval == Gdk.KEY_Escape:
            self.close()
            return True
        return False

    def _open_main_app(self, btn):
        import subprocess
        venv_py = os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "..", ".venv", "bin", "python3"
        )
        py = venv_py if os.path.exists(venv_py) else sys.executable
        subprocess.Popen([py, "-m", "vcontrol.main"], start_new_session=True)

    def start_updates(self):
        self._update_now()
        self._update_timer = GLib.timeout_add(UPDATE_INTERVAL_MS, self._update_now)

    def stop_updates(self):
        if self._update_timer:
            GLib.source_remove(self._update_timer)
            self._update_timer = None

    def _update_now(self) -> bool:
        try:
            status = self._fan.get_status()
            sensors = _read_all_safe()
            cpu_t   = sensors.get("cpu_temp", 0.0)

            self._cpu_rpm_lbl.set_label(
                f"{status.cpu_rpm:,}" if status.cpu_rpm > 0 else "—"
            )
            self._gpu_rpm_lbl.set_label(
                f"{status.gpu_rpm:,}" if status.gpu_rpm > 0 else "—"
            )
            self._cpu_temp_lbl.set_label(f"{cpu_t:.0f}" if cpu_t > 0 else "—")

            profile_display = PP_DISPLAY.get(status.platform_profile, status.platform_profile)
            self._header_status.set_label(
                f"{profile_display} · {cpu_t:.0f}°C"
            )
            self._active_label.set_label(f"Aktif: {profile_display}")
            self._refresh_buttons(status.platform_profile)

        except Exception as e:
            logger.error(f"Overlay güncelleme hatası: {e}")
        return True

    def _refresh_buttons(self, active: str = None):
        if active is None:
            active = self._fan.get_status().platform_profile
        for name, btn in self._pp_buttons.items():
            if name == active:
                btn.add_css_class("active")
            else:
                btn.remove_css_class("active")

    def do_close_request(self) -> bool:
        self.stop_updates()
                return False

def _read_all_safe() -> dict:
    try:
        r = _read_all()
        return {"cpu_temp": r.cpu_temp, "gpu_temp": r.gpu_temp}
    except Exception:
        return {"cpu_temp": 0.0, "gpu_temp": 0.0}

class OverlayApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.vcontrol.overlay")
        self._window: Optional[QuickOverlay] = None

    def do_activate(self):
        load_css()
        if self._window is None:
            self._window = QuickOverlay(app=self)
        self._window.present()
        self._window.start_updates()
