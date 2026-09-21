import logging
import statistics
from collections import deque
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
        self._last_mode = None
        self._last_is_manual = None
        self._temp_history: deque[int] = deque(maxlen=5)

        # Spin-up: target must be stable for SPINUP_TICKS ticks before applying
        self._pending_up_speed = -1
        self._pending_up_count = 0
        SPINUP_TICKS = 2   # 2 ticks × 2 s = 4 s confirmation window

        # Spin-down: hold current speed for HOLD_TICKS ticks after a rise
        self._hold_down_ticks = 0
        HOLD_TICKS = 4     # 4 ticks × 2 s = 8 s hold period

        self._SPINUP_TICKS = SPINUP_TICKS
        self._HOLD_TICKS = HOLD_TICKS

    @property
    def is_running(self) -> bool:
        return self._enabled and self._timer_id is not None

    def start(self):
        if self._enabled:
            return
        self._enabled = True
        self._schedule()
        logger.info("Smart Thermal Engine started.")

    def stop(self):
        self._enabled = False
        if self._timer_id is not None:
            try:
                from gi.repository import GLib
                GLib.source_remove(self._timer_id)
            except Exception:
                pass
            self._timer_id = None
        logger.info("Thermal Engine stopped.")

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

    def _reset_state(self):
        """Reset all transient state when profile or mode changes."""
        self._last_speed = -1
        self._pending_up_speed = -1
        self._pending_up_count = 0
        self._hold_down_ticks = 0
        self._temp_history.clear()

    def _apply_logic(self):
        if not self._fan.available:
            logger.warning("Fan controller is not available.")
            return

        active_prof = self._profiles.active_profile
        mode_name = active_prof.name
        is_manual = active_prof.is_manual
        manual_speed = active_prof.manual_speed
        hysteresis = getattr(active_prof, "hysteresis", 4)

        # Reset all state when profile or control mode changes
        if mode_name != self._last_mode or is_manual != self._last_is_manual:
            self._reset_state()
            self._last_mode = mode_name
            self._last_is_manual = is_manual

        if is_manual:
            target_speed = manual_speed
            raw_temp = filtered_temp = cpu_temp = gpu_temp = 0
        else:
            temps = self._fan.get_temperatures()
            cpu_temp = temps.get("cpu", 0)
            gpu_temp = temps.get("gpu", 0)
            raw_temp = max(cpu_temp, gpu_temp)

            # 1. Median filter (5-sample sliding window):
            #    Eliminates single-sample sensor spikes (e.g. 95 °C blip on 50 °C baseline)
            self._temp_history.append(raw_temp)
            filtered_temp = int(round(statistics.median(self._temp_history)))

            # 2. Determine target from curve (using filtered temperature)
            curve_target = get_target_pwm(
                filtered_temp,
                mode_name,
                current_speed=self._last_speed,
                hysteresis=hysteresis,
            )

            # 3. Hardware protection: bypass all delays at critical temperature
            if filtered_temp >= 70:
                curve_target = 100

            # ---- First-run: apply immediately ----
            if self._last_speed == -1:
                target_speed = curve_target
                self._pending_up_speed = -1
                self._pending_up_count = 0

            # ---- Speed increase: require SPINUP_TICKS consecutive confirmations ----
            elif curve_target > self._last_speed:
                if curve_target > self._pending_up_speed:
                    # New higher target — restart confirmation counter
                    # (use > instead of != so oscillation between two targets
                    #  does NOT reset the counter when the higher one reappears)
                    self._pending_up_speed = curve_target
                    self._pending_up_count = 1
                    target_speed = self._last_speed
                else:
                    # Same pending target seen again — increment counter
                    self._pending_up_count += 1
                    if self._pending_up_count < self._SPINUP_TICKS:
                        target_speed = self._last_speed
                    else:
                        # Confirmed — apply new speed and start hold timer
                        target_speed = curve_target
                        self._hold_down_ticks = self._HOLD_TICKS
                        self._pending_up_speed = -1
                        self._pending_up_count = 0

            # ---- Speed decrease: hold for HOLD_TICKS after last spin-up ----
            elif curve_target < self._last_speed:
                self._pending_up_speed = -1
                self._pending_up_count = 0
                if self._hold_down_ticks > 0:
                    self._hold_down_ticks -= 1
                    target_speed = self._last_speed
                else:
                    target_speed = curve_target

            # ---- Speed unchanged ----
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
                    logger.info(f"Fan speed set MANUAL to {target_speed}%.")
                else:
                    crit_flag = " [OVERHEAT PROTECTION 100%]" if filtered_temp >= 70 else ""
                    logger.info(
                        f"Fan speed -> {target_speed}% "
                        f"(raw: {raw_temp}°C [CPU:{cpu_temp}°C GPU:{gpu_temp}°C], "
                        f"filtered: {filtered_temp}°C | mode: {mode_name} | "
                        f"hysteresis: {hysteresis}°C){crit_flag}"
                    )
                self._last_speed = target_speed
            else:
                logger.error(f"Fan write failed (target: {target_speed}%).")


_watchdog = None


def get_watchdog() -> FanWatchdog:
    global _watchdog
    if _watchdog is None:
        _watchdog = FanWatchdog()
    return _watchdog
