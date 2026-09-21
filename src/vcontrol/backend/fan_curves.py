ECO_CURVE = [
    (0,  0),
    (50, 20),
    (60, 30),
    (70, 40),
    (80, 50),
    (85, 100),
]

BALANCED_CURVE = [
    (0,  20),
    (50, 30),
    (60, 45),
    (70, 60),
    (80, 80),
    (85, 100),
]

PERFORMANCE_CURVE = [
    (0,  40),
    (50, 55),
    (60, 75),
    (70, 90),
    (75, 100),
]

DEFAULT_HYSTERESIS = 4   # Cooling hysteresis margin (°C)
CRITICAL_TEMP = 88        # Emergency hardware protection threshold (°C)


def get_target_pwm(
    temp: int,
    mode: str,
    current_speed: int = -1,
    hysteresis: int = DEFAULT_HYSTERESIS,
) -> int:
    """
    Calculate target fan speed (%) based on temperature and active mode.

    Hysteresis (Tolerance):
    Prevents constant speed oscillation when temperature hovers near a
    curve threshold.
    - On temperature rise: returns the speed for the new tier.
    - On temperature drop: only steps down once (threshold - hysteresis)
      is passed; otherwise keeps current speed.
    """
    if mode == "Eco":
        curve = ECO_CURVE
    elif mode == "Performance":
        curve = PERFORMANCE_CURVE
    else:
        curve = BALANCED_CURVE

    # First run or after a reset — apply curve directly without hysteresis
    if current_speed < 0:
        target = curve[0][1]
        for threshold, speed in curve:
            if temp >= threshold:
                target = speed
        return target

    # Find the index of the current tier by matching the current speed
    # exactly (or the nearest speed not exceeding current_speed).
    current_idx = 0
    for idx, (threshold, speed) in enumerate(curve):
        # Use <= so that when current_speed matches a tier exactly we land on it.
        if speed <= current_speed:
            current_idx = idx

    # 1. Temperature rising — check all tiers above current for new threshold
    for idx in range(len(curve) - 1, current_idx, -1):
        threshold, speed = curve[idx]
        if temp >= threshold:
            return speed

    # 2. Temperature falling — only drop after (threshold - hysteresis)
    curr_threshold, curr_speed = curve[current_idx]
    down_threshold = curr_threshold - hysteresis

    if temp < down_threshold:
        # Walk back down the curve applying hysteresis to each step
        for idx in range(current_idx - 1, -1, -1):
            threshold, speed = curve[idx]
            if temp >= (threshold - hysteresis):
                return speed
        return curve[0][1]

    # Within hysteresis band — hold current speed
    return curr_speed
