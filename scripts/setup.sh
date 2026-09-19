#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────
# hp-victus-tools Kurulum Scripti
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
echo -e "${BOLD}HP Victus Tools — Kurulum${RESET}"
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
python3 -c "import gi; gi.require_version('Gtk','4.0'); from gi.repository import Gtk" 2>/dev/null \
    && success "GTK4 + python-gobject mevcut." \
    || error "python-gobject bulunamadı! Kurun: sudo pacman -S python-gobject"

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

# ── 4. udev kuralları ─────────────────────────────────────────────
info "udev kuralları kuruluyor..."
bash "$SCRIPT_DIR/install-udev.sh" || warn "udev kurulumu başarısız — manuel kurulum gerekebilir."

# ── 5. KDE kısayolu ───────────────────────────────────────────────
if command -v kwriteconfig6 >/dev/null 2>&1 || command -v kwriteconfig5 >/dev/null 2>&1; then
    info "KDE global kısayol kaydediliyor..."
    bash "$SCRIPT_DIR/install-shortcut.sh" || warn "KDE kısayol kurulumu başarısız."
else
    warn "KDE konfigürasyon araçları bulunamadı. Kısayolu manuel ekleyin."
fi

# ── 6. Tamamlandı ─────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}✓ Kurulum tamamlandı!${RESET}"
echo ""
echo "Kullanım:"
echo "  Ana uygulama:   .venv/bin/hp-victus-tools"
echo "  Quick Overlay:  .venv/bin/hp-victus-overlay"
echo "  Kısayol:        Meta + Shift + F"
echo ""
