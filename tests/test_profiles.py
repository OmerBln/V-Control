import os
import tempfile
import time
import unittest

from vcontrol.backend import daemon_status, profiles, settings


class TestProfiles(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.orig_config_dir = profiles.CONFIG_DIR
        self.orig_profiles_file = profiles.PROFILES_FILE
        profiles.CONFIG_DIR = self.tmp_dir.name
        profiles.PROFILES_FILE = os.path.join(self.tmp_dir.name, "profiles.json")

    def tearDown(self):
        profiles.CONFIG_DIR = self.orig_config_dir
        profiles.PROFILES_FILE = self.orig_profiles_file
        self.tmp_dir.cleanup()

    def test_save_and_load(self):
        pm = profiles.ProfileManager()
        pm.set_active("Eco")
        pm.update_manual("Eco", is_manual=True, speed=42)
        pm.update_hysteresis("Eco", 7)

        pm2 = profiles.ProfileManager()
        active = pm2.active_profile
        self.assertEqual(active.name, "Eco")
        self.assertTrue(active.is_manual)
        self.assertEqual(active.manual_speed, 42)
        self.assertEqual(active.hysteresis, 7)

    def test_settings_persistence(self):
        cfg_path = os.path.join(self.tmp_dir.name, "settings.json")
        s = settings.load_settings(cfg_path)
        self.assertEqual(s.theme, "system")
        self.assertIsNone(s.lighting)

        s.theme = "dark"
        s.lighting = settings.LightingState(brightness=180, red=10, green=20, blue=30)
        s.save()

        s2 = settings.load_settings(cfg_path)
        self.assertEqual(s2.theme, "dark")
        self.assertIsNotNone(s2.lighting)
        self.assertEqual(s2.lighting.brightness, 180)
        self.assertEqual((s2.lighting.red, s2.lighting.green, s2.lighting.blue), (10, 20, 30))

    def test_daemon_heartbeat(self):
        hb_path = os.path.join(self.tmp_dir.name, "hb.json")
        self.assertFalse(daemon_status.is_daemon_alive(hb_path))

        daemon_status.write_heartbeat(hb_path)
        self.assertTrue(daemon_status.is_daemon_alive(hb_path))

        # Stale heartbeat should report dead
        future = time.time() + daemon_status.HEARTBEAT_MAX_AGE_S + 5
        self.assertFalse(daemon_status.is_daemon_alive(hb_path, now=future))

        daemon_status.clear_heartbeat(hb_path)
        self.assertFalse(daemon_status.is_daemon_alive(hb_path))


if __name__ == "__main__":
    unittest.main()
