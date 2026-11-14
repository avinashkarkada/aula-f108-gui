"""What a remapped key should send.

A binding is written as a short string:

    lctrl            another key
    ctrl+shift+c     a key with modifiers held
    media:play       a media control
    mouse:lclick     a mouse button or scroll step

`slot()` turns one into the four bytes the firmware stores per key.
"""

from . import keys

MODIFIERS = {"ctrl": 0x01, "shift": 0x02, "alt": 0x04, "super": 0x08}

MEDIA = {
    "play": (0xCD, "Play / pause"),
    "stop": (0xB7, "Stop"),
    "prev": (0xB6, "Previous track"),
    "next": (0xB5, "Next track"),
    "volup": (0xE9, "Volume up"),
    "voldown": (0xEA, "Volume down"),
    "mute": (0xE2, "Mute"),
}

MOUSE = {
    "lclick": ((0x01, 0x00, 0x00), "Left click"),
    "rclick": ((0x02, 0x00, 0x00), "Right click"),
    "mclick": ((0x04, 0x00, 0x00), "Middle click"),
    "scrollup": ((0x00, 0x01, 0x00), "Scroll up"),
    "scrolldown": ((0x00, 0xFF, 0x00), "Scroll down"),
}

# Fn is handled inside the keyboard. Remapping it away would also take the
# mode switching shortcuts with it, so it stays where it is.
FIXED = {"fn"}

_TITLES = {
    "esc": "Escape", "grave": "` ~", "minus": "- _", "equal": "= +",
    "backspace": "Backspace", "tab": "Tab", "lbracket": "[ {",
    "rbracket": "] }", "backslash": "\\ |", "capslock": "Caps Lock",
    "semicolon": "; :", "quote": "' \"", "enter": "Enter",
    "lshift": "Left Shift", "rshift": "Right Shift", "comma": ", <",
    "dot": ". >", "slash": "/ ?", "lctrl": "Left Ctrl", "rctrl": "Right Ctrl",
    "lalt": "Left Alt", "ralt": "Right Alt", "lwin": "Super", "fn": "Fn",
    "menu": "Menu", "space": "Space", "printscreen": "Print Screen",
    "scrolllock": "Scroll Lock", "pause": "Pause", "insert": "Insert",
    "home": "Home", "pageup": "Page Up", "delete": "Delete", "end": "End",
    "pagedown": "Page Down", "up": "Up", "down": "Down", "left": "Left",
    "right": "Right", "numlock": "Num Lock", "numenter": "Numpad Enter",
}


def title(key):
    """Readable name for a key, for lists and messages."""
    if key.name in _TITLES:
        return _TITLES[key.name]
    if key.name.startswith("num"):
        return "Numpad " + key.label
    return key.label


def slot(binding):
    """Four firmware bytes for a binding. Raises ValueError if it makes no
    sense."""
    binding = binding.strip().lower()
    kind, sep, what = binding.partition(":")
    if sep:
        if kind == "media" and what in MEDIA:
            return bytes((0x03, MEDIA[what][0], 0, 0))
        if kind == "mouse" and what in MOUSE:
            return bytes((0x07, *MOUSE[what][0]))
        raise ValueError(f"unknown action {binding!r}")

    *held, name = binding.split("+")
    mods = 0
    for mod in held:
        if mod not in MODIFIERS:
            raise ValueError(f"unknown modifier {mod!r}")
        mods |= MODIFIERS[mod]
    key = keys.BY_NAME.get(name)
    if key is None or name in FIXED:
        raise ValueError(f"unknown key {name!r}")
    if 0xE0 <= key.hid <= 0xE7:
        # modifiers live in the bitmask, not in the key byte
        return bytes((0x02, mods | 1 << (key.hid - 0xE0), 0, 0))
    return bytes((0x02, mods, key.hid, 0))


def describe(binding):
    kind, sep, what = binding.partition(":")
    if sep:
        table = MEDIA if kind == "media" else MOUSE
        return table[what][1]
    *held, name = binding.split("+")
    parts = [m.capitalize() for m in held] + [title(keys.BY_NAME[name])]
    return " + ".join(parts)


def table(bindings):
    """Slots keyed by firmware index, from a {key name: binding} dict."""
    slots = {}
    for name, binding in bindings.items():
        if name not in keys.BY_NAME:
            raise ValueError(f"unknown key {name!r}")
        if name in FIXED:
            raise ValueError(f"{title(keys.BY_NAME[name])} can't be remapped")
        slots[keys.BY_NAME[name].index] = slot(binding)
    return slots
