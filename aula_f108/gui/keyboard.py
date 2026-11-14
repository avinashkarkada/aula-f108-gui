import math

import gi

gi.require_version("PangoCairo", "1.0")
from gi.repository import Gtk, Pango, PangoCairo  # noqa: E402

from .. import keys

GAP = 0.06      # space around each key, in key units
RADIUS = 0.14
UNLIT = (0.23, 0.23, 0.25)


class KeyboardView(Gtk.DrawingArea):
    """Picture of the keyboard. Keys are filled with whatever `colors` says
    (key name -> (r, g, b)); `on_key(key, button)` fires for clicks and for
    every key the pointer is dragged over."""

    def __init__(self, colors, on_key):
        super().__init__()
        self.colors = colors
        self.on_key = on_key
        self._last = None
        self._origin = (0.0, 0.0)

        self.set_content_width(860)
        self.set_content_height(250)
        self.set_hexpand(True)
        self.set_draw_func(self._draw)

        drag = Gtk.GestureDrag()
        drag.set_button(0)
        drag.connect("drag-begin", self._drag_begin)
        drag.connect("drag-update", self._drag_update)
        self.add_controller(drag)

    def _geometry(self):
        width, height = self.get_width(), self.get_height()
        unit = min(width / keys.WIDTH, height / keys.HEIGHT)
        left = (width - keys.WIDTH * unit) / 2
        top = (height - keys.HEIGHT * unit) / 2
        return unit, left, top

    def _hit(self, gesture, x, y):
        unit, left, top = self._geometry()
        key = keys.key_at((x - left) / unit, (y - top) / unit)
        if key is not None and key is not self._last:
            self._last = key
            self.on_key(key, gesture.get_current_button())
            self.queue_draw()

    def _drag_begin(self, gesture, x, y):
        self._last = None
        self._origin = (x, y)
        self._hit(gesture, x, y)

    def _drag_update(self, gesture, dx, dy):
        self._hit(gesture, self._origin[0] + dx, self._origin[1] + dy)

    def _draw(self, _area, cr, _width, _height):
        unit, left, top = self._geometry()
        radius = RADIUS * unit
        layout = self.create_pango_layout("")
        font = Pango.FontDescription("Sans")

        for key in keys.KEYS:
            color = self.colors.get(key.name)
            if color and any(color):
                fill = tuple(c / 255 for c in color)
            else:
                fill = UNLIT
            x = left + (key.x + GAP) * unit
            y = top + (key.y + GAP) * unit
            w = (key.w - 2 * GAP) * unit
            h = (key.h - 2 * GAP) * unit

            cr.new_sub_path()
            cr.arc(x + w - radius, y + radius, radius, -math.pi / 2, 0)
            cr.arc(x + w - radius, y + h - radius, radius, 0, math.pi / 2)
            cr.arc(x + radius, y + h - radius, radius, math.pi / 2, math.pi)
            cr.arc(x + radius, y + radius, radius, math.pi, 1.5 * math.pi)
            cr.close_path()
            cr.set_source_rgb(*fill)
            cr.fill()

            if not key.label:
                continue
            # dark text on bright keys and the other way round
            bright = 0.299 * fill[0] + 0.587 * fill[1] + 0.114 * fill[2]
            cr.set_source_rgb(*((0.1,) * 3 if bright > 0.6 else (0.92,) * 3))
            size = 0.27 if len(key.label) > 1 else 0.34
            font.set_absolute_size(size * unit * Pango.SCALE)
            layout.set_font_description(font)
            layout.set_text(key.label)
            text_w, text_h = layout.get_pixel_size()
            cr.move_to(x + (w - text_w) / 2, y + (h - text_h) / 2)
            PangoCairo.show_layout(cr, layout)
