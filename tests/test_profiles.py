import os
import tempfile
import unittest

from vcontrol.backend import profiles


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

        pm2 = profiles.ProfileManager()
        active = pm2.active_profile
        self.assertEqual(active.name, "Eco")
        self.assertTrue(active.is_manual)
        self.assertEqual(active.manual_speed, 42)


if __name__ == "__main__":
    unittest.main()
