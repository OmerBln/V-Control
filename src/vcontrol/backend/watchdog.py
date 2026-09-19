import logging
import time
from collections import deque
from typing import Optional
from vcontrol.backend.fan import get_controller
from vcontrol.backend.profiles import get_manager
from vcontrol.backend.fan_curves import get_target_pwm, CRITICAL_TEMP

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
        self._temp_history = deque(maxlen=3)
        self._pending_up_speed = -1
        self._pending_up_count = 0
        self._hold_down_ticks = 0

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

        # Mod veya manuel kontrol değiştiyse tüm durumları sıfırla ki kullanıcı tercihi anında uygulansın
        if mode_name != self._last_mode or is_manual != self._last_is_manual:
            self._last_speed = -1
            self._last_mode = mode_name
            self._last_is_manual = is_manual
            self._pending_up_speed = -1
            self._pending_up_count = 0
            self._hold_down_ticks = 0
            self._temp_history.clear()

        if is_manual:
            target_speed = manual_speed
            raw_temp = 0
            smooth_temp = 0
            cpu_temp = 0
            gpu_temp = 0
        else:
            temps = self._fan.get_temperatures()
            cpu_temp = temps.get("cpu", 0)
            gpu_temp = temps.get("gpu", 0)
            raw_temp = max(cpu_temp, gpu_temp)

            # 1. Sıcaklık Yumuşatma (Hareketli Ortalama):
            # Anlık 200ms-1sn'lik turbo boost tepe noktalarını filtreler
            self._temp_history.append(raw_temp)
            smooth_temp = round(sum(self._temp_history) / len(self._temp_history))

            # 2. Kritik Donanım Koruması (Gerçek acil durum: >= 88°C)
            if raw_temp >= CRITICAL_TEMP:
                curve_target = 100
                self._pending_up_speed = -1
                self._pending_up_count = 0
                self._hold_down_ticks = 4
                target_speed = 100
            else:
                curve_target = get_target_pwm(
                    smooth_temp, 
                    mode_name, 
                    current_speed=self._last_speed, 
                    hysteresis=hysteresis
                )

                # İlk başlatma / sıfırlama anı
                if self._last_speed == -1:
                    target_speed = curve_target
                    self._pending_up_speed = -1
                    self._pending_up_count = 0
                # 3. Yükselme Gecikmesi / Doğrulaması (Spin-up delay):
                # Sıcaklık yükseldiğinde tek bir anlık ölçümde hemen devir fırlatmaz,
                # yüksek sıcaklığın en az 2 ölçüm (4 saniye) boyunca devam ettiğini doğrular
                elif curve_target > self._last_speed:
                    if curve_target != self._pending_up_speed:
                        self._pending_up_speed = curve_target
                        self._pending_up_count = 1
                        target_speed = self._last_speed  # Bekle, hemen yükseltme
                    else:
                        self._pending_up_count += 1
                        if self._pending_up_count < 2:
                            target_speed = self._last_speed
                        else:
                            # Isınma kalıcı, fan devrini yükselt ve soğuma bekleme süresini başlat
                            target_speed = curve_target
                            self._hold_down_ticks = 4  # En az 8 sn bu devirde kal
                # 4. Soğuma Bekleme Süresi (Spin-down hold):
                # Fan hızlandıktan sonra sıcaklık aniden düşerse hemen devir düşürüp
                # 1 saniye sonra tekrar yükselmesini (ses dalgalanmasını) engellemek için
                # en az 8 saniye boyunca mevcut devri korur
                elif curve_target < self._last_speed:
                    self._pending_up_speed = -1
                    self._pending_up_count = 0
                    if self._hold_down_ticks > 0:
                        self._hold_down_ticks -= 1
                        target_speed = self._last_speed  # Hızı koru
                    else:
                        target_speed = curve_target
                else:
                    self._pending_up_speed = -1
                    self._pending_up_count = 0
                    if self._hold_down_ticks > 0:
                        self._hold_down_ticks -= 1
                    target_speed = self._last_speed

        if target_speed != self._last_speed:
            ok = self._fan.set_fan_speed(target_speed)
            if ok:
                if is_manual:
                    logger.info(f"Fan hızı MANUEL olarak %{target_speed} değerine ayarlandı.")
                else:
                    crit_flag = " [ACİL KORUMA %100]" if raw_temp >= CRITICAL_TEMP else ""
                    logger.info(
                        f"Fan hızı ayarlandı: %{target_speed} (Ölçülen: {raw_temp}°C [CPU:{cpu_temp}°C, GPU:{gpu_temp}°C], "
                        f"Yumuşatılmış: {smooth_temp}°C | Mod: {mode_name} | Tolerans: {hysteresis}°C){crit_flag}"
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
