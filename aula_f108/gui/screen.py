import datetime
import os
import threading

from gi.repository import Adw, Gdk, GLib, Gtk

from .. import device, lcd

PREVIEW_SCALE = 1.5


class ScreenPage(Adw.PreferencesPage):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.data = None        # ready-to-send picture
        self.textures = []
        self.delays = []
        self._shown = 0
        self._timer = 0

        group = Adw.PreferencesGroup(
            title="Picture",
            description="A picture or GIF for the keyboard's screen. It is "
                        "scaled to fit, and animations longer than "
                        f"{lcd.MAX_FRAMES} frames are thinned out. This only "
                        "works over the USB cable.")
        self.add(group)

        self.preview = Gtk.Picture(can_shrink=False,
                                   content_fit=Gtk.ContentFit.FILL)
        self.preview.set_size_request(round(lcd.WIDTH * PREVIEW_SCALE),
                                      round(lcd.HEIGHT * PREVIEW_SCALE))
        frame = Gtk.Frame(child=self.preview, halign=Gtk.Align.CENTER,
                          margin_top=6, margin_bottom=12)
        group.add(frame)

        self.file_row = Adw.ActionRow(title="No file chosen")
        choose = Gtk.Button(label="Choose…", valign=Gtk.Align.CENTER)
        choose.connect("clicked", self._choose)
        self.file_row.add_suffix(choose)
        group.add(self.file_row)

        self.progress = Gtk.ProgressBar(visible=False, margin_top=12)
        group.add(self.progress)

        self.upload = Gtk.Button(label="Send to keyboard",
                                 halign=Gtk.Align.CENTER, margin_top=12)
        self.upload.add_css_class("suggested-action")
        self.upload.add_css_class("pill")
        self.upload.connect("clicked", self._confirm)
        window.watch_button(self.upload, cable_only=True,
                            ready=lambda: self.data is not None)
        group.add(self.upload)

        # says why the button is greyed out
        self.hint = Gtk.Label(wrap=True, justify=Gtk.Justification.CENTER,
                              margin_top=8)
        self.hint.add_css_class("dim-label")
        group.add(self.hint)
        window.watch_connection(self._connection_changed)

        group = Adw.PreferencesGroup(title="Clock")
        self.add(group)

        row = Adw.ActionRow(
            title="Set the clock",
            subtitle="Copies the date and time from this computer")
        button = Gtk.Button(label="Sync now", valign=Gtk.Align.CENTER)
        button.connect("clicked", self._sync)
        window.watch_button(button)
        row.add_suffix(button)
        group.add(row)

    def _connection_changed(self, kind):
        if kind == device.USB:
            text = ""
        elif kind == device.DONGLE:
            text = ("Pictures can't be sent through the 2.4G receiver. Plug "
                    "in the USB cable and switch the keyboard to USB mode.")
        else:
            text = "Connect the keyboard with the USB cable to send a picture."
        self.hint.set_label(text)
        self.hint.set_visible(bool(text))

    # --- choosing and previewing ---

    def _choose(self, _button):
        images = Gtk.FileFilter()
        images.set_name("Pictures")
        images.add_mime_type("image/*")
        dialog = Gtk.FileDialog(title="Choose a picture or GIF", modal=True,
                                default_filter=images)
        dialog.open(self.window, None, self._chosen)

    def _chosen(self, dialog, result):
        try:
            path = dialog.open_finish(result).get_path()
        except GLib.Error:
            return      # cancelled
        self.load(path)

    def load(self, path):
        self.file_row.set_title(os.path.basename(path))
        self.file_row.set_subtitle("Reading…")

        def work():
            try:
                frames, delays, original = lcd.load(path)
                data = lcd.build(frames, delays)
                raw = [frame.tobytes() for frame in frames]
                error = None
            except ImportError:
                error = "Pictures need Pillow (python3-pil)."
            except (OSError, ValueError, SyntaxError) as e:
                error = f"Can't use this file: {e}"
            if error:
                GLib.idle_add(self._failed, error)
            else:
                GLib.idle_add(self._loaded, data, raw, delays, original)

        threading.Thread(target=work, daemon=True).start()

    def _failed(self, error):
        self.data = None
        self.textures = []
        self._stop_preview()
        self.preview.set_paintable(None)
        self.file_row.set_subtitle("")
        self.window.toast(error)
        self.window.refresh_buttons()
        return GLib.SOURCE_REMOVE

    def _loaded(self, data, raw, delays, original):
        self.data = data
        self.delays = delays
        self.textures = [
            Gdk.MemoryTexture.new(lcd.WIDTH, lcd.HEIGHT,
                                  Gdk.MemoryFormat.R8G8B8,
                                  GLib.Bytes.new(pixels), lcd.WIDTH * 3)
            for pixels in raw]

        count = len(raw)
        seconds = round(lcd.seconds(lcd.check(data)))
        if count == 1:
            text = "Still picture"
        else:
            text = f"{count} frames"
            if original > count:
                text += f" (cut down from {original})"
        self.file_row.set_subtitle(f"{text}, about {seconds} s to send")

        self._stop_preview()
        self._shown = -1
        self._next_frame()
        self.window.refresh_buttons()
        return GLib.SOURCE_REMOVE

    def _stop_preview(self):
        if self._timer:
            GLib.source_remove(self._timer)
            self._timer = 0

    def _next_frame(self):
        self._timer = 0
        if not self.textures:
            return GLib.SOURCE_REMOVE
        self._shown = (self._shown + 1) % len(self.textures)
        self.preview.set_paintable(self.textures[self._shown])
        if len(self.textures) > 1:
            # same clamping the keyboard will apply
            delay = max(lcd.DELAY_STEP_MS,
                        min(lcd.MAX_DELAY_MS, self.delays[self._shown]))
            self._timer = GLib.timeout_add(delay, self._next_frame)
        return GLib.SOURCE_REMOVE

    # --- sending ---

    def _confirm(self, _button):
        dialog = Adw.MessageDialog(
            transient_for=self.window,
            heading="Replace the picture on the screen?",
            body="What the screen shows now will be overwritten. Leave the "
                 "cable plugged in until it has finished.")
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("send", "Send")
        dialog.set_response_appearance("send",
                                       Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.connect("response", self._answered)
        dialog.present()

    def _answered(self, _dialog, response):
        if response == "send":
            self.send()

    def send(self):
        data = self.data
        if data is None:
            return
        self.progress.set_fraction(0)
        self.progress.set_visible(True)

        def progress(done, total):
            GLib.idle_add(self.progress.set_fraction, done / total)

        self.window.send(
            lambda kb: kb.show_image(data, progress),
            "Picture sent. The keyboard may take a moment to save it.",
            after=lambda: self.progress.set_visible(False))

    def _sync(self, _button):
        self.window.send(lambda kb: kb.clock(datetime.datetime.now()),
                         "Clock set")
