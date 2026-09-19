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

DEFAULT_HYSTERESIS = 4   # Soğuma histerezis payı (°C)
CRITICAL_TEMP = 88        # Acil donanım koruma eşiği (°C)

def get_target_pwm(
    temp: int, 
    mode: str, 
    current_speed: int = -1, 
    hysteresis: int = DEFAULT_HYSTERESIS
) -> int:
    """
    Sıcaklığa ve aktif moda göre hedef fan hızını (%) hesaplar.
    
    Histerezis (Tolerans):
    Sıcaklık kademe sınırında (örn. 50°C) gezinirken fanların sürekli
    devir yükseltip düşürmesini önler.
    - Sıcaklık artarken ilgili kademenin hızını döndürür.
    - Sıcaklık düşerken ise (eşik - histerezis) kadar soğuma olmadan
      alt kademeye geçmez, mevcut hızı korur.
    """
    if mode == "Eco":
        curve = ECO_CURVE
    elif mode == "Performance":
        curve = PERFORMANCE_CURVE
    else:
        curve = BALANCED_CURVE

    # İlk başlangıç veya sıfırlanmış hızda doğrudan eşik kontrolü
    if current_speed < 0:
        target = curve[0][1]
        for threshold, speed in curve:
            if temp >= threshold:
                target = speed
        return target

    # Mevcut hızın eğrideki indeksini bul
    current_idx = 0
    for idx, (threshold, speed) in enumerate(curve):
        if speed <= current_speed:
            current_idx = idx

    # 1. Sıcaklık artışı (YUKARI KADEME):
    for idx in range(len(curve) - 1, current_idx, -1):
        threshold, speed = curve[idx]
        if temp >= threshold:
            return speed

    # 2. Sıcaklık düşüşü (AŞAĞI KADEME - Histerezis):
    # Sıcaklık (mevcut eşik - histerezis) değerinin altına inmediyse hızı koru
    curr_threshold, curr_speed = curve[current_idx]
    down_threshold = curr_threshold - hysteresis

    if temp < down_threshold:
        for idx in range(current_idx - 1, -1, -1):
            threshold, speed = curve[idx]
            if temp >= (threshold - hysteresis):
                return speed
        return curve[0][1]

    # Tolerans aralığında mevcut hızı koru
    return curr_speed
