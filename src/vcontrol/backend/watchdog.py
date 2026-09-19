import logging
import time
from typing import Optional
from vcontrol.backend.fan import get_controller
from vcontrol.backend.profiles import get_manager
from vcontrol.backend.fan_curves import get_target_pwm, PROTECTION_TEMP

logger = logging.getLogger(__name__)
WATCHDOG_INTERVAL_S = 2

class FanWatchdog:
    def __init__(self):
        self._enabled = False
        self._timer_id: Optional[int] = None
        self._fan = get_controller()
        self._profiles = get_manager()
        self._last_speed = -1
        self._last_mode = None
        self._last_is_manual = None
        self._pending_up_speed = -1
        self._pending_up_count = 0

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
        hysteresis = getattr(active_prof, "hysteresis", 4)

        # Mod veya manuel kontrol değiştiyse son hızı ve bekleyen durumu sıfırla
        if mode_name != self._last_mode or is_manual != self._last_is_manual:
            self._last_speed = -1
            self._last_mode = mode_name
            self._last_is_manual = is_manual
            self._pending_up_speed = -1
            self._pending_up_count = 0

        if is_manual:
            target_speed = manual_speed
            cur_temp = 0
            cpu_temp = 0
            gpu_temp = 0
        else:
            temps = self._fan.get_temperatures()
            cpu_temp = temps.get("cpu", 0)
            gpu_temp = temps.get("gpu", 0)
            cur_temp = max(cpu_temp, gpu_temp)
            target_speed = get_target_pwm(
                cur_temp, 
                mode_name, 
                current_speed=self._last_speed, 
                hysteresis=hysteresis
            )

        # 70°C altı için zaman toleransı (anlık 1 sn'lik turbo spike'ları filtreleme)
        # 70°C ve üzerinde donanım koruması için gecikmesiz derhal uygulanır
        if not is_manual and self._last_speed != -1 and target_speed > self._last_speed:
            if cur_temp < PROTECTION_TEMP:
                # 70°C altında tepe noktasının kalıcı olduğunu doğrula (en az 2 ölçüm / 4 sn)
                if target_speed != self._pending_up_speed:
                    self._pending_up_speed = target_speed
                    self._pending_up_count = 1
                    return
                else:
                    self._pending_up_count += 1
                    if self._pending_up_count < 2:
                        return
            # 70°C ve üzeri ise bekleme yapmadan hemen uygula
            self._pending_up_speed = -1
            self._pending_up_count = 0
        else:
            self._pending_up_speed = -1
            self._pending_up_count = 0

        if target_speed != self._last_speed:
            ok = self._fan.set_fan_speed(target_speed)
            if ok:
                if is_manual:
                    logger.info(f"Fan hızı MANUEL olarak %{target_speed} değerine ayarlandı.")
                else:
                    protection_flag = " [KORUMA MODU - GECİKMESİZ]" if cur_temp >= PROTECTION_TEMP else ""
                    logger.info(
                        f"Fan hızı {cur_temp}°C (CPU: {cpu_temp}°C, GPU: {gpu_temp}°C | "
                        f"Mod: {mode_name} | Tolerans: {hysteresis}°C){protection_flag} -> %{target_speed} ayarlandı."
                    )
                self._last_speed = target_speed
            else:
                logger.error(f"NBFC fan ayarı başarısız oldu (hedef: {target_speed}).")

_watchdog = None
def get_watchdog() -> FanWatchdog:
    global _watchdog
    if _watchdog is None:
        _watchdog = FanWatchdog()
    return _watchdog
