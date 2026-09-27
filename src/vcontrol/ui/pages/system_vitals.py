import time
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib, Gdk

from vcontrol.backend.fan import get_controller
from vcontrol.backend.sensors import update_history, get_history


GRAPH_POINTS = 60   # seconds of history shown
GRAPH_W = 560
GRAPH_H = 120


class _GraphArea(Gtk.DrawingArea):
    """Simple line graph drawn with Cairo."""

    def __init__(self, color_r: float, color_g: float, color_b: float):
        super().__init__()
        self._color = (color_r, color_g, color_b)
        self._values: list[float] = []
        self.set_content_width(GRAPH_W)
        self.set_content_height(GRAPH_H)
        self.set_hexpand(True)
        self.set_draw_func(self._draw)

    def push(self, value: float):
        self._values.append(value)
        if len(self._values) > GRAPH_POINTS:
            self._values.pop(0)
        self.queue_draw()

    def _draw(self, area, cr, w, h):
        if not self._values:
            return

        cr.set_source_rgba(1, 1, 1, 0.04)
        cr.rectangle(0, 0, w, h)
        cr.fill()

        vals = self._values
        max_v = max(max(vals), 100)

        r, g, b = self._color

        # Filled area
        cr.move_to(0, h)
        for i, v in enumerate(vals):
            x = i / (GRAPH_POINTS - 1) * w
            y = h - (v / max_v) * (h - 8)
            cr.line_to(x, y)
        cr.line_to((len(vals) - 1) / (GRAPH_POINTS - 1) * w, h)
        cr.close_path()
        cr.set_source_rgba(r, g, b, 0.12)
        cr.fill()

        # Line
        cr.move_to(0, h - (vals[0] / max_v) * (h - 8))
        for i, v in enumerate(vals[1:], 1):
            x = i / (GRAPH_POINTS - 1) * w
            y = h - (v / max_v) * (h - 8)
            cr.line_to(x, y)
        cr.set_source_rgba(r, g, b, 0.85)
        cr.set_line_width(2)
        cr.stroke()

        # Current value label
        last = vals[-1]
        cr.set_source_rgba(r, g, b, 1.0)
        cr.select_font_face("Sans", 0, 1)
        cr.set_font_size(13)
        cr.move_to(w - 52, 18)
        cr.show_text(f"{last:.0f}°C")


class SystemVitalsPage(Gtk.ScrolledWindow):
    def __init__(self):
        super().__init__()
        self.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._fan = get_controller()

        clamp = Adw.Clamp()
        clamp.set_maximum_size(680)
        clamp.set_margin_top(28)
        clamp.set_margin_bottom(28)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)

        # ── Live stat bar ──────────────────────────────────────
        stat_grid = Gtk.Grid(column_spacing=12, row_spacing=12)
        stat_grid.set_column_homogeneous(True)

        self._lbl_cpu  = self._make_stat("CPU", "0°C", "#4f9cf9")
        self._lbl_gpu  = self._make_stat("GPU", "0°C", "#9d7df0")
        self._lbl_nvme = self._make_stat("NVMe", "0°C", "#2dd4bf")
        self._lbl_f1   = self._make_stat("Fan 1", "0 RPM", "#00d4ff")
        self._lbl_f2   = self._make_stat("Fan 2", "0 RPM", "#00d4ff")

        stat_grid.attach(self._lbl_cpu["box"],  0, 0, 1, 1)
        stat_grid.attach(self._lbl_gpu["box"],  1, 0, 1, 1)
        stat_grid.attach(self._lbl_nvme["box"], 2, 0, 1, 1)
        stat_grid.attach(self._lbl_f1["box"],   0, 1, 1, 1)
        stat_grid.attach(self._lbl_f2["box"],   1, 1, 1, 1)
        root.append(stat_grid)

        # ── Graphs ────────────────────────────────────────────
        self._graph_cpu = self._make_graph_card("CPU Sıcaklığı", 0.31, 0.61, 0.98)
        self._graph_gpu = self._make_graph_card("GPU Sıcaklığı", 0.62, 0.49, 0.94)
        root.append(self._graph_cpu["card"])
        root.append(self._graph_gpu["card"])

        clamp.set_child(root)
        self.set_child(clamp)

        GLib.timeout_add(1000, self._tick)

    def _make_stat(self, title: str, val: str, color: str) -> dict:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.add_css_class("dashboard-card")

        t = Gtk.Label(label=title)
        t.add_css_class("dashboard-title")
        t.set_xalign(0)

        v = Gtk.Label(label=val)
        v.add_css_class("dashboard-value")
        v.set_xalign(0)
        v.set_markup(f'<span foreground="{color}">{val}</span>')

        box.append(t)
        box.append(v)
        return {"box": box, "val": v, "color": color}

    def _make_graph_card(self, title: str, r: float, g: float, b: float) -> dict:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card.add_css_class("vitals-graph-card")

        lbl = Gtk.Label(label=title)
        lbl.add_css_class("vitals-graph-title")
        lbl.set_xalign(0)

        area = _GraphArea(r, g, b)

        card.append(lbl)
        card.append(area)
        return {"card": card, "area": area}

    def _set_stat(self, widget: dict, val: str):
        widget["val"].set_markup(f'<span foreground="{widget["color"]}">{val}</span>')

    def _tick(self) -> bool:
        reading = update_history()
        rpms = self._fan.get_rpms()

        self._set_stat(self._lbl_cpu,  f"{reading.cpu_temp:.0f}°C")
        self._set_stat(self._lbl_gpu,  f"{reading.gpu_temp:.0f}°C")
        self._set_stat(self._lbl_nvme, f"{reading.nvme_temp:.0f}°C")
        self._set_stat(self._lbl_f1,   f"{rpms.get('fan1', 0)} RPM")
        self._set_stat(self._lbl_f2,   f"{rpms.get('fan2', 0)} RPM")

        self._graph_cpu["area"].push(reading.cpu_temp)
        self._graph_gpu["area"].push(reading.gpu_temp)

        return True
