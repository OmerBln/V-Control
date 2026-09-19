

ECO_CURVE = [
    (0, 0),
    (50, 20),
    (60, 30),
    (70, 40),
    (80, 50),
    (85, 100),
]

BALANCED_CURVE = [
    (0, 20),
    (50, 30),
    (60, 45),
    (70, 60),
    (80, 80),
    (85, 100),
]

PERFORMANCE_CURVE = [
    (0, 40),
    (50, 55),
    (60, 75),
    (70, 90),
    (75, 100),
]

def get_target_pwm(temp: int, mode: str) -> int:
    
    if mode == "Eco":
        curve = ECO_CURVE
    elif mode == "Performance":
        curve = PERFORMANCE_CURVE
    else:
        curve = BALANCED_CURVE
        
    target = 0
    for threshold, speed in curve:
        if temp >= threshold:
            target = speed
    return target
