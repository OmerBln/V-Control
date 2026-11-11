import logging
import os
from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, GLib, Gtk

logger = logging.getLogger(__name__)

TEMP_CLASSES = ("temp-cool", "temp-warm", "temp-hot", "temp-critical")
CSS_PATH = os.path.join(os.path.dirname(__file__), "style.css")

_THEME_SCHEMES = {
    "system": Adw.ColorScheme.DEFAULT,
    "light": Adw.ColorScheme.FORCE_LIGHT,
    "dark": Adw.ColorScheme.FORCE_DARK,
}


def temp_class(temp: float) -> str:
    if temp >= 85:
        return "temp-critical"
    if temp >= 70:
        return "temp-hot"
    if temp >= 55:
        return "temp-warm"
    return "temp-cool"


def set_temp_class(widget: Gtk.Widget, temp: float) -> None:
    wanted = temp_class(temp)
    for cls in TEMP_CLASSES:
        if cls != wanted:
            widget.remove_css_class(cls)
    widget.add_css_class(wanted)


def load_css() -> None:
    display = Gdk.Display.get_default()
    if display is None or not os.path.exists(CSS_PATH):
        logger.warning(f"CSS not loaded: {CSS_PATH}")
        return
    provider = Gtk.CssProvider()
    provider.load_from_path(CSS_PATH)
    Gtk.StyleContext.add_provider_for_display(
        display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )


def apply_theme(theme: str) -> None:
    Adw.StyleManager.get_default().set_color_scheme(
        _THEME_SCHEMES.get(theme, Adw.ColorScheme.DEFAULT)
    )


class Debouncer:
    """Runs a callback once input has been idle for `delay_ms` (latest args win)."""

    def __init__(self, delay_ms: int, callback: Callable[..., None]):
        self._delay_ms = delay_ms
        self._callback = callback
        self._source_id: int | None = None
        self._args: tuple = ()

    @property
    def pending(self) -> bool:
        return self._source_id is not None

    def __call__(self, *args) -> None:
        self._args = args
        if self._source_id is not None:
            GLib.source_remove(self._source_id)
        self._source_id = GLib.timeout_add(self._delay_ms, self._fire)

    def flush(self) -> None:
        if self._source_id is not None:
            GLib.source_remove(self._source_id)
            self._fire()

    def cancel(self) -> None:
        if self._source_id is not None:
            GLib.source_remove(self._source_id)
            self._source_id = None

    def _fire(self) -> bool:
        self._source_id = None
        try:
            self._callback(*self._args)
        except Exception:  # noqa: BLE001 - never break the GLib main loop
            logger.exception("Debounced callback failed")
        return GLib.SOURCE_REMOVE

