import logging
import statistics
from collections import deque
from typing import Optional
from vcontrol.backend.fan import get_controller
from vcontrol.backend.profiles import get_manager
from vcontrol.backend.fan_curves import get_target_pwm

logger = logging.getLogger(__name__)
WATCHDOG_INTERVAL_S = 2

# Maximum allowed single-sample jump vs. recent median before treating as spike
SPIKE_THRESHOLD_C = 20

# Hardware protection: ramp to 100% above this temperature (°C)
OVERHEAT_TEMP = 70
# Don't drop out of overheat protection until temperature falls below this
OVERHEAT_RELEASE_TEMP = 65


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
        self._SPINUP_TICKS = 2   # 2 ticks × 2 s = 4 s confirmation window

        # Spin-down: hold current speed for HOLD_TICKS ticks after a rise
        self._hold_down_ticks = 0
        self._HOLD_TICKS = 4     # 4 ticks × 2 s = 8 s hold period

        # Track overheat state with hysteresis to avoid rapid toggling
        self._in_overheat = False

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
        self._in_overheat = False

    def _add_temp_sample(self, raw_temp: int) -> int:
        """
        Add a temperature sample with upward spike rejection.

        Only upward jumps larger than SPIKE_THRESHOLD_C from the recent
        median are treated as sensor glitches and discarded.  Genuine
        cooling (downward changes) is always accepted so the filter does
        not delay fan spin-down when load truly stops.
        Returns the filtered (median) temperature.
        """
        # Need at least 2 previous samples to detect spikes reliably
        if len(self._temp_history) >= 2:
            recent = list(self._temp_history)[-3:]
            recent_median = statistics.median(recent)
            upward_jump = raw_temp - recent_median  # positive = hotter
            if upward_jump > SPIKE_THRESHOLD_C:
                logger.warning(
                    f"Sensor spike rejected: {raw_temp}°C "
                    f"(recent median {recent_median:.0f}°C, "
                    f"+{upward_jump:.0f}°C upward jump)"
                )
                # Do not add to history; return current median unchanged
                return int(round(statistics.median(self._temp_history)))

        self._temp_history.append(raw_temp)
        return int(round(statistics.median(self._temp_history)))

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

            # Two-stage filtering:
            # Stage 1 — spike rejection: discard samples that jump >SPIKE_THRESHOLD_C
            #           from the recent median (sensor glitches, DTS bursts, etc.)
            # Stage 2 — median of the clean 5-sample window for smoothing
            filtered_temp = self._add_temp_sample(raw_temp)

            # 2. Determine target from curve (using filtered temperature)
            curve_target = get_target_pwm(
                filtered_temp,
                mode_name,
                current_speed=self._last_speed,
                hysteresis=hysteresis,
            )

            # 3. Hardware protection with hysteresis to avoid rapid 100% toggling:
            #    - Enter overheat mode when filtered temp >= OVERHEAT_TEMP
            #    - Exit overheat mode only when filtered temp <= OVERHEAT_RELEASE_TEMP
            if self._in_overheat:
                if filtered_temp <= OVERHEAT_RELEASE_TEMP:
                    self._in_overheat = False
                    logger.info(
                        f"Overheat protection released at {filtered_temp}°C "
                        f"(<= {OVERHEAT_RELEASE_TEMP}°C threshold)."
                    )
                else:
                    curve_target = 100
            else:
                if filtered_temp >= OVERHEAT_TEMP:
                    self._in_overheat = True
                    curve_target = 100
                    logger.warning(
                        f"Overheat protection engaged at {filtered_temp}°C "
                        f"(>= {OVERHEAT_TEMP}°C threshold)."
                    )

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
                    crit_flag = " [OVERHEAT PROTECTION 100%]" if self._in_overheat else ""
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
