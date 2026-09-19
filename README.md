<p align="center">
  <img src="data/icons/hpvictustools.svg" width="96" alt="hp-victus-tools logo"/>
</p>

<h1 align="center">hp-victus-tools</h1>

<p align="center">
  HP Victus 16 için Linux'ta fan hızı ve RGB klavye arka aydınlatma kontrolü.<br/>
  CachyOS / Arch Linux · KDE Plasma · GTK4
</p>

<p align="center">
  <img src="https://img.shields.io/badge/platform-Linux-blue?logo=linux" />
  <img src="https://img.shields.io/badge/python-3.11%2B-brightgreen?logo=python" />
  <img src="https://img.shields.io/badge/GUI-GTK4-orange" />
  <img src="https://img.shields.io/badge/license-MIT-lightgrey" />
</p>

---

## ✨ Özellikler

- 🌀 **Fan Kontrolü** — Otomatik / Manuel / Profil modları
- ⚡ **Quick Layout** — Kısayol tuşuyla açılan yüzen HUD (OMEN Gaming Hub benzeri)
- 🎨 **RGB Kontrol** — Klavye arka aydınlatma renk ve parlaklık ayarı
- 📊 **Gerçek Zamanlı İzleme** — CPU/GPU sıcaklık ve fan RPM grafikleri
- 🔁 **Watchdog Servisi** — HP BIOS override'ını engeller

## 🖥️ Sistem Gereksinimleri

| Gereksinim | Detay |
|---|---|
| Laptop | HP Victus 16 (hp-wmi sürücülü) |
| OS | CachyOS / Arch Linux (veya türevleri) |
| Kernel | 6.x+ (`hp-wmi` driver gerekli) |
| Python | 3.11+ |
| GUI | GTK4 + python-gobject |

## 🚀 Kurulum

```bash
git clone https://github.com/KULLANICI/hp-victus-tools.git
cd hp-victus-tools
bash scripts/setup.sh
```

## ⌨️ Quick Layout Kısayolu

Varsayılan: `Meta + Shift + F`

KDE Plasma'da özelleştirmek için:
*Sistem Ayarları → Kısayollar → Özel Kısayollar → hp-victus-tools*

## 📝 Lisans

MIT © 2026
