import unittest

from vcontrol.backend.fan_curves import get_target_pwm
from vcontrol.backend.thermal_filter import ThermalFilter


class TestThermalFilter(unittest.TestCase):
    def test_filter_removes_idle_spikes(self):
        f = ThermalFilter(window_s=10.0, trim_ratio=0.2)
        # Simulate 10 seconds of 500ms samples: mostly 52°C with occasional 95°C spikes
        for i in range(20):
            temp = 95.0 if i in (3, 11) else 52.0
            f.add(temp, now=i * 0.5)

        val = f.value(now=10.0)
        # Spikes should be trimmed out, leaving close to 52°C
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
        # Now at t=10.0, samples from t=1 and t=2 should be pruned
        f.add(50.0, now=9.0)
        f.add(50.0, now=10.0)
        val = f.value(now=10.0)
        self.assertAlmostEqual(val, 50.0, places=1)


class TestFanCurves(unittest.TestCase):
    def test_idle_temperatures(self):
        # At 50°C idle, Eco should be 0%, Balanced 20%, Performance 35%
        self.assertEqual(get_target_pwm(50, "Eco"), 0)
        self.assertEqual(get_target_pwm(50, "Balanced"), 20)
        self.assertEqual(get_target_pwm(50, "Performance"), 35)

    def test_progressive_scaling(self):
        # 60°C should produce moderate fan speeds, never 100%
        self.assertLessEqual(get_target_pwm(60, "Balanced"), 45)
        self.assertLessEqual(get_target_pwm(70, "Balanced"), 60)

    def test_hysteresis(self):
        # Once at 75°C (speed=60 in Balanced), temperature drops to 73°C (within hysteresis 4)
        speed = get_target_pwm(73, "Balanced", current_speed=60, hysteresis=4)
        self.assertEqual(speed, 60)


if __name__ == "__main__":
    unittest.main()
