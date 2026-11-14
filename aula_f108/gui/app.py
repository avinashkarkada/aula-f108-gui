import os
import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from .. import device, store  # noqa: E402
from .lighting import LightingPage  # noqa: E402
from .perkey import PerKeyPage  # noqa: E402
from .remapping import RemapPage  # noqa: E402
from .screen import ScreenPage  # noqa: E402

APP_ID = "io.github.avinashkarkada.AulaF108"

WIRELESS_NOTE = ("Connected through the 2.4G receiver. Wireless support is "
                 "experimental: if a change doesn't show up, apply it again "
                 "or use the cable.")
BATTERY_EVERY = 60     # seconds between battery readings


class Window(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Aula F108 Pro",
                         default_width=920, default_height=680)
        self.settings = store.load()
        self.connected = False
        self.kind = None
        self.busy = False
        self._buttons = []
        self._battery_checked = 0.0

        self.stack = Adw.ViewStack()
        self.toasts = Adw.ToastOverlay(child=self.stack)

        header = Adw.HeaderBar()
        header.set_title_widget(Adw.ViewSwitcher(
            stack=self.stack, policy=Adw.ViewSwitcherPolicy.WIDE))
        self.battery = Gtk.Label(visible=False, margin_start=6)
        self.battery.add_css_class("dim-label")
        self.battery.set_tooltip_text("Keyboard battery")
        header.pack_start(self.battery)

        self.banner = Adw.Banner()

        view = Adw.ToolbarView(content=self.toasts)
        view.add_top_bar(header)
        view.add_top_bar(self.banner)
        self.set_content(view)

        self._add_page(LightingPage(self), "lighting", "Lighting",
                       "preferences-color-symbolic")
        self._add_page(PerKeyPage(self), "keys", "Key colours",
                       "input-keyboard-symbolic")
        self._add_page(RemapPage(self), "remap", "Remap",
                       "preferences-desktop-keyboard-shortcuts-symbolic")
        self._add_page(ScreenPage(self), "screen", "Screen",
                       "video-display-symbolic")

        self._check_connection()
        GLib.timeout_add_seconds(2, self._check_connection)

    def _add_page(self, page, name, title, icon):
        self.stack.add_titled_with_icon(page, name, title, icon)

    # pages hand their apply buttons over so they grey out when there is
    # nothing to talk to
    def watch_button(self, button):
        self._buttons.append(button)
        button.set_sensitive(self.connected and not self.busy)

    def _refresh_buttons(self):
        for button in self._buttons:
            button.set_sensitive(self.connected and not self.busy)

    def _check_connection(self):
        problem = None
        kind = None
        try:
            link = device.find()
            kind = link.kind
            if not os.access(link.path, os.R_OK | os.W_OK):
                problem = ("The keyboard is connected but can't be opened. "
                           "Install the udev rule and replug it.")
        except device.NotFound as e:
            problem = str(e)
        self.connected = problem is None
        self.kind = kind if self.connected else None

        if problem:
            self.banner.set_title(problem)
        elif kind == device.DONGLE:
            self.banner.set_title(WIRELESS_NOTE)
        self.banner.set_revealed(problem is not None or kind == device.DONGLE)

        if self.kind == device.DONGLE:
            self._update_battery()
        else:
            self.battery.set_visible(False)
            self._battery_checked = 0.0
        self._refresh_buttons()
        return GLib.SOURCE_CONTINUE

    def _update_battery(self):
        now = GLib.get_monotonic_time() / 1e6
        if self.busy or now - self._battery_checked < BATTERY_EVERY:
            return
        self._battery_checked = now

        def work():
            try:
                level = device.run(lambda kb: kb.battery())
            except device.KeyboardError:
                level = None
            GLib.idle_add(show, level)

        def show(level):
            # may have been unplugged in the meantime
            if self.kind == device.DONGLE and level is not None:
                self.battery.set_label(f"Battery {level}%")
                self.battery.set_visible(True)
            else:
                self.battery.set_visible(False)
            return GLib.SOURCE_REMOVE

        threading.Thread(target=work, daemon=True).start()

    def toast(self, text):
        self.toasts.add_toast(Adw.Toast(title=text, timeout=3))

    def send(self, job, done_text, on_done=None):
        """Run job(keyboard) without freezing the window."""
        if self.busy:
            return
        self.busy = True
        self._refresh_buttons()

        def work():
            error = None
            try:
                device.run(job)
            except device.KeyboardError as e:
                error = str(e)
            GLib.idle_add(finished, error)

        def finished(error):
            self.busy = False
            self._refresh_buttons()
            self.toast(error or done_text)
            if error is None:
                store.save(self.settings)
                if on_done:
                    on_done()
            return GLib.SOURCE_REMOVE

        threading.Thread(target=work, daemon=True).start()


class Application(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID,
                         flags=Gio.ApplicationFlags.DEFAULT_FLAGS)

    def do_activate(self):
        Gtk.Window.set_default_icon_name(APP_ID)
        window = self.props.active_window or Window(self)
        window.present()
