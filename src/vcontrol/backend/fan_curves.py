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

DEFAULT_HYSTERESIS = 4      # Soğuma toleransı (°C)
DEFAULT_RISE_TOLERANCE = 2  # 70°C altı için ısınma toleransı (°C)
PROTECTION_TEMP = 70        # Donanım koruma eşiği (bu dereceden itibaren gecikmesiz yükselir)

def get_target_pwm(
    temp: int, 
    mode: str, 
    current_speed: int = -1, 
    hysteresis: int = DEFAULT_HYSTERESIS,
    rise_tolerance: int = DEFAULT_RISE_TOLERANCE,
    protection_temp: int = PROTECTION_TEMP
) -> int:
    """
    Sıcaklığa ve aktif moda göre hedef fan hızını (%) hesaplar.
    
    Kural ve Tolerans Davranışı:
    1. Donanım Koruma (>= 70°C):
       70°C ve üzerindeki sıcaklıklarda donanımı korumak için fanlar
       gecikmesiz ve toleranssız olarak doğrudan eğri hızına yükseltilir.
    2. Düşük/Orta Sıcaklıklar (< 70°C):
       70°C altındaki sıcaklıklarda 1 derecelik dalgalanmalarda fanların
       sürekli hızlanmasını önlemek için 'rise_tolerance' (+2°C) payı bırakılır.
    3. Soğuma Histerezisi:
       Sıcaklık düşerken ise mevcut eşikten en az 'hysteresis' (4°C) kadar
       soğuma gerçekleşmeden alt kademeye geçilmez, hız sabit tutulur.
    """
    if mode == "Eco":
        curve = ECO_CURVE
    elif mode == "Performance":
        curve = PERFORMANCE_CURVE
    else:
        curve = BALANCED_CURVE

    # İlk başlangıç veya bilinmeyen hızda doğrudan eşik kontrolü
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
        if threshold >= protection_temp or temp >= protection_temp:
            # 70°C ve üzeri: DONANIM KORUMASI - Gecikmesiz doğrudan eşiğe bak
            if temp >= threshold:
                return speed
        else:
            # 70°C altı: Isınma toleransı (+rise_tolerance) aranır
            if temp >= (threshold + rise_tolerance):
                return speed

    # 2. Sıcaklık düşüşü (AŞAĞI KADEME):
    # Sıcaklık (mevcut eşik - histerezis) değerinin altına inmediyse hızı koru
    curr_threshold, curr_speed = curve[current_idx]
    down_threshold = curr_threshold - hysteresis

    if temp < down_threshold:
        for idx in range(current_idx - 1, -1, -1):
            threshold, speed = curve[idx]
            if temp >= (threshold - hysteresis):
                return speed
        return curve[0][1]

    # Tolerans aralığında ise mevcut hızı koru
    return curr_speed
