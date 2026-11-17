import math

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

from vcontrol.backend.daemon_status import is_daemon_alive, start_service
from vcontrol.backend.fan import get_controller
from vcontrol.backend.fan_curves import get_curve, get_target_pwm
from vcontrol.backend.profiles import get_manager
from vcontrol.ui.util import Debouncer, set_temp_class
from vcontrol.ui.widgets import BLUE, CYAN, GREEN, ORANGE, RED, MetricCard

_MODE_COLORS = {
    "Eco": GREEN,
    "Balanced": BLUE,
    "Performance": ORANGE,
}


class FanCurveArea(Gtk.DrawingArea):
    """Draws the active fan curve, hysteresis release band, and operating point with Cairo."""

    MARGIN_LEFT = 42
    MARGIN_RIGHT = 16
    MARGIN_TOP = 14
    MARGIN_BOTTOM = 24
    TEMP_MIN = 30.0
    TEMP_MAX = 100.0

    def __init__(self):
        super().__init__()
        self._mode = "Balanced"
        self._is_manual = False
        self._max_fan = False
        self._manual_speed = 50
        self._hysteresis = 4
        self._current_temp = 45
        self._target_speed = 30
        self._hover_temp: int | None = None
        self.set_content_height(160)
        self.set_hexpand(True)
        self.set_draw_func(self._draw)

        motion = Gtk.EventControllerMotion.new()
        motion.connect("motion", self._on_motion)
        motion.connect("leave", self._on_leave)
        self.add_controller(motion)

    def _on_motion(self, _ctrl: Gtk.EventControllerMotion, x: float, _y: float) -> None:
        plot_w = max(1.0, self.get_width() - self.MARGIN_LEFT - self.MARGIN_RIGHT)
        if x < self.MARGIN_LEFT or x > self.MARGIN_LEFT + plot_w:
            self._on_leave(_ctrl)
            return
        ratio = (x - self.MARGIN_LEFT) / plot_w
        temp = round(self.TEMP_MIN + ratio * (self.TEMP_MAX - self.TEMP_MIN))
        temp = max(int(self.TEMP_MIN), min(int(self.TEMP_MAX), temp))
        if temp != self._hover_temp:
            self._hover_temp = temp
            self.queue_draw()

    def _on_leave(self, _ctrl: Gtk.EventControllerMotion) -> None:
        if self._hover_temp is not None:
            self._hover_temp = None
            self.queue_draw()

    def update_state(
        self,
        mode: str,
        is_manual: bool,
        max_fan: bool,
        manual_speed: int,
        hysteresis: int,
        control_temp: int,
        target_speed: int,
    ) -> None:
        state = (mode, is_manual, max_fan, manual_speed, hysteresis, control_temp, target_speed)
        prev = (
            self._mode,
            self._is_manual,
            self._max_fan,
            self._manual_speed,
            self._hysteresis,
            self._current_temp,
            self._target_speed,
        )
        if state == prev:
            return
        (
            self._mode,
            self._is_manual,
            self._max_fan,
            self._manual_speed,
            self._hysteresis,
            self._current_temp,
            self._target_speed,
        ) = state
        if self.get_mapped():
            self.queue_draw()

    def _build_step_points(self, shift_temp: float = 0.0) -> list[tuple[float, float]]:
        if self._max_fan:
            return [(self.TEMP_MIN, 100.0), (self.TEMP_MAX, 100.0)]
        if self._is_manual:
            return [
                (self.TEMP_MIN, float(self._manual_speed)),
                (self.TEMP_MAX, float(self._manual_speed)),
            ]
        raw_curve = get_curve(self._mode)
        pts: list[tuple[float, float]] = [(self.TEMP_MIN, float(raw_curve[0][1]))]
        for t, s in raw_curve[1:]:
            shifted = max(self.TEMP_MIN, min(self.TEMP_MAX, float(t) - shift_temp))
            pts.append((shifted, float(s)))
        pts.append((self.TEMP_MAX, float(raw_curve[-1][1])))
        return pts

    def _draw(self, _area, cr, w, h):
        c = self.get_color()
        fr, fg, fb = c.red, c.green, c.blue
        left = self.MARGIN_LEFT
        top = self.MARGIN_TOP
        plot_w = max(1.0, w - left - self.MARGIN_RIGHT)
        plot_h = max(1.0, h - top - self.MARGIN_BOTTOM)

        def tx(temp: float) -> float:
            clamped = max(self.TEMP_MIN, min(self.TEMP_MAX, temp))
            return left + ((clamped - self.TEMP_MIN) / (self.TEMP_MAX - self.TEMP_MIN)) * plot_w

        def py(pct: float) -> float:
            clamped = max(0.0, min(100.0, pct))
            return top + plot_h - (clamped / 100.0) * plot_h

        cr.select_font_face("Sans", 0, 0)
        cr.set_font_size(10)
        cr.set_line_width(1)

        # Horizontal grid (0%, 25%, 50%, 75%, 100%)
        for pct in (0, 25, 50, 75, 100):
            y = py(pct)
            cr.set_source_rgba(fr, fg, fb, 0.08 if pct else 0.18)
            cr.move_to(left, round(y) + 0.5)
            cr.line_to(left + plot_w, round(y) + 0.5)
            cr.stroke()
            lbl = f"%{pct}"
            ext = cr.text_extents(lbl)
            cr.set_source_rgba(fr, fg, fb, 0.45)
            cr.move_to(left - ext.width - 6, y + ext.height / 2)
            cr.show_text(lbl)

        # Temperature axis ticks
        for t in (30, 50, 65, 75, 85, 95):
            x = tx(t)
            lbl = f"{t}°C"
            ext = cr.text_extents(lbl)
            cr.set_source_rgba(fr, fg, fb, 0.45)
            cr.move_to(x - ext.width / 2, h - 6)
            cr.show_text(lbl)

        pts = self._build_step_points()
        flat_line = self._is_manual or self._max_fan
        if self._max_fan:
            r, g, b = RED
        elif self._is_manual:
            r, g, b = CYAN
        else:
            r, g, b = _MODE_COLORS.get(self._mode, BLUE)

        # Filled area under curve
        cr.move_to(tx(pts[0][0]), py(0))
        for idx, (t, s) in enumerate(pts):
            if idx > 0 and not flat_line:
                cr.line_to(tx(t), py(pts[idx - 1][1]))
            cr.line_to(tx(t), py(s))
        cr.line_to(tx(pts[-1][0]), py(0))
        cr.close_path()
        cr.set_source_rgba(r, g, b, 0.12)
        cr.fill()

        # Dashed hysteresis release curve (auto mode only)
        if not flat_line and self._hysteresis > 0:
            hyst_pts = self._build_step_points(shift_temp=float(self._hysteresis))
            cr.save()
            cr.set_dash([4.0, 4.0])
            cr.move_to(tx(hyst_pts[0][0]), py(hyst_pts[0][1]))
            for idx, (t, s) in enumerate(hyst_pts[1:], 1):
                cr.line_to(tx(t), py(hyst_pts[idx - 1][1]))
                cr.line_to(tx(t), py(s))
            cr.set_source_rgba(r, g, b, 0.45)
            cr.set_line_width(1.4)
            cr.stroke()
            cr.restore()

        # Primary step curve line
        cr.move_to(tx(pts[0][0]), py(pts[0][1]))
        for idx, (t, s) in enumerate(pts[1:], 1):
            if not flat_line:
                cr.line_to(tx(t), py(pts[idx - 1][1]))
            cr.line_to(tx(t), py(s))
        cr.set_source_rgba(r, g, b, 0.92)
        cr.set_line_width(2.2)
        cr.stroke()

        # Breakpoint nodes on automatic curves
        if not flat_line:
            cr.set_source_rgba(r, g, b, 0.95)
            for t, s in pts[1:-1]:
                cr.arc(tx(t), py(s), 3.0, 0, 2 * math.pi)
                cr.fill()

        # Hover crosshair and readout
        if self._hover_temp is not None:
            if self._max_fan:
                hover_speed = 100
            elif self._is_manual:
                hover_speed = self._manual_speed
            else:
                hover_speed = get_target_pwm(
                    self._hover_temp, self._mode, hysteresis=self._hysteresis
                )
            hx = tx(self._hover_temp)
            hy = py(hover_speed)
            cr.save()
            cr.set_dash([3.0, 3.0])
            cr.set_source_rgba(fr, fg, fb, 0.35)
            cr.set_line_width(1.0)
            cr.move_to(hx, top)
            cr.line_to(hx, top + plot_h)
            cr.stroke()
            cr.restore()

            cr.set_source_rgba(fr, fg, fb, 0.9)
            cr.arc(hx, hy, 4.0, 0, 2 * math.pi)
            cr.fill()

            tip = f"İmleç: {self._hover_temp}°C → %{hover_speed}"
            ext = cr.text_extents(tip)
            pad_x = 7
            box_w = ext.width + pad_x * 2
            box_h = 18
            bx = min(left + plot_w - box_w - 4, max(left + 4, hx + 8))
            by = top + 4
            cr.set_source_rgba(0.08, 0.09, 0.12, 0.78)
            cr.rectangle(bx, by, box_w, box_h)
            cr.fill()
            cr.set_source_rgba(1.0, 1.0, 1.0, 0.95)
            cr.move_to(bx + pad_x, by + 13)
            cr.show_text(tip)

        # Operating point marker
        cx = tx(self._current_temp)
        cy = py(self._target_speed)
        marker_color = RED if self._max_fan else CYAN
        cr.set_source_rgba(*marker_color, 0.25)
        cr.arc(cx, cy, 9, 0, 2 * math.pi)
        cr.fill()
        cr.set_source_rgba(*marker_color, 1.0)
        cr.arc(cx, cy, 4.5, 0, 2 * math.pi)
        cr.fill()


class FanPanel(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        self.profiles = get_manager()
        self.fan_ctrl = get_controller()
        self._current_profile = self.profiles.active_profile.name
        self._last_prof_state: tuple[str, bool, int, int, bool] | None = None
        self._effective_target = -1
        self._updating = False
        self._slider_debouncer = Debouncer(150, self._commit_slider_speed)
        self._hyst_debouncer = Debouncer(150, self._commit_hysteresis)

        # ── Daemon status banner ──────────────────────────────
        self.daemon_banner = Adw.Banner(
            title="Arka plan fan servisi çalışmıyor — profil değişiklikleri donanıma uygulanamayabilir.",
            button_label="Servisi Başlat",
            revealed=False,
        )
        self.daemon_banner.connect("button-clicked", self._on_start_daemon_clicked)
        self.append(self.daemon_banner)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(680)
        clamp.set_tightening_threshold(420)
        clamp.set_margin_top(24)
        clamp.set_margin_bottom(28)
        clamp.set_margin_start(16)
        clamp.set_margin_end(16)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)

        # ── Dashboard cards ───────────────────────────────────
        dashboard_grid = Gtk.Grid(column_spacing=14, row_spacing=14)
        dashboard_grid.set_column_homogeneous(True)

        self.card_cpu = MetricCard("🌡", "CPU Sıcaklığı", "°C", "temp-cool")
        self.card_gpu = MetricCard("⚡", "GPU Sıcaklığı", "°C", "temp-cool")
        self.card_fan1 = MetricCard("🌀", "Sol Fan (Fan 1)", "RPM", "val-rpm")
        self.card_fan2 = MetricCard("🌀", "Sağ Fan (Fan 2)", "RPM", "val-rpm")

        dashboard_grid.attach(self.card_cpu, 0, 0, 1, 1)
        dashboard_grid.attach(self.card_gpu, 1, 0, 1, 1)
        dashboard_grid.attach(self.card_fan1, 0, 1, 1, 1)
        dashboard_grid.attach(self.card_fan2, 1, 1, 1, 1)
        root.append(dashboard_grid)

        # ── Profile selector ──────────────────────────────────
        sec_lbl = Gtk.Label(label="Termal Mod", xalign=0)
        sec_lbl.add_css_class("heading")
        root.append(sec_lbl)

        profile_grid = Gtk.Grid(column_spacing=12, row_spacing=12)
        profile_grid.set_column_homogeneous(True)

        self.buttons: dict[str, Gtk.Button] = {}
        self.desc_labels: dict[str, Gtk.Label] = {}
        for col, p in enumerate(self.profiles.all_profiles()):
            card = self._make_profile_card(p)
            profile_grid.attach(card, col, 0, 1, 1)
        root.append(profile_grid)

        # ── Fan curve visualization card ──────────────────────
        curve_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        curve_box.add_css_class("vitals-graph-card")

        curve_hdr = Gtk.Box(spacing=12)
        curve_title = Gtk.Label(label="Aktif Fan Eğrisi", xalign=0, hexpand=True)
        curve_title.add_css_class("vitals-graph-title")
        self.curve_point_lbl = Gtk.Label(label="–")
        self.curve_point_lbl.add_css_class("graph-legend-value")
        curve_hdr.append(curve_title)
        curve_hdr.append(self.curve_point_lbl)

        self.curve_area = FanCurveArea()
        curve_box.append(curve_hdr)
        curve_box.append(self.curve_area)
        root.append(curve_box)

        # ── Manual, boost & hysteresis control ────────────────
        manual_group = Adw.PreferencesGroup(
            title="Fan Hızı ve Tepki Ayarları",
            description="Seçili profil için özel fan hızı veya sıcaklık toleransı belirleyin",
        )

        reset_btn = Gtk.Button()
        reset_btn.add_css_class("flat")
        reset_btn.set_tooltip_text("Aktif profili varsayılan ayarlarına sıfırla")
        reset_btn.set_child(Adw.ButtonContent(icon_name="view-refresh-symbolic", label="Sıfırla"))
        reset_btn.connect("clicked", self._on_reset_clicked)
        manual_group.set_header_suffix(reset_btn)

        boost_row = Adw.ActionRow(
            title="Maksimum Fan (Turbo Boost)",
            subtitle="Tüm fanları anında %100 tam devirde çalıştırır",
        )
        self.boost_switch = Gtk.Switch(valign=Gtk.Align.CENTER)
        self.boost_switch.connect("state-set", self._on_boost_toggled)
        boost_row.add_suffix(self.boost_switch)
        manual_group.add(boost_row)

        manual_row = Adw.ActionRow(
            title="Özel Fan Hızı",
            subtitle="Otomatik sıcaklık eğrisini devre dışı bırakır",
        )
        self.manual_switch = Gtk.Switch(valign=Gtk.Align.CENTER)
        self.manual_switch.connect("state-set", self._on_switch_toggled)
        manual_row.add_suffix(self.manual_switch)
        manual_group.add(manual_row)

        readout_row = Adw.ActionRow(title="Hedef Fan Hızı")
        self._speed_val = Gtk.Label(label="50")
        self._speed_val.add_css_class("speed-readout")
        self._speed_unit = Gtk.Label(label="%", valign=Gtk.Align.END)
        self._speed_unit.add_css_class("speed-readout-unit")
        self._speed_unit.set_margin_bottom(6)
        speed_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        speed_box.set_valign(Gtk.Align.CENTER)
        speed_box.append(self._speed_val)
        speed_box.append(self._speed_unit)
        readout_row.add_suffix(speed_box)
        manual_group.add(readout_row)

        self.slider = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 30, 100, 1)
        self.slider.add_css_class("premium-slider")
        self.slider.set_hexpand(True)
        self.slider.set_margin_top(8)
        self.slider.set_margin_bottom(16)
        self.slider.set_margin_start(24)
        self.slider.set_margin_end(24)
        self.slider.add_mark(30, Gtk.PositionType.BOTTOM, "%30")
        self.slider.add_mark(50, Gtk.PositionType.BOTTOM, "%50")
        self.slider.add_mark(75, Gtk.PositionType.BOTTOM, "%75")
        self.slider.add_mark(100, Gtk.PositionType.BOTTOM, "%100")
        self.slider.connect("value-changed", self._on_slider_changed)

        slider_row = Adw.PreferencesRow()
        slider_row.set_child(self.slider)
        manual_group.add(slider_row)

        self.hyst_row = Adw.SpinRow.new_with_range(1, 10, 1)
        self.hyst_row.set_title("Histerezis (Sıcaklık Toleransı)")
        self.hyst_row.set_subtitle("Fan hızı düşürülmeden önce sıcaklığın kaç °C inmesi gerektiği")
        self.hyst_row.connect("notify::value", self._on_hysteresis_changed)
        manual_group.add(self.hyst_row)

        root.append(manual_group)

        clamp.set_child(root)
        scrolled.set_child(clamp)
        self.append(scrolled)

        self._refresh_ui()
        self._update_dashboard()
        GLib.timeout_add(1000, self._update_dashboard)

    def flush_pending(self) -> None:
        self._slider_debouncer.flush()
        self._hyst_debouncer.flush()

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

        desc_text = f"Özel Hız (%{profile.manual_speed})" if profile.is_manual else "Otomatik Eğri"
        desc = Gtk.Label(label=desc_text)
        desc.add_css_class("profile-desc")

        inner.append(icon)
        inner.append(title)
        inner.append(desc)
        card.set_child(inner)
        card.connect("clicked", self._on_profile_clicked, profile.name)
        self.buttons[profile.name] = card
        self.desc_labels[profile.name] = desc
        return card

    def _refresh_profile_descriptions(self) -> None:
        for prof in self.profiles.all_profiles():
            lbl = self.desc_labels.get(prof.name)
            if lbl is not None:
                text = f"Özel Hız (%{prof.manual_speed})" if prof.is_manual else "Otomatik Eğri"
                lbl.set_label(text)

    def _on_start_daemon_clicked(self, _banner: Adw.Banner) -> None:
        if start_service():
            self.daemon_banner.set_revealed(False)

    def _update_dashboard(self) -> bool:
        if not self.get_root():
            return False

        p = self.profiles.active_profile
        max_fan = self.profiles.max_fan
        prof_state = (p.name, p.is_manual, p.manual_speed, p.hysteresis, max_fan)
        if (
            not self._slider_debouncer.pending
            and not self._hyst_debouncer.pending
            and self._last_prof_state != prof_state
        ):
            if self._last_prof_state is None or self._last_prof_state[0] != p.name:
                self._effective_target = -1
            self._last_prof_state = prof_state
            self._current_profile = p.name
            for n, b in self.buttons.items():
                if n == p.name:
                    b.add_css_class("active-profile")
                else:
                    b.remove_css_class("active-profile")
            self._refresh_ui()

        if not self.get_mapped():
            return True

        self.daemon_banner.set_revealed(not is_daemon_alive())

        rpms = self.fan_ctrl.get_rpms()
        self.card_fan1.set_value(str(rpms.get("fan1", 0)))
        self.card_fan2.set_value(str(rpms.get("fan2", 0)))

        temps = self.fan_ctrl.get_temperatures()
        cpu = int(temps.get("cpu", 0))
        gpu = int(temps.get("gpu", 0))

        self.card_cpu.set_value(str(cpu))
        self.card_gpu.set_value(str(gpu))
        set_temp_class(self.card_cpu.value_label, cpu)
        set_temp_class(self.card_gpu.value_label, gpu)

        control_temp = max(cpu, gpu)
        if max_fan:
            target_pct = 100
        elif p.is_manual:
            target_pct = p.manual_speed
        else:
            target_pct = get_target_pwm(
                control_temp,
                p.name,
                current_speed=self._effective_target,
                hysteresis=p.hysteresis,
            )
        self._effective_target = target_pct

        mode_tag = " [TURBO]" if max_fan else ""
        self.curve_point_lbl.set_label(f"Kontrol: {control_temp}°C → Hedef: %{target_pct}{mode_tag}")
        self.curve_area.update_state(
            p.name,
            p.is_manual,
            max_fan,
            p.manual_speed,
            p.hysteresis,
            control_temp,
            target_pct,
        )
        return True

    def _on_profile_clicked(self, _btn: Gtk.Button, name: str) -> None:
        self.flush_pending()
        self._effective_target = -1
        self.profiles.set_active(name)
        self._current_profile = name
        for n, b in self.buttons.items():
            if n == name:
                b.add_css_class("active-profile")
            else:
                b.remove_css_class("active-profile")
        self._refresh_ui()

    def _refresh_ui(self) -> None:
        self._updating = True
        p = self.profiles.active_profile
        max_fan = self.profiles.max_fan
        self.boost_switch.set_active(max_fan)
        self.manual_switch.set_active(p.is_manual)
        self.manual_switch.set_sensitive(not max_fan)
        self.slider.set_value(100 if max_fan else p.manual_speed)
        self.slider.set_sensitive(p.is_manual and not max_fan)
        self.hyst_row.set_value(p.hysteresis)
        self.hyst_row.set_sensitive((not p.is_manual) and (not max_fan))
        self._speed_val.set_label("100" if max_fan else str(int(p.manual_speed)))
        self._refresh_profile_descriptions()
        self._updating = False

    def _on_reset_clicked(self, _btn: Gtk.Button) -> None:
        self._slider_debouncer.cancel()
        self._hyst_debouncer.cancel()
        self._effective_target = -1
        self.profiles.reset_profile(self.profiles.active_profile.name)
        self._refresh_ui()
        self._update_dashboard()

    def _on_boost_toggled(self, _switch: Gtk.Switch, state: bool) -> bool:
        if self._updating:
            return False
        self.flush_pending()
        self._effective_target = -1
        self.profiles.set_max_fan(state)
        self._refresh_ui()
        self._update_dashboard()
        return False

    def _on_switch_toggled(self, _switch: Gtk.Switch, state: bool) -> bool:
        if self._updating:
            return False
        self._effective_target = -1
        self.slider.set_sensitive(state)
        self.hyst_row.set_sensitive(not state)
        p = self.profiles.active_profile
        self.profiles.update_manual(p.name, state, int(self.slider.get_value()))
        self._refresh_profile_descriptions()
        return False

    def _on_slider_changed(self, slider: Gtk.Scale) -> None:
        if self._updating:
            return
        val = int(slider.get_value())
        self._speed_val.set_label(str(val))
        self._slider_debouncer(self.profiles.active_profile.name, self.manual_switch.get_active(), val)

    def _commit_slider_speed(self, profile_name: str, is_manual: bool, speed: int) -> None:
        self.profiles.update_manual(profile_name, is_manual, speed)
        self._refresh_profile_descriptions()

    def _on_hysteresis_changed(self, spin_row: Adw.SpinRow, _pspec) -> None:
        if self._updating:
            return
        val = int(spin_row.get_value())
        self._hyst_debouncer(self.profiles.active_profile.name, val)

    def _commit_hysteresis(self, profile_name: str, hysteresis: int) -> None:
        self.profiles.update_hysteresis(profile_name, hysteresis)
