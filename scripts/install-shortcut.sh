#!/usr/bin/env bash
# KDE Plasma global kısayol kaydedici
# hp-victus-overlay'i Meta+Shift+F ile tetikler

set -euo pipefail

OVERLAY_BIN="$(cd "$(dirname "$0")/.." && pwd)/.venv/bin/hp-victus-overlay"

if [[ ! -f "$OVERLAY_BIN" ]]; then
    echo "[WARN] hp-victus-overlay binary bulunamadı: $OVERLAY_BIN"
    echo "[WARN] Önce 'bash scripts/setup.sh' çalıştırın."
    exit 1
fi

# kwriteconfig6 veya kwriteconfig5 kullan
KWRITE=""
command -v kwriteconfig6 >/dev/null 2>&1 && KWRITE="kwriteconfig6"
command -v kwriteconfig5 >/dev/null 2>&1 && KWRITE="${KWRITE:-kwriteconfig5}"

if [[ -z "$KWRITE" ]]; then
    echo "[WARN] kwriteconfig bulunamadı."
    exit 1
fi

# KDE Custom Shortcut kaydet
KSHORTCUTS_FILE="${HOME}/.config/khotkeysrc"

# Basit yol: .desktop dosyasını autostart'a ekle + kısayolu manuel bildir
AUTOSTART_DIR="${HOME}/.config/autostart"
mkdir -p "$AUTOSTART_DIR"

cat > "${HOME}/.local/share/applications/hp-victus-overlay.desktop" << DESKEOF
[Desktop Entry]
Name=HP Victus Quick Layout
Comment=HP Victus 16 Fan & RGB hızlı kontrol overlay
Exec=$OVERLAY_BIN
Icon=utilities-system-monitor
Type=Application
Categories=System;
Keywords=fan;rpm;victus;hp;gaming;
DESKEOF

echo "[OK] .desktop dosyası oluşturuldu."
echo ""
echo "KDE'de kısayol eklemek için:"
echo "  Sistem Ayarları → Kısayollar → Özel Kısayollar → Uygulama Başlatma"
echo "  Tetikleyici: Meta+Shift+F"
echo "  Komut: $OVERLAY_BIN"
