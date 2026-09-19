

import logging
import time
from typing import Optional
from vcontrol.backend.fan import get_controller
from vcontrol.backend.profiles import get_manager
from vcontrol.backend.fan_curves import get_target_pwm

logger = logging.getLogger(__name__)
WATCHDOG_INTERVAL_S = 2

class FanWatchdog:
    def __init__(self):
        self._enabled = False
        self._timer_id: Optional[int] = None
        self._fan = get_controller()
        self._profiles = get_manager()
        self._last_speed = -1

    @property
    def is_running(self) -> bool:
        return self._enabled and self._timer_id is not None

    def start(self):
        if self._enabled:
            return
        self._enabled = True
        self._schedule()
        logger.info("Akıllı Termal Motor başlatıldı.")

    def stop(self):
        self._enabled = False
        if self._timer_id is not None:
            try:
                from gi.repository import GLib
                GLib.source_remove(self._timer_id)
            except Exception:
                pass
            self._timer_id = None
        logger.info("Termal Motor durduruldu.")

    def _schedule(self):
        try:
            from gi.repository import GLib
            self._timer_id = GLib.timeout_add_seconds(WATCHDOG_INTERVAL_S, self._tick)
        except ImportError:
            import threading
            t = threading.Timer(WATCHDOG_INTERVAL_S, self._tick_thread)
            t.daemon = True
            t.start()

    def _tick(self) -> bool:
        if not self._enabled:
            return False
        self._apply_logic()
        return True

    def _tick_thread(self):
        if self._enabled:
            self._apply_logic()
            self._schedule()

    def _apply_logic(self):
        if not self._fan.available:
            logger.warning("NBFC is not available according to fan.py")
            return

        active_prof = self._profiles.active_profile
        mode_name = active_prof.name  
        is_manual = active_prof.is_manual
        manual_speed = active_prof.manual_speed

        if is_manual:
            target_speed = manual_speed
        else:
            temps = self._fan.get_temperatures()
            cpu_temp = temps.get("cpu", 0)
            target_speed = get_target_pwm(cpu_temp, mode_name)

        if target_speed != self._last_speed:
            ok = self._fan.set_fan_speed(target_speed)
            if ok:
                logger.info(f"Fan hızı NBFC üzerinden {target_speed} değerine ayarlandı.")
                self._last_speed = target_speed
            else:
                logger.error(f"NBFC fan ayarı başarısız oldu (hedef: {target_speed}).")
_watchdog = None
def get_watchdog() -> FanWatchdog:
    global _watchdog
    if _watchdog is None:
        _watchdog = FanWatchdog()
    return _watchdog
