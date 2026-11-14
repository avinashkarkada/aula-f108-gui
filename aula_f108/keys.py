"""Key table for the F108 Pro (ANSI). 104 switches; the knob and screen take
the place of the four extra keys a 108 layout normally has.

`index` is the slot number the firmware uses for both lighting and remapping.
Positions are in key units (1u = one letter key) and only matter for drawing.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Key:
    name: str
    label: str
    index: int
    hid: int
    x: float
    y: float
    w: float = 1.0
    h: float = 1.0


WIDTH = 22.5
HEIGHT = 6.25

KEYS: list[Key] = []


def _run(y, x, items):
    for item in items:
        name, label, index, hid = item[:4]
        w = item[4] if len(item) > 4 else 1.0
        h = item[5] if len(item) > 5 else 1.0
        KEYS.append(Key(name, label, index, hid, x, y, w, h))
        x += w


NAV = 15.25
PAD = 18.5

# function row
_run(0, 0, [("esc", "Esc", 1, 0x29)])
_run(0, 2, [("f1", "F1", 2, 0x3A), ("f2", "F2", 3, 0x3B),
            ("f3", "F3", 4, 0x3C), ("f4", "F4", 5, 0x3D)])
_run(0, 6.5, [("f5", "F5", 6, 0x3E), ("f6", "F6", 7, 0x3F),
              ("f7", "F7", 8, 0x40), ("f8", "F8", 9, 0x41)])
_run(0, 11, [("f9", "F9", 10, 0x42), ("f10", "F10", 11, 0x43),
             ("f11", "F11", 12, 0x44), ("f12", "F12", 13, 0x45)])
_run(0, NAV, [("printscreen", "PrtSc", 112, 0x46),
              ("scrolllock", "ScrLk", 113, 0x47),
              ("pause", "Pause", 115, 0x48)])

# number row
_run(1.25, 0, [("grave", "`", 19, 0x35), ("1", "1", 20, 0x1E),
               ("2", "2", 21, 0x1F), ("3", "3", 22, 0x20),
               ("4", "4", 23, 0x21), ("5", "5", 24, 0x22),
               ("6", "6", 25, 0x23), ("7", "7", 26, 0x24),
               ("8", "8", 27, 0x25), ("9", "9", 28, 0x26),
               ("0", "0", 29, 0x27), ("minus", "-", 30, 0x2D),
               ("equal", "=", 31, 0x2E),
               ("backspace", "Bksp", 103, 0x2A, 2.0)])
_run(1.25, NAV, [("insert", "Ins", 116, 0x49), ("home", "Home", 117, 0x4A),
                 ("pageup", "PgUp", 118, 0x4B)])
_run(1.25, PAD, [("numlock", "Num", 32, 0x53), ("numslash", "/", 33, 0x54),
                 ("numstar", "*", 34, 0x55), ("numminus", "-", 122, 0x56)])

# qwerty row
_run(2.25, 0, [("tab", "Tab", 37, 0x2B, 1.5), ("q", "Q", 38, 0x14),
               ("w", "W", 39, 0x1A), ("e", "E", 40, 0x08),
               ("r", "R", 41, 0x15), ("t", "T", 42, 0x17),
               ("y", "Y", 43, 0x1C), ("u", "U", 44, 0x18),
               ("i", "I", 45, 0x0C), ("o", "O", 46, 0x12),
               ("p", "P", 47, 0x13), ("lbracket", "[", 48, 0x2F),
               ("rbracket", "]", 49, 0x30),
               ("backslash", "\\", 67, 0x31, 1.5)])
_run(2.25, NAV, [("delete", "Del", 119, 0x4C), ("end", "End", 120, 0x4D),
                 ("pagedown", "PgDn", 121, 0x4E)])
_run(2.25, PAD, [("num7", "7", 50, 0x5F), ("num8", "8", 51, 0x60),
                 ("num9", "9", 52, 0x61),
                 ("numplus", "+", 123, 0x57, 1.0, 2.0)])

# home row
_run(3.25, 0, [("capslock", "Caps", 55, 0x39, 1.75), ("a", "A", 56, 0x04),
               ("s", "S", 57, 0x16), ("d", "D", 58, 0x07),
               ("f", "F", 59, 0x09), ("g", "G", 60, 0x0A),
               ("h", "H", 61, 0x0B), ("j", "J", 62, 0x0D),
               ("k", "K", 63, 0x0E), ("l", "L", 64, 0x0F),
               ("semicolon", ";", 65, 0x33), ("quote", "'", 66, 0x34),
               ("enter", "Enter", 85, 0x28, 2.25)])
_run(3.25, PAD, [("num4", "4", 68, 0x5C), ("num5", "5", 69, 0x5D),
                 ("num6", "6", 70, 0x5E)])

# shift row
_run(4.25, 0, [("lshift", "Shift", 73, 0xE1, 2.25), ("z", "Z", 74, 0x1D),
               ("x", "X", 75, 0x1B), ("c", "C", 76, 0x06),
               ("v", "V", 77, 0x19), ("b", "B", 78, 0x05),
               ("n", "N", 79, 0x11), ("m", "M", 80, 0x10),
               ("comma", ",", 81, 0x36), ("dot", ".", 82, 0x37),
               ("slash", "/", 83, 0x38),
               ("rshift", "Shift", 84, 0xE5, 2.75)])
_run(4.25, NAV + 1, [("up", "↑", 101, 0x52)])
_run(4.25, PAD, [("num1", "1", 86, 0x59), ("num2", "2", 87, 0x5A),
                 ("num3", "3", 88, 0x5B),
                 ("numenter", "Ent", 106, 0x58, 1.0, 2.0)])

# bottom row
_run(5.25, 0, [("lctrl", "Ctrl", 91, 0xE0, 1.25),
               ("lwin", "Super", 92, 0xE3, 1.25),
               ("lalt", "Alt", 93, 0xE2, 1.25),
               ("space", "", 94, 0x2C, 6.25),
               ("ralt", "Alt", 95, 0xE6, 1.25),
               ("fn", "Fn", 96, 0xAF, 1.25),
               ("menu", "Menu", 97, 0x65, 1.25),
               ("rctrl", "Ctrl", 98, 0xE4, 1.25)])
_run(5.25, NAV, [("left", "←", 99, 0x50), ("down", "↓", 100, 0x51),
                 ("right", "→", 102, 0x4F)])
_run(5.25, PAD, [("num0", "0", 104, 0x62, 2.0), ("numdot", ".", 105, 0x63)])

BY_NAME = {k.name: k for k in KEYS}
BY_INDEX = {k.index: k for k in KEYS}


def key_at(x, y):
    """Key under a point given in key units, or None."""
    for k in KEYS:
        if k.x <= x < k.x + k.w and k.y <= y < k.y + k.h:
            return k
    return None
