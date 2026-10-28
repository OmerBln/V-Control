import logging

from vcontrol.backend.fan import get_controller
from vcontrol.backend.fan_curves import get_target_pwm
from vcontrol.backend.profiles import get_manager
from vcontrol.backend.thermal_filter import ThermalFilter

logger = logging.getLogger(__name__)

WATCHDOG_INTERVAL_S = 2
SAMPLE_INTERVAL_MS = 500
CONTROL_WINDOW_S = 10.0
OVERHEAT_TEMP = 95
OVERHEAT_RELEASE_TEMP = 85
_OVERHEAT_CONFIRM_TICKS = 2
_SPINUP_TICKS = 2
_HOLD_TICKS = 6
_STOP_HOLD_TICKS = 15


class FanWatchdog:
    def __init__(self):
        self._enabled = False
        self._timer_id: int | None = None
        self._sample_timer_id: int | None = None
        self._fan = get_controller()
        self._profiles = get_manager()
        self._cpu_filter = ThermalFilter(CONTROL_WINDOW_S)
        self._last_speed = -1
        self._last_mode = None
        self._last_is_manual = None
        self._pending_up_speed = -1
        self._pending_up_count = 0
        self._hold_down_ticks = 0
        self._in_overheat = False
        self._overheat_confirm_count = 0
        self._has_control = False
        self._warned_unavailable = False
        self._warned_no_sensor = False

    @property
    def is_running(self) -> bool:
        return self._enabled and self._timer_id is not None

    def start(self):
        if self._enabled:
            return
        self._enabled = True
        self._schedule()
        logger.info("Smart Thermal Engine started.")

    def stop(self, restore_auto: bool = True):
        self._enabled = False
        for attr in ("_timer_id", "_sample_timer_id"):
            source_id = getattr(self, attr)
            if source_id is None:
                continue
            try:
                from gi.repository import GLib
                GLib.source_remove(source_id)
            except Exception as e:  # noqa: BLE001
                logger.debug(f"GLib timer cleanup: {e}")
            setattr(self, attr, None)

        if restore_auto and self._has_control:
            if self._fan.set_auto():
                logger.info("Fan control handed back to firmware (auto).")
            else:
                logger.error("Failed to restore firmware fan control.")
            self._has_control = False
        logger.info("Thermal Engine stopped.")

    def _schedule(self):
        try:
            from gi.repository import GLib
            self._sample_timer_id = GLib.timeout_add(SAMPLE_INTERVAL_MS, self._sample_tick)
            self._timer_id = GLib.timeout_add_seconds(WATCHDOG_INTERVAL_S, self._tick)
        except ImportError:
            import threading
            t = threading.Timer(WATCHDOG_INTERVAL_S, self._tick_thread)
            t.daemon = True
            t.start()

    def _sample_tick(self) -> bool:
        if not self._enabled:
            return False
        self._cpu_filter.add(self._fan.read_cpu_temp_raw())
        return True

    def _tick(self) -> bool:
        if not self._enabled:
            return False
        self._safe_apply()
        return True

    def _tick_thread(self):
        if self._enabled:
            self._safe_apply()
            self._schedule()

    def _safe_apply(self):
        try:
            self._apply_logic()
        except Exception:
            logger.exception("Thermal engine tick failed")

    def _reset_state(self):
        self._last_speed = -1
        self._pending_up_speed = -1
        self._pending_up_count = 0
        self._hold_down_ticks = 0

    def _update_overheat(self, temp: int):
        if self._in_overheat:
            if temp <= OVERHEAT_RELEASE_TEMP:
                self._in_overheat = False
                self._overheat_confirm_count = 0
                logger.info(f"Overheat protection released at {temp}°C.")
        elif temp >= OVERHEAT_TEMP:
            self._overheat_confirm_count += 1
            if self._overheat_confirm_count >= _OVERHEAT_CONFIRM_TICKS:
                self._in_overheat = True
                logger.warning(f"Overheat protection engaged at {temp}°C.")
            else:
                logger.debug(
                    f"Overheat candidate ({self._overheat_confirm_count}/"
                    f"{_OVERHEAT_CONFIRM_TICKS}) at {temp}°C."
                )
        else:
            self._overheat_confirm_count = 0

    def _rate_limit(self, curve_target: int) -> int:
        if self._last_speed == -1:
            self._pending_up_speed = -1
            self._pending_up_count = 0
            return curve_target

        if curve_target > self._last_speed:
            if curve_target > self._pending_up_speed:
                self._pending_up_speed = curve_target
                self._pending_up_count = 1
            else:
                self._pending_up_count += 1
            if self._pending_up_count < _SPINUP_TICKS:
                return self._last_speed
            self._pending_up_speed = -1
            self._pending_up_count = 0
            self._hold_down_ticks = _STOP_HOLD_TICKS if self._last_speed == 0 else _HOLD_TICKS
            return curve_target

        self._pending_up_speed = -1
        self._pending_up_count = 0
        if self._hold_down_ticks > 0:
            self._hold_down_ticks -= 1
            return self._last_speed
        return curve_target

    def _release_to_firmware(self):
        if self._has_control and self._fan.set_auto():
            self._has_control = False
        self._reset_state()

    def _apply_logic(self):
        if not self._fan.available:
            if not self._warned_unavailable:
                logger.warning("Fan controller is not available.")
                self._warned_unavailable = True
            return
        self._warned_unavailable = False

        active_prof = self._profiles.active_profile
        mode_name = active_prof.name
        is_manual = active_prof.is_manual
        hysteresis = getattr(active_prof, "hysteresis", 4)

        if mode_name != self._last_mode or is_manual != self._last_is_manual:
            self._reset_state()
            self._last_mode = mode_name
            self._last_is_manual = is_manual

        cpu_raw = cpu_temp = gpu_temp = control_temp = 0
        if is_manual:
            target_speed = max(0, min(100, int(active_prof.manual_speed)))
        else:
            cpu_raw = self._fan.read_cpu_temp_raw()
            if len(self._cpu_filter) == 0:
                self._cpu_filter.add(cpu_raw)
            cpu_temp = round(self._cpu_filter.value())
            gpu_temp = self._fan.read_gpu_temp()
            control_temp = max(cpu_temp, gpu_temp)

            if control_temp <= 0:
                if not self._warned_no_sensor:
                    logger.error("No valid temperature reading; falling back to firmware control.")
                    self._warned_no_sensor = True
                self._release_to_firmware()
                return
            self._warned_no_sensor = False

            self._update_overheat(control_temp)
            if self._in_overheat:
                target_speed = 100
                self._pending_up_speed = -1
                self._pending_up_count = 0
                self._hold_down_ticks = _HOLD_TICKS
            else:
                curve_target = get_target_pwm(
                    control_temp,
                    mode_name,
                    current_speed=self._last_speed,
                    hysteresis=hysteresis,
                )
                target_speed = self._rate_limit(curve_target)

        hw_reverted = self._has_control and not self._fan.is_manual_mode()
        if hw_reverted:
            logger.warning("Firmware took back fan control; re-applying.")

        if target_speed == self._last_speed and not hw_reverted:
            return

        if not self._fan.set_fan_speed(target_speed):
            logger.error(f"Fan write failed (target: {target_speed}%).")
            return

        self._has_control = True
        self._last_speed = target_speed
        if is_manual:
            logger.info(f"Fan speed set MANUAL to {target_speed}%.")
        else:
            crit_flag = " [OVERHEAT]" if self._in_overheat else ""
            logger.info(
                f"Fan speed -> {target_speed}% "
                f"(control: {control_temp}°C [CPU raw:{cpu_raw}°C filtered:{cpu_temp}°C "
                f"GPU:{gpu_temp}°C] | mode: {mode_name}){crit_flag}"
            )


_watchdog = None


def get_watchdog() -> FanWatchdog:
    global _watchdog
    if _watchdog is None:
        _watchdog = FanWatchdog()
    return _watchdog
