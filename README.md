<p align="center">
  <img src="data/icons/v-control.svg" width="96" alt="V-Control logo"/>
</p>

<h1 align="center">V-Control</h1>

<p align="center">
  HP Victus 16 için Linux'ta fan hızı, termal profil ve RGB klavye arka aydınlatma kontrolü.<br/>
  CachyOS / Arch Linux · KDE Plasma · GTK4 & Libadwaita
</p>

<p align="center">
  <img src="https://img.shields.io/badge/platform-Linux-blue?logo=linux" />
  <img src="https://img.shields.io/badge/python-3.11%2B-brightgreen?logo=python" />
  <img src="https://img.shields.io/badge/GUI-GTK4%20%2B%20Libadwaita-orange" />
  <img src="https://img.shields.io/badge/license-MIT-lightgrey" />
</p>

---

## ✨ Özellikler

- 🌀 **Fan Kontrolü ve Canlı Eğri** — Eco / Dengeli / Performans modları, histerezis toleransı ve manuel hız kontrolü
- ⚡ **Quick Overlay (HUD)** — Kısayol tuşuyla açılan yüzen kontrol ve izleme paneli
- 🎨 **RGB Klavye Kontrolü** — Bölge destekli renk seçimi, hazır renk çipleri ve kalıcı parlaklık ayarı
- 📊 **Gerçek Zamanlı Sistem İzleme** — CPU, GPU, NVMe sıcaklıkları, sistem yükü ve fan RPM grafikleri
- 🔁 **Akıllı Termal Motor (`v-control-daemon`)** — Sıcaklık sıçrama filtresi ve BIOS override koruması

## 🖥️ Sistem Gereksinimleri

| Gereksinim | Detay |
|---|---|
| Laptop | HP Victus 16 (`hp-wmi` sürücülü) |
| OS | CachyOS / Arch Linux (veya türevleri) |
| Kernel | 6.x+ (`hp-wmi` sürücüsü gerekli) |
| Python | 3.11+ |
| GUI | GTK4 + Libadwaita (`python-gobject`) |

## 🚀 Kurulum

```bash
git clone https://github.com/KULLANICI/V-Control.git
cd V-Control
bash scripts/setup.sh
```

## ⌨️ Quick Overlay Kısayolu

Varsayılan: `Shift + F2`

KDE Plasma'da özelleştirmek için:
*Sistem Ayarları → Kısayollar → V-Control Overlay*

## 📝 Lisans

MIT © 2026
