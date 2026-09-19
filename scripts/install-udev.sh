#!/usr/bin/env bash
# hp-victus-tools — Sistem izin kurulumu
# İki yöntem: sudoers (tercih) + udev (yedek)

set -euo pipefail

if [[ $EUID -ne 0 ]]; then
    exec sudo bash "$0" "$@"
fi

SUDOERS_FILE="/etc/sudoers.d/hp-victus-tools"
UDEV_FILE="/etc/udev/rules.d/99-hp-victus-tools.rules"
HWMON_PATH="/sys/devices/platform/hp-wmi/hwmon"

echo "[INFO] Sudoers kuralı yazılıyor: $SUDOERS_FILE"
cat > "$SUDOERS_FILE" << 'SUDOEOF'
# hp-victus-tools: Şifresiz fan kontrolü
# Yalnızca belirli sysfs dosyalarına tee ile yazılmasına izin verir.
%wheel ALL=(root) NOPASSWD: /usr/bin/tee /sys/class/platform-profile/*/profile
%wheel ALL=(root) NOPASSWD: /usr/bin/tee /sys/devices/platform/hp-wmi/platform-profile/*/profile
%wheel ALL=(root) NOPASSWD: /usr/bin/tee /sys/devices/platform/hp-wmi/hwmon/hwmon*/pwm1_enable
SUDOEOF
chmod 440 "$SUDOERS_FILE"
echo "[OK] Sudoers kuralı kuruldu."

echo "[INFO] udev kuralı yazılıyor: $UDEV_FILE"
cat > "$UDEV_FILE" << 'UDEVEOF'
# hp-victus-tools: hp-wmi hwmon fan erişimi
SUBSYSTEM=="hwmon", ATTR{name}=="hp", GROUP="wheel", MODE="0664"
UDEVEOF
udevadm control --reload-rules
udevadm trigger --subsystem-match=hwmon
echo "[OK] udev kuralı kuruldu."

echo ""
echo "[INFO] Anlık sysfs izinleri elle düzeltiliyor..."
for f in $(find $HWMON_PATH -name "pwm1*" 2>/dev/null); do
    chown root:wheel "$f"
    chmod 0664 "$f"
    echo "  → $f"
done

PP_PATH=$(find /sys/class/platform-profile -name "profile" 2>/dev/null | head -1)
if [ -n "$PP_PATH" ]; then
    chown root:wheel "$PP_PATH"
    chmod 0664 "$PP_PATH"
    echo "  → $PP_PATH"
fi

echo ""
echo "[OK] Kurulum tamamlandı! Fan kontrolü artık çalışmalı."
