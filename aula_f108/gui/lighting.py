from gi.repository import Adw, Gdk, Gtk

from .. import protocol


def level_scale(value):
    scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0,
                                     protocol.MAX_LEVEL, 1)
    scale.set_value(value)
    scale.set_draw_value(True)
    scale.set_digits(0)
    scale.set_value_pos(Gtk.PositionType.RIGHT)
    scale.set_size_request(240, -1)
    scale.set_valign(Gtk.Align.CENTER)
    return scale


def rgba_from(color):
    rgba = Gdk.RGBA()
    rgba.red, rgba.green, rgba.blue = (c / 255 for c in color)
    rgba.alpha = 1.0
    return rgba


def color_from(rgba):
    return [round(rgba.red * 255), round(rgba.green * 255),
            round(rgba.blue * 255)]


def apply_button(label="Apply"):
    button = Gtk.Button(label=label, halign=Gtk.Align.CENTER)
    button.add_css_class("suggested-action")
    button.add_css_class("pill")
    return button


class LightingPage(Adw.PreferencesPage):
    def __init__(self, window):
        super().__init__()
        self.window = window
        saved = window.settings["lighting"]

        group = Adw.PreferencesGroup(title="Backlight")
        self.add(group)

        self.effect = Adw.ComboRow(title="Effect")
        self.effect.set_model(Gtk.StringList.new(
            [e.name for e in protocol.EFFECTS]))
        self.effect.set_selected(saved["effect"])
        self.effect.connect("notify::selected", self._update_rows)
        group.add(self.effect)

        self.brightness = level_scale(saved["brightness"])
        self.brightness_row = Adw.ActionRow(title="Brightness")
        self.brightness_row.add_suffix(self.brightness)
        group.add(self.brightness_row)

        self.speed = level_scale(saved["speed"])
        self.speed_row = Adw.ActionRow(title="Speed")
        self.speed_row.add_suffix(self.speed)
        group.add(self.speed_row)

        self.reverse = Adw.SwitchRow(title="Reverse direction")
        self.reverse.set_active(saved["reverse"])
        group.add(self.reverse)

        group = Adw.PreferencesGroup(title="Colour")
        self.add(group)

        self.rainbow = Adw.SwitchRow(
            title="Rainbow", subtitle="Cycle through colours instead of using one")
        self.rainbow.set_active(saved["rainbow"])
        self.rainbow.connect("notify::active", self._update_rows)
        group.add(self.rainbow)

        self.color = Gtk.ColorDialogButton(
            dialog=Gtk.ColorDialog(with_alpha=False), valign=Gtk.Align.CENTER)
        self.color.set_rgba(rgba_from(saved["color"]))
        self.color_row = Adw.ActionRow(title="Colour",
                                       activatable_widget=self.color)
        self.color_row.add_suffix(self.color)
        group.add(self.color_row)
        self.color_group = group

        group = Adw.PreferencesGroup()
        self.add(group)
        button = apply_button()
        button.connect("clicked", self._apply)
        window.watch_button(button)
        group.add(button)

        self._update_rows()

    def _update_rows(self, *_):
        controls = protocol.EFFECTS[self.effect.get_selected()].controls
        self.brightness_row.set_sensitive(controls & protocol.BRIGHTNESS)
        self.speed_row.set_sensitive(controls & protocol.SPEED)
        self.reverse.set_sensitive(controls & protocol.DIRECTION)
        has_color = bool(controls & protocol.COLOR)
        self.color_group.set_sensitive(has_color)
        self.color_row.set_sensitive(has_color and not self.rainbow.get_active())

    def _apply(self, _button):
        values = {
            "effect": self.effect.get_selected(),
            "color": color_from(self.color.get_rgba()),
            "brightness": int(self.brightness.get_value()),
            "speed": int(self.speed.get_value()),
            "reverse": self.reverse.get_active(),
            "rainbow": self.rainbow.get_active(),
        }
        self.window.settings["lighting"] = values
        self.window.send(
            lambda kb: kb.lighting(values["effect"], values["color"],
                                   values["brightness"], values["speed"],
                                   values["reverse"], values["rainbow"]),
            "Lighting updated")
