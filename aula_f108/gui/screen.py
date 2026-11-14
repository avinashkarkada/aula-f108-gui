import datetime

from gi.repository import Adw, Gtk


class ScreenPage(Adw.PreferencesPage):
    def __init__(self, window):
        super().__init__()
        self.window = window

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

    def _sync(self, _button):
        self.window.send(lambda kb: kb.clock(datetime.datetime.now()),
                         "Clock set")
