import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from vcontrol.backend import profiles
from vcontrol.backend.fan import FanController
from vcontrol.backend.fan_curves import get_curve, get_target_pwm
from vcontrol.backend.sysfs import atomic_write_json, clamp
from vcontrol.backend.thermal_filter import ThermalFilter
from vcontrol.backend.watchdog import FanWatchdog


class TestThermalFilter(unittest.TestCase):
    def test_filter_removes_idle_spikes(self):
        f = ThermalFilter(window_s=10.0, trim_ratio=0.2)
        for i in range(20):
            temp = 95.0 if i in (3, 11) else 52.0
            f.add(temp, now=i * 0.5)

        val = f.value(now=10.0)
        self.assertLess(val, 55.0)
        self.assertGreaterEqual(val, 52.0)

    def test_filter_reflects_sustained_heat(self):
        f = ThermalFilter(window_s=10.0, trim_ratio=0.2)
        for i in range(20):
            f.add(85.0, now=i * 0.5)

        val = f.value(now=10.0)
        self.assertAlmostEqual(val, 85.0, places=1)

    def test_filter_prunes_old_samples(self):
        f = ThermalFilter(window_s=5.0, trim_ratio=0.2)
        f.add(90.0, now=1.0)
        f.add(90.0, now=2.0)
        f.add(50.0, now=9.0)
        f.add(50.0, now=10.0)
        val = f.value(now=10.0)
        self.assertAlmostEqual(val, 50.0, places=1)


class TestFanCurves(unittest.TestCase):
    def test_idle_temperatures(self):
        self.assertEqual(get_target_pwm(50, "Eco"), 0)
        self.assertEqual(get_target_pwm(50, "Balanced"), 30)
        self.assertEqual(get_target_pwm(50, "Performance"), 35)

    def test_progressive_scaling(self):
        self.assertLessEqual(get_target_pwm(60, "Balanced"), 45)
        self.assertLessEqual(get_target_pwm(70, "Balanced"), 60)

    def test_hysteresis(self):
        speed = get_target_pwm(73, "Balanced", current_speed=60, hysteresis=4)
        self.assertEqual(speed, 60)

    def test_eco_hysteresis(self):
        speed = get_target_pwm(50, "Eco", current_speed=30, hysteresis=6)
        self.assertEqual(speed, 30)
        speed_off = get_target_pwm(48, "Eco", current_speed=30, hysteresis=6)
        self.assertEqual(speed_off, 0)

    def test_get_curve_fallback(self):
        self.assertEqual(get_curve("Unknown"), get_curve("Balanced"))

    def test_cpu_zero_sensor_no_recursion(self):
        # B1 regression test: if core sensors exist but read 0, read_cpu_temp_raw
        # must return 0 without raising RecursionError.
        with tempfile.TemporaryDirectory() as tmp:
            zero_file = os.path.join(tmp, "temp1_input")
            with open(zero_file, "w") as f:
                f.write("0\n")

            ctrl = FanController()
            ctrl._cpu_core_paths = [zero_file]
            ctrl._cpu_pkg_path = zero_file
            ctrl._cpu_temp_path = zero_file
            with patch.object(ctrl, "_find_cpu_sensors", lambda: None):
                self.assertEqual(ctrl.read_cpu_temp_raw(), 0)

    def test_sysfs_helpers(self):
        self.assertEqual(clamp("42", 0, 100, 50), 42)
        self.assertEqual(clamp(150, 0, 100, 50), 100)
        self.assertEqual(clamp(-5, 0, 100, 50), 0)
        self.assertEqual(clamp("bad", 0, 100, 50), 50)

        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "nested", "data.json")
            self.assertTrue(atomic_write_json(target, {"ok": True, "val": 7}))
            with open(target, encoding="utf-8") as f:
                self.assertEqual(json.load(f), {"ok": True, "val": 7})

    def test_watchdog_max_fan_boost(self):
        orig_dir = profiles.CONFIG_DIR
        orig_file = profiles.PROFILES_FILE
        with tempfile.TemporaryDirectory() as tmp:
            try:
                profiles.CONFIG_DIR = tmp
                profiles.PROFILES_FILE = os.path.join(tmp, "profiles.json")
                pm = profiles.ProfileManager()
                pm.set_active("Balanced")
                pm.set_max_fan(True)

                mock_fan = MagicMock()
                mock_fan.available = True
                mock_fan.is_manual_mode.return_value = True
                mock_fan.set_fan_speed.return_value = True
                mock_fan.read_cpu_temp_raw.return_value = 50
                mock_fan.read_gpu_temp.return_value = 40

                with (
                    patch("vcontrol.backend.watchdog.get_controller", return_value=mock_fan),
                    patch("vcontrol.backend.watchdog.get_manager", return_value=pm),
                ):
                    wd = FanWatchdog()
                    wd._apply_logic()
                    mock_fan.set_fan_speed.assert_called_with(100)

                    pm.set_max_fan(False)
                    wd._apply_logic()
                    mock_fan.set_fan_speed.assert_called_with(30)
            finally:
                profiles.CONFIG_DIR = orig_dir
                profiles.PROFILES_FILE = orig_file


if __name__ == "__main__":
    unittest.main()
