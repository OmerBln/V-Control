import math
from collections import deque

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

Color = tuple[float, float, float]

# Series colours, matching the accent tokens in style.css
BLUE: Color = (0.31, 0.61, 0.98)
PURPLE: Color = (0.62, 0.49, 0.94)
CYAN: Color = (0.0, 0.83, 1.0)
GREEN: Color = (0.18, 0.83, 0.75)
ORANGE: Color = (0.98, 0.57, 0.24)


def _fg(widget: Gtk.Widget) -> tuple[float, float, float]:
    c = widget.get_color()
    return c.red, c.green, c.blue


class MetricCard(Gtk.Box):
    def __init__(self, icon: str, title: str, unit: str, value_class: str | None = None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.add_css_class("dashboard-card")

        header = Gtk.Box(spacing=8)
        icon_lbl = Gtk.Label(label=icon)
        icon_lbl.add_css_class("dashboard-card-icon")
        title_lbl = Gtk.Label(label=title, xalign=0)
        title_lbl.add_css_class("dashboard-title")
        header.append(icon_lbl)
        header.append(title_lbl)

        val_box = Gtk.Box()
        self.value_label = Gtk.Label(label="–")
        self.value_label.add_css_class("dashboard-value")
        if value_class:
            self.value_label.add_css_class(value_class)
        unit_lbl = Gtk.Label(label=unit, valign=Gtk.Align.END)
        unit_lbl.add_css_class("dashboard-unit")
        val_box.append(self.value_label)
        val_box.append(unit_lbl)

        self.append(header)
        self.append(val_box)

    def set_value(self, text: str) -> None:
        if self.value_label.get_label() != text:
            self.value_label.set_label(text)


class _ColorDot(Gtk.DrawingArea):
    def __init__(self, color: Color, size: int = 10):
        super().__init__()
        self._color = color
        self.set_content_width(size)
        self.set_content_height(size)
        self.set_valign(Gtk.Align.CENTER)
        self.set_draw_func(self._draw)

    def _draw(self, _area, cr, w, h):
        cr.set_source_rgb(*self._color)
        cr.arc(w / 2, h / 2, min(w, h) / 2, 0, 2 * math.pi)
        cr.fill()


class LineGraph(Gtk.DrawingArea):
    """Multi-series line graph with grid and axis labels, drawn with Cairo."""

    MARGIN_LEFT = 40
    MARGIN_BOTTOM = 18
    MARGIN_TOP = 6

    def __init__(
        self,
        colors: list[Color],
        unit: str,
        fixed_max: float | None = 100.0,
        points: int = 60,
        height: int = 130,
    ):
        super().__init__()
        self._colors = colors
        self._unit = unit
        self._fixed_max = fixed_max
        self._points = points
        self._series: list[deque[float]] = [deque(maxlen=points) for _ in colors]
        self.set_content_height(height)
        self.set_hexpand(True)
        self.set_draw_func(self._draw)

    def push(self, values: list[float]) -> None:
        for series, value in zip(self._series, values):
            series.append(max(0.0, float(value)))
        if self.get_mapped():
            self.queue_draw()

    def _scale_max(self) -> float:
        if self._fixed_max is not None:
            peak = max((max(s) for s in self._series if s), default=0.0)
            return max(self._fixed_max, peak)
        peak = max((max(s) for s in self._series if s), default=0.0)
        return max(1000.0, math.ceil(peak / 1000.0) * 1000.0)

    def _draw(self, _area, cr, w, h):
        fr, fg, fb = _fg(self)
        left, top = self.MARGIN_LEFT, self.MARGIN_TOP
        plot_w = max(1, w - left - 4)
        plot_h = max(1, h - top - self.MARGIN_BOTTOM)
        vmax = self._scale_max()

        cr.select_font_face("Sans", 0, 0)
        cr.set_font_size(10)
        cr.set_line_width(1)

        # Horizontal grid + y labels
        for i in range(5):
            frac = i / 4
            y = top + plot_h - frac * plot_h
            cr.set_source_rgba(fr, fg, fb, 0.08 if i else 0.18)
            cr.move_to(left, round(y) + 0.5)
            cr.line_to(left + plot_w, round(y) + 0.5)
            cr.stroke()
            label = f"{vmax * frac:.0f}"
            ext = cr.text_extents(label)
            cr.set_source_rgba(fr, fg, fb, 0.45)
            cr.move_to(left - ext.width - 6, y + ext.height / 2)
            cr.show_text(label)

        # X labels
        cr.set_source_rgba(fr, fg, fb, 0.45)
        cr.move_to(left, h - 4)
        cr.show_text(f"{self._points} sn")
        now_lbl = "şimdi"
        ext = cr.text_extents(now_lbl)
        cr.move_to(left + plot_w - ext.width, h - 4)
        cr.show_text(now_lbl)

        step = plot_w / max(1, self._points - 1)
        for series, (r, g, b) in zip(self._series, self._colors):
            if len(series) < 2:
                continue
            vals = list(series)
            x0 = left + (self._points - len(vals)) * step

            def pt(i, v, x0=x0):
                return x0 + i * step, top + plot_h - (v / vmax) * plot_h

            # Fill
            cr.move_to(x0, top + plot_h)
            for i, v in enumerate(vals):
                cr.line_to(*pt(i, v))
            cr.line_to(pt(len(vals) - 1, 0)[0], top + plot_h)
            cr.close_path()
            cr.set_source_rgba(r, g, b, 0.10)
            cr.fill()

            # Line
            cr.move_to(*pt(0, vals[0]))
            for i, v in enumerate(vals[1:], 1):
                cr.line_to(*pt(i, v))
            cr.set_source_rgba(r, g, b, 0.9)
            cr.set_line_width(2)
            cr.stroke()
            cr.set_line_width(1)


class GraphCard(Gtk.Box):
    """Titled card containing a LineGraph and a live legend."""

    def __init__(
        self,
        title: str,
        series: list[tuple[str, Color]],
        unit: str,
        fixed_max: float | None = 100.0,
        value_format: str = "{:.0f}",
    ):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.add_css_class("vitals-graph-card")
        self._unit = unit
        self._fmt = value_format

        header = Gtk.Box(spacing=16)
        title_lbl = Gtk.Label(label=title, xalign=0, hexpand=True)
        title_lbl.add_css_class("vitals-graph-title")
        header.append(title_lbl)

        self._legend_values: list[Gtk.Label] = []
        for name, color in series:
            item = Gtk.Box(spacing=6)
            item.append(_ColorDot(color))
            name_lbl = Gtk.Label(label=name)
            name_lbl.add_css_class("graph-legend-name")
            val_lbl = Gtk.Label(label="–")
            val_lbl.add_css_class("graph-legend-value")
            item.append(name_lbl)
            item.append(val_lbl)
            header.append(item)
            self._legend_values.append(val_lbl)

        self.graph = LineGraph([c for _, c in series], unit, fixed_max)
        self.append(header)
        self.append(self.graph)

    def push(self, values: list[float]) -> None:
        self.graph.push(values)
        for lbl, v in zip(self._legend_values, values):
            lbl.set_label(f"{self._fmt.format(v)} {self._unit}")

