#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────
# V-Control Kurulum Scripti
# Kullanım: bash scripts/setup.sh
# ──────────────────────────────────────────────────────────────────

set -euo pipefail

# Renk kodları
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

info()    { echo -e "${CYAN}[INFO]${RESET} $*"; }
success() { echo -e "${GREEN}[OK]${RESET} $*"; }
warn()    { echo -e "${YELLOW}[WARN]${RESET} $*"; }
error()   { echo -e "${RED}[HATA]${RESET} $*" >&2; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo -e "${BOLD}"
echo "  ██╗  ██╗██████╗      ██╗   ██╗██╗ ██████╗████████╗██╗   ██╗███████╗"
echo "  ██║  ██║██╔══██╗     ██║   ██║██║██╔════╝╚══██╔══╝██║   ██║██╔════╝"
echo "  ███████║██████╔╝     ██║   ██║██║██║        ██║   ██║   ██║███████╗"
echo "  ██╔══██║██╔═══╝      ╚██╗ ██╔╝██║██║        ██║   ██║   ██║╚════██║"
echo "  ██║  ██║██║           ╚████╔╝ ██║╚██████╗   ██║   ╚██████╔╝███████║"
echo "  ╚═╝  ╚═╝╚═╝            ╚═══╝  ╚═╝ ╚═════╝   ╚═╝    ╚═════╝ ╚══════╝"
echo -e "${RESET}"
echo -e "${BOLD}V-Control — Kurulum${RESET}"
echo "────────────────────────────────────────"

cd "$PROJECT_DIR"

# ── 1. Gereksinim kontrolleri ──────────────────────────────────────
info "Sistem gereksinimleri kontrol ediliyor..."

command -v python3 >/dev/null 2>&1 || error "python3 bulunamadı!"
PYTHON_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
info "Python sürümü: $PYTHON_VER"

# hp-wmi hwmon kontrolü
HP_HWMON=""
for path in /sys/class/hwmon/hwmon*; do
    name_file="$path/name"
    if [[ -f "$name_file" ]] && [[ "$(cat "$name_file")" == "hp" ]]; then
        HP_HWMON="$path"
        break
    fi
done

if [[ -n "$HP_HWMON" ]]; then
    success "hp-wmi hwmon bulundu: $HP_HWMON"
else
    warn "hp-wmi hwmon bulunamadı. Fan kontrolü çalışmayabilir."
    warn "Kernel: $(uname -r)"
fi

# GTK4 ve python-gobject kontrolü
python3 -c "import gi; gi.require_version('Gtk','4.0'); gi.require_version('Adw','1'); from gi.repository import Gtk, Adw" 2>/dev/null \
    && success "GTK4 + Libadwaita + python-gobject mevcut." \
    || error "GTK4 / Libadwaita / python-gobject bulunamadı! Kurun: sudo pacman -S python-gobject gtk4 libadwaita"

# ── 2. Python sanal ortamı ─────────────────────────────────────────
if [[ -d ".venv" ]]; then
    info "Mevcut .venv bulundu, yenileniyor..."
else
    info "Python sanal ortamı oluşturuluyor (.venv/)..."
fi

python3 -m venv --system-site-packages .venv
success "Sanal ortam hazır: .venv/"

info "pip güncelleniyor..."
.venv/bin/python -m pip install --upgrade pip --quiet

# ── 3. Proje bağımlılıkları ────────────────────────────────────────
info "Bağımlılıklar kuruluyor (sadece .venv içine)..."
.venv/bin/pip install -e ".[dev]" --quiet
success "Bağımlılıklar kuruldu."

# ── 4. İkon, Masaüstü Başlatıcı ve Systemd Kullanıcı Servisi ──────
info "İkon, masaüstü başlatıcı ve arka plan servisi kuruluyor..."
mkdir -p "$HOME/.local/bin"
ln -sf "$PROJECT_DIR/.venv/bin/v-control" "$HOME/.local/bin/v-control"
ln -sf "$PROJECT_DIR/.venv/bin/v-control-overlay" "$HOME/.local/bin/v-control-overlay"
ln -sf "$PROJECT_DIR/.venv/bin/v-control-daemon" "$HOME/.local/bin/v-control-daemon"

ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"
mkdir -p "$ICON_DIR"
if [[ -f "$PROJECT_DIR/data/icons/v-control.svg" ]]; then
    cp "$PROJECT_DIR/data/icons/v-control.svg" "$ICON_DIR/v-control.svg"
fi

APP_DIR="$HOME/.local/share/applications"
mkdir -p "$APP_DIR"
cat > "$APP_DIR/v-control.desktop" << DESKEOF
[Desktop Entry]
Name=V-Control
GenericName=Laptop Fan & RGB Controller
Comment=HP Victus 16 fan hızı ve RGB klavye arka aydınlatma kontrolü
Exec=$PROJECT_DIR/.venv/bin/v-control
Icon=$PROJECT_DIR/data/icons/v-control.svg
Type=Application
Categories=System;HardwareSettings;
Keywords=fan;rpm;victus;hp;gaming;rgb;keyboard;
StartupNotify=true
StartupWMClass=com.vcontrol.app
DESKEOF

SYSTEMD_USER_DIR="$HOME/.config/systemd/user"
mkdir -p "$SYSTEMD_USER_DIR"
cat > "$SYSTEMD_USER_DIR/v-control-daemon.service" << SVCEOF
[Unit]
Description=V-Control Fan & Thermal Daemon
After=default.target

[Service]
Type=simple
ExecStart=$PROJECT_DIR/.venv/bin/v-control-daemon
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
SVCEOF

if command -v systemctl >/dev/null 2>&1; then
    systemctl --user daemon-reload || true
    systemctl --user enable --now v-control-daemon.service \
        && success "Arka plan servisi (v-control-daemon) etkinleştirildi ve başlatıldı." \
        || warn "Systemd kullanıcı servisi başlatılamadı."
fi

# ── 5. udev kuralları ─────────────────────────────────────────────
info "udev kuralları kuruluyor..."
bash "$SCRIPT_DIR/install-udev.sh" || warn "udev kurulumu başarısız — manuel kurulum gerekebilir."

# ── 6. Masaüstü kısayolu ──────────────────────────────────────────
info "Global kısayol kaydediliyor..."
bash "$SCRIPT_DIR/install-shortcut.sh" || warn "Kısayol kurulumu başarısız."

# ── 7. Tamamlandı ─────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}✓ Kurulum tamamlandı!${RESET}"
echo ""
echo "Kullanım:"
echo "  Ana uygulama:   .venv/bin/v-control"
echo "  Quick Overlay:  .venv/bin/v-control-overlay"
echo "  Arka Plan:      .venv/bin/v-control-daemon"
echo "  Kısayol:        Shift + F2"
echo ""
