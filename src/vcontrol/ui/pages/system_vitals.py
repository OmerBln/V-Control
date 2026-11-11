import gi
import psutil

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

from vcontrol.backend.fan import get_controller
from vcontrol.backend.sensors import update_history
from vcontrol.ui.util import set_temp_class
from vcontrol.ui.widgets import BLUE, CYAN, GREEN, ORANGE, PURPLE, GraphCard, MetricCard


class SystemVitalsPage(Gtk.ScrolledWindow):
    def __init__(self):
        super().__init__()
        self.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._fan = get_controller()

        clamp = Adw.Clamp()
        clamp.set_maximum_size(680)
        clamp.set_tightening_threshold(420)
        clamp.set_margin_top(24)
        clamp.set_margin_bottom(28)
        clamp.set_margin_start(16)
        clamp.set_margin_end(16)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)

        # ── Live stat grid ─────────────────────────────────────
        stat_grid = Gtk.Grid(column_spacing=12, row_spacing=12)
        stat_grid.set_column_homogeneous(True)

        self._card_cpu = MetricCard("🌡", "CPU Sıcaklığı", "°C", "temp-cool")
        self._card_gpu = MetricCard("⚡", "GPU Sıcaklığı", "°C", "temp-cool")
        self._card_nvme = MetricCard("💾", "NVMe Disk", "°C", "temp-cool")
        self._card_cpu_load = MetricCard("🧮", "CPU Kullanımı", "%", "val-cpu")
        self._card_ram = MetricCard("🧠", "Bellek (RAM)", "%", "val-gpu")
        self._card_f1 = MetricCard("🌀", "Fan 1", "RPM", "val-rpm")
        self._card_f2 = MetricCard("🌀", "Fan 2", "RPM", "val-rpm")

        stat_grid.attach(self._card_cpu, 0, 0, 1, 1)
        stat_grid.attach(self._card_gpu, 1, 0, 1, 1)
        stat_grid.attach(self._card_nvme, 2, 0, 1, 1)
        stat_grid.attach(self._card_cpu_load, 0, 1, 1, 1)
        stat_grid.attach(self._card_ram, 1, 1, 1, 1)
        stat_grid.attach(self._card_f1, 2, 1, 1, 1)
        stat_grid.attach(self._card_f2, 0, 2, 3, 1)
        root.append(stat_grid)

        # ── Multi-series graphs ────────────────────────────────
        self._graph_temp = GraphCard(
            "Sıcaklık Geçmişi",
            [("CPU", BLUE), ("GPU", PURPLE), ("NVMe", GREEN)],
            unit="°C",
            fixed_max=100.0,
        )
        self._graph_load = GraphCard(
            "Sistem Yükü",
            [("CPU", ORANGE), ("RAM", PURPLE)],
            unit="%",
            fixed_max=100.0,
        )
        self._graph_fan = GraphCard(
            "Fan Devir Hızı",
            [("Fan 1", CYAN), ("Fan 2", BLUE)],
            unit="RPM",
            fixed_max=None,
        )

        root.append(self._graph_temp)
        root.append(self._graph_load)
        root.append(self._graph_fan)

        clamp.set_child(root)
        self.set_child(clamp)

        self._tick()
        GLib.timeout_add(1000, self._tick)

    def _tick(self) -> bool:
        if not self.get_root():
            return False

        reading = update_history()
        rpms = self._fan.get_rpms()
        cpu_pct = psutil.cpu_percent(interval=None)
        ram_pct = psutil.virtual_memory().percent
        f1 = float(rpms.get("fan1", 0))
        f2 = float(rpms.get("fan2", 0))

        self._graph_temp.push([reading.cpu_temp, reading.gpu_temp, reading.nvme_temp])
        self._graph_load.push([cpu_pct, ram_pct])
        self._graph_fan.push([f1, f2])

        if not self.get_mapped():
            return True

        self._card_cpu.set_value(f"{reading.cpu_temp:.0f}")
        self._card_gpu.set_value(f"{reading.gpu_temp:.0f}")
        self._card_nvme.set_value(f"{reading.nvme_temp:.0f}")
        self._card_cpu_load.set_value(f"{cpu_pct:.0f}")
        self._card_ram.set_value(f"{ram_pct:.0f}")
        self._card_f1.set_value(f"{int(f1)}")
        self._card_f2.set_value(f"{int(f2)}")

        set_temp_class(self._card_cpu.value_label, reading.cpu_temp)
        set_temp_class(self._card_gpu.value_label, reading.gpu_temp)
        set_temp_class(self._card_nvme.value_label, reading.nvme_temp)
        return True
