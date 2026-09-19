#!/usr/bin/env bash
set -e

echo "============================================="
echo " HP Victus Tools - Kernel WMI Yama Kurulumu"
echo "============================================="

# Remove nbfc if installed
echo "NBFC kaldırılıyor..."
sudo systemctl disable --now nbfc_service || true
yay -Rns nbfc-linux acpi_call-dkms --noconfirm || true

# Install omen-fan-control DKMS patch
echo "Gerekli bağımlılıklar kuruluyor..."
sudo pacman -S --needed dkms linux-headers base-devel python-pipx jq --noconfirm

echo "omen-fan-control indiriliyor..."
pipx install git+https://github.com/arfelious/omen-fan-control.git --force
sudo ln -sf "$HOME/.local/bin/omen-fan-control"* /usr/local/bin/ || true

# Bypass calibration step for omen-fan-control by injecting config
echo "Kalibrasyon zorunluluğu atlanıyor (Manuel Maksimum Devir 6000 RPM olarak ayarlandı)..."
mkdir -p "$HOME/.config/omen-fan-control"
sudo mkdir -p "/etc/omen-fan-control"
if [ ! -f "/etc/omen-fan-control/config.json" ]; then
    echo "{}" | sudo tee /etc/omen-fan-control/config.json
fi
sudo jq '.use_manual_max_rpm = true | .max_fan_speed_strategy = "manual" | .manual_cpu_max_rpm = 6000 | .manual_gpu_max_rpm = 6000' /etc/omen-fan-control/config.json | sudo tee /tmp/config_root.json
sudo cp /tmp/config_root.json /etc/omen-fan-control/config.json

echo "Kernel yaması DKMS ile kalıcı olarak kuruluyor..."
sudo omen-fan-control install-patch permanent

# Udev rule for hp-wmi hwmon permissions
echo "Udev kuralları ekleniyor (Kullanıcı izni için)..."
cat << 'UDEV' | sudo tee /etc/udev/rules.d/99-hp-wmi-fan.rules
ACTION=="add", SUBSYSTEM=="hwmon", KERNEL=="hwmon*", DRIVERS=="hp-wmi", RUN+="/bin/sh -c 'chmod a+rw /sys%p/pwm*'"
UDEV
sudo udevadm control --reload-rules
sudo udevadm trigger

echo "Kurulum tamamlandı! Lütfen arayüzü başlatın."
