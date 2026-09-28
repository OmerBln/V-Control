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
    (65, 75),
    (72, 90),
    (78, 100),
]

DEFAULT_HYSTERESIS = 4
CRITICAL_TEMP = 88


def get_target_pwm(temp: int, mode: str, current_speed: int = -1, hysteresis: int = DEFAULT_HYSTERESIS) -> int:
    if mode == "Eco":
        curve = ECO_CURVE
    elif mode == "Performance":
        curve = PERFORMANCE_CURVE
    else:
        curve = BALANCED_CURVE

    if current_speed < 0:
        target = curve[0][1]
        for threshold, speed in curve:
            if temp >= threshold:
                target = speed
        return target

    current_idx = 0
    for idx, (threshold, speed) in enumerate(curve):
        if speed <= current_speed:
            current_idx = idx

    for idx in range(len(curve) - 1, current_idx, -1):
        threshold, speed = curve[idx]
        if temp >= threshold:
            return speed

    curr_threshold, curr_speed = curve[current_idx]
    if temp < curr_threshold - hysteresis:
        for idx in range(current_idx - 1, -1, -1):
            threshold, speed = curve[idx]
            if temp >= (threshold - hysteresis):
                return speed
        return curve[0][1]

    return curr_speed
