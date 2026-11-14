import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

from vcontrol import __version__
from vcontrol.backend.daemon_status import (
    is_daemon_alive,
    service_enabled,
    service_installed,
    set_service_enabled,
    start_service,
    stop_service,
)
from vcontrol.backend.settings import THEMES, load_settings
from vcontrol.ui.util import apply_theme


class SettingsPanel(Gtk.ScrolledWindow):
    def __init__(self, parent_window: Gtk.Window | None = None):
        super().__init__()
        self.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._parent_window = parent_window
        self._settings = load_settings()
        self._updating = False

        clamp = Adw.Clamp()
        clamp.set_maximum_size(640)
        clamp.set_tightening_threshold(400)
        clamp.set_margin_top(24)
        clamp.set_margin_bottom(28)
        clamp.set_margin_start(16)
        clamp.set_margin_end(16)

        clamp_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)

        # ── Appearance group ───────────────────────────────────
        theme_group = Adw.PreferencesGroup(
            title="Görünüm Ayarları",
            description="Uygulama renk şemasını belirleyin (otomatik kaydedilir)",
        )
        theme_row = Adw.ComboRow(
            title="Uygulama Teması",
            model=Gtk.StringList.new(["Sistem Varsayılanı", "Açık Tema", "Koyu Tema"]),
        )
        idx = THEMES.index(self._settings.theme) if self._settings.theme in THEMES else 0
        theme_row.set_selected(idx)
        theme_row.connect("notify::selected", self._on_theme_changed)
        theme_group.add(theme_row)
        clamp_box.append(theme_group)

        # ── Background service group ───────────────────────────
        service_group = Adw.PreferencesGroup(
            title="Arka Plan Fan Servisi",
            description="v-control-daemon akıllı termal motorunu ve systemd kullanıcı servisini yönetin",
        )

        self.daemon_row = Adw.ActionRow(
            title="Termal Motor Durumu",
            subtitle="Kontrol ediliyor...",
        )
        self.daemon_switch = Gtk.Switch(valign=Gtk.Align.CENTER)
        self.daemon_switch.connect("state-set", self._on_daemon_toggled)
        self.daemon_row.add_suffix(self.daemon_switch)
        service_group.add(self.daemon_row)

        self.autostart_row = Adw.ActionRow(
            title="Oturum Açılışında Başlat",
            subtitle="Kullanıcı oturumu açıldığında fan servisini otomatik çalıştır",
        )
        self.autostart_switch = Gtk.Switch(valign=Gtk.Align.CENTER)
        self.autostart_switch.connect("state-set", self._on_autostart_toggled)
        self.autostart_row.add_suffix(self.autostart_switch)
        service_group.add(self.autostart_row)

        clamp_box.append(service_group)

        # ── About group ────────────────────────────────────────
        about_group = Adw.PreferencesGroup(title="Uygulama")
        about_row = Adw.ActionRow(
            title="V-Control Hakkında",
            subtitle=f"Sürüm {__version__} · HP Victus 16 Fan ve Aydınlatma Kontrolcüsü",
            activatable=True,
        )
        about_row.add_suffix(Gtk.Image.new_from_icon_name("go-next-symbolic"))
        about_row.connect("activated", self._on_about_clicked)
        about_group.add(about_row)
        clamp_box.append(about_group)

        clamp.set_child(clamp_box)
        self.set_child(clamp)

        self._refresh_service_state()
        GLib.timeout_add(2000, self._refresh_service_state)

    def _on_theme_changed(self, combo_row: Adw.ComboRow, _pspec) -> None:
        selected = int(combo_row.get_selected())
        theme = THEMES[selected] if 0 <= selected < len(THEMES) else "system"
        self._settings.theme = theme
        self._settings.save()
        apply_theme(theme)

    def _refresh_service_state(self) -> bool:
        if not self.get_root():
            return False
        if not self.get_mapped():
            return True

        self._updating = True
        installed = service_installed()
        alive = is_daemon_alive()
        enabled = service_enabled() if installed else False

        if alive:
            self.daemon_row.set_subtitle("Çalışıyor — fan eğrisi ve termal koruma aktif")
        elif installed:
            self.daemon_row.set_subtitle("Durduruldu — fan kontrolü BIOS'ta")
        else:
            self.daemon_row.set_subtitle("Systemd kullanıcı servisi kurulu değil (scripts/setup.sh çalıştırın)")

        self.daemon_switch.set_sensitive(installed or alive)
        self.daemon_switch.set_active(alive)
        self.autostart_switch.set_sensitive(installed)
        self.autostart_switch.set_active(enabled)
        self._updating = False
        return True

    def _on_daemon_toggled(self, _switch: Gtk.Switch, state: bool) -> bool:
        if self._updating:
            return False
        if state:
            start_service()
        else:
            stop_service()
        GLib.timeout_add(600, self._refresh_service_state)
        return False

    def _on_autostart_toggled(self, _switch: Gtk.Switch, state: bool) -> bool:
        if self._updating:
            return False
        set_service_enabled(state)
        return False

    def _on_about_clicked(self, _row: Adw.ActionRow) -> None:
        about = Adw.AboutWindow(
            transient_for=self._parent_window or self.get_root(),
            application_name="V-Control",
            application_icon="v-control",
            developer_name="V-Control Geliştiricileri",
            version=__version__,
            comments="HP Victus 16 dizüstü bilgisayarlar için Linux ortamında fan hızı, termal profil ve RGB klavye aydınlatma kontrolü.",
            license_type=Gtk.License.MIT_X11,
        )
        about.present()
