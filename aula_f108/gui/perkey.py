from gi.repository import Adw, Gdk, Gtk

from .. import keys
from .keyboard import KeyboardView
from .lighting import apply_button, color_from, level_scale, rgba_from

SWATCHES = [
    (255, 0, 0), (255, 110, 0), (255, 220, 0), (0, 220, 60),
    (0, 210, 255), (0, 80, 255), (170, 0, 255), (255, 255, 255),
]


class PerKeyPage(Gtk.ScrolledWindow):
    def __init__(self, window):
        super().__init__(hscrollbar_policy=Gtk.PolicyType.NEVER)
        self.window = window
        saved = window.settings["per_key"]
        self.colors = {name: tuple(c) for name, c in saved["colors"].items()
                       if name in keys.BY_NAME}

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18,
                      margin_top=24, margin_bottom=24,
                      margin_start=18, margin_end=18)
        self.set_child(Adw.Clamp(child=box, maximum_size=1100))

        tools = Gtk.Box(spacing=8)
        box.append(tools)

        self.color = Gtk.ColorDialogButton(
            dialog=Gtk.ColorDialog(with_alpha=False))
        self.color.set_rgba(rgba_from(saved["brush"]))
        self.color.set_tooltip_text("Paint colour")
        tools.append(self.color)

        css = []
        for i, rgb in enumerate(SWATCHES):
            swatch = Gtk.Button(valign=Gtk.Align.CENTER)
            swatch.add_css_class("swatch")
            swatch.add_css_class(f"swatch-{i}")
            swatch.connect("clicked", self._pick, rgb)
            tools.append(swatch)
            css.append(".swatch-%d { background: rgb(%d,%d,%d); }" % (i, *rgb))
        css.append(".swatch { min-width: 22px; min-height: 22px; padding: 0;"
                   " border-radius: 11px; }")
        provider = Gtk.CssProvider()
        provider.load_from_data("\n".join(css).encode())
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        tools.append(Gtk.Box(hexpand=True))

        fill = Gtk.Button(label="Fill all")
        fill.connect("clicked", self._fill)
        tools.append(fill)
        clear = Gtk.Button(label="Clear")
        clear.connect("clicked", self._clear)
        tools.append(clear)

        self.view = KeyboardView(self.colors, self._paint)
        box.append(self.view)

        hint = Gtk.Label(label="Click or drag to paint. Right click turns a "
                               "key off.")
        hint.add_css_class("dim-label")
        box.append(hint)

        bright = Gtk.Box(spacing=12, halign=Gtk.Align.CENTER)
        bright.append(Gtk.Label(label="Brightness"))
        self.brightness = level_scale(saved["brightness"])
        bright.append(self.brightness)
        box.append(bright)

        button = apply_button()
        button.connect("clicked", self._apply)
        window.watch_button(button)
        box.append(button)

    def _brush(self):
        return tuple(color_from(self.color.get_rgba()))

    def _pick(self, _button, rgb):
        self.color.set_rgba(rgba_from(rgb))

    def _paint(self, key, button):
        if button == Gdk.BUTTON_SECONDARY:
            self.colors.pop(key.name, None)
        else:
            self.colors[key.name] = self._brush()

    def _fill(self, _button):
        brush = self._brush()
        for key in keys.KEYS:
            self.colors[key.name] = brush
        self.view.queue_draw()

    def _clear(self, _button):
        self.colors.clear()
        self.view.queue_draw()

    def _apply(self, _button):
        brightness = int(self.brightness.get_value())
        self.window.settings["per_key"] = {
            "brightness": brightness,
            "brush": list(self._brush()),
            "colors": {name: list(c) for name, c in self.colors.items()},
        }
        table = {keys.BY_NAME[name].index: c
                 for name, c in self.colors.items()}
        self.window.send(lambda kb: kb.per_key(table, brightness),
                         "Key colours updated")
