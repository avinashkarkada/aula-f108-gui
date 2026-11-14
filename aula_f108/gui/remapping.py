from gi.repository import Adw, Gtk

from .. import keys, protocol, remap
from .keyboard import KeyboardView
from .lighting import apply_button

CHANGED = (53, 132, 228)

KINDS = ["Itself", "Another key", "Media control", "Mouse"]
TARGETS = [k for k in keys.KEYS if k.name not in remap.FIXED]
MEDIA = list(remap.MEDIA)
MOUSE = list(remap.MOUSE)
MODS = list(remap.MODIFIERS)


def combo(title, labels):
    row = Adw.ComboRow(title=title)
    row.set_model(Gtk.StringList.new(labels))
    return row


class RemapPage(Gtk.ScrolledWindow):
    def __init__(self, window):
        super().__init__(hscrollbar_policy=Gtk.PolicyType.NEVER)
        self.window = window
        self.bindings = {}
        for name, binding in window.settings["remap"].items():
            try:
                remap.table({name: binding})
            except ValueError:
                continue    # left over from an older version, drop it
            self.bindings[name] = binding
        self.current = None
        self._loading = False

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18,
                      margin_top=24, margin_bottom=24,
                      margin_start=18, margin_end=18)
        self.set_child(Adw.Clamp(child=box, maximum_size=1100))

        self.marks = {}
        self.view = KeyboardView(self.marks, self._select)
        box.append(self.view)

        self.group = Adw.PreferencesGroup()
        box.append(Adw.Clamp(child=self.group, maximum_size=600))

        self.kind = combo("Sends", KINDS)
        self.kind.connect("notify::selected", self._edited)
        self.group.add(self.kind)

        self.target = combo("Key", [remap.title(k) for k in TARGETS])
        self.target.connect("notify::selected", self._edited)
        self.group.add(self.target)

        self.mods_row = Adw.ActionRow(title="Held together with")
        mods = Gtk.Box(spacing=6, valign=Gtk.Align.CENTER)
        self.mods = {}
        for name in MODS:
            toggle = Gtk.ToggleButton(label=name.capitalize())
            toggle.connect("toggled", self._edited)
            mods.append(toggle)
            self.mods[name] = toggle
        self.mods_row.add_suffix(mods)
        self.group.add(self.mods_row)

        self.media = combo("Control", [remap.MEDIA[m][1] for m in MEDIA])
        self.media.connect("notify::selected", self._edited)
        self.group.add(self.media)

        self.mouse = combo("Action", [remap.MOUSE[m][1] for m in MOUSE])
        self.mouse.connect("notify::selected", self._edited)
        self.group.add(self.mouse)

        buttons = Gtk.Box(spacing=12, halign=Gtk.Align.CENTER)
        reset = Gtk.Button(label="Reset all")
        reset.add_css_class("pill")
        reset.connect("clicked", self._reset)
        buttons.append(reset)
        button = apply_button()
        button.connect("clicked", self._apply)
        window.watch_button(button)
        buttons.append(button)
        box.append(buttons)

        hint = Gtk.Label(label="Changed keys are shown in blue. Nothing is "
                               "sent to the keyboard until you press Apply.")
        hint.add_css_class("dim-label")
        box.append(hint)

        self._refresh_marks()
        self._load(None)

    def _refresh_marks(self):
        self.marks.clear()
        for name in self.bindings:
            self.marks[name] = CHANGED
        self.view.queue_draw()

    def _select(self, key, _button):
        self._load(key)

    def _load(self, key):
        """Show the binding of `key` in the editor."""
        self._loading = True
        self.current = key
        self.view.selected = key.name if key else None

        fixed = key is not None and key.name in remap.FIXED
        if key is None:
            self.group.set_title("Pick a key")
            self.group.set_description("")
        elif fixed:
            self.group.set_title(remap.title(key))
            self.group.set_description("This key can't be remapped.")
        else:
            self.group.set_title(remap.title(key))
            self.group.set_description("")
        self.kind.set_sensitive(key is not None and not fixed)

        binding = self.bindings.get(key.name) if key else None
        kind, sep, what = (binding or "").partition(":")
        for toggle in self.mods.values():
            toggle.set_active(False)
        if not binding:
            self.kind.set_selected(0)
        elif sep and kind == "media":
            self.kind.set_selected(2)
            self.media.set_selected(MEDIA.index(what))
        elif sep:
            self.kind.set_selected(3)
            self.mouse.set_selected(MOUSE.index(what))
        else:
            *held, name = binding.split("+")
            self.kind.set_selected(1)
            self.target.set_selected(TARGETS.index(keys.BY_NAME[name]))
            for mod in held:
                self.mods[mod].set_active(True)

        self._loading = False
        self._show_rows()
        self.view.queue_draw()

    def _show_rows(self):
        kind = self.kind.get_selected()
        self.target.set_visible(kind == 1)
        self.mods_row.set_visible(kind == 1)
        self.media.set_visible(kind == 2)
        self.mouse.set_visible(kind == 3)

    def _edited(self, *_):
        if self._loading or self.current is None:
            return
        if self.current.name in remap.FIXED:
            return
        self._show_rows()
        kind = self.kind.get_selected()
        name = self.current.name
        if kind == 0:
            self.bindings.pop(name, None)
        elif kind == 1:
            held = [m for m in MODS if self.mods[m].get_active()]
            target = TARGETS[self.target.get_selected()].name
            if target == name and not held:
                self.bindings.pop(name, None)   # a key mapped to itself
            else:
                self.bindings[name] = "+".join(held + [target])
        elif kind == 2:
            self.bindings[name] = "media:" + MEDIA[self.media.get_selected()]
        else:
            self.bindings[name] = "mouse:" + MOUSE[self.mouse.get_selected()]
        self._refresh_marks()

    def _reset(self, _button):
        self.bindings.clear()
        self._refresh_marks()
        self._load(self.current)

    def _apply(self, _button):
        self.window.settings["remap"] = dict(self.bindings)
        count = len(self.bindings)
        done = ("Keys are back to normal" if count == 0 else
                f"{count} key{'s' if count != 1 else ''} remapped")
        self.window.send(protocol.remap(remap.table(self.bindings)), done)
