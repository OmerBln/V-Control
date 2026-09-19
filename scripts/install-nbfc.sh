#!/usr/bin/env bash
set -e

echo "============================================="
echo " HP Victus Tools - NBFC Kurulum Betiği"
echo "============================================="

echo "[1/4] Gerekli paketler kuruluyor (yay üzerinden)..."
yay -S nbfc-linux acpi_call-dkms --noconfirm

echo "[2/4] NBFC servisi başlatılıyor..."
sudo systemctl enable --now nbfc_service

echo "[3/4] Cihaz modeli tespit ediliyor..."
sudo nbfc config -r

echo "[4/4] NBFC başarıyla kuruldu!"
echo "Lütfen kurulum başarılı olduysa uygulamanıza geri dönün."
