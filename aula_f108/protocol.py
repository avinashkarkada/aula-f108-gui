"""Packet builders for the wired (USB-C) configuration protocol.

Everything goes over 64-byte HID feature reports on interface 3. A change is
a short transaction: begin, an init packet naming what is being written, the
data, then apply/finalize. Some packets have to be followed by a GET_REPORT
or the keyboard drops the rest of the sequence, hence the `readback` flag.

Nothing in here touches the device, the functions only return the list of
packets to send.

Protocol details come from the reverse engineering notes in
https://github.com/parsiya/f108-pro
"""

from collections import namedtuple
from dataclasses import dataclass

REPORT_SIZE = 64
TABLE_SIZE = 0x240  # per-key tables: 144 slots of 4 bytes
MAX_SLOT = 142      # last slot that doesn't run into the trailer

Step = namedtuple("Step", "payload readback")


def _packet(head=(), at=None):
    buf = bytearray(REPORT_SIZE)
    buf[:len(head)] = bytes(head)
    for offset, value in (at or {}).items():
        buf[offset] = value
    return bytes(buf)


def _begin():
    return Step(_packet((0x04, 0x18)), True)


def _apply():
    return Step(_packet((0x04, 0x02)), True)


def _finalize(readback=False):
    return Step(_packet((0x04, 0xF0)), readback)


def _chunks(data):
    return [data[i:i + REPORT_SIZE] for i in range(0, len(data), REPORT_SIZE)]


# --- backlight effects -----------------------------------------------------

# which controls make sense for an effect
BRIGHTNESS = 0x01
SPEED = 0x02
DIRECTION = 0x04
COLOR = 0x08


@dataclass(frozen=True)
class Effect:
    id: int
    name: str
    controls: int


_BS = BRIGHTNESS | SPEED

EFFECTS = [
    Effect(0, "Off", 0),
    Effect(1, "Static", BRIGHTNESS | COLOR),
    Effect(2, "Single on", _BS | COLOR),
    Effect(3, "Single off", _BS | COLOR),
    Effect(4, "Glittering", _BS | COLOR),
    Effect(5, "Falling", _BS | COLOR),
    Effect(6, "Colourful", _BS),
    Effect(7, "Breath", _BS | COLOR),
    Effect(8, "Spectrum", _BS),
    Effect(9, "Outward", _BS | COLOR),
    Effect(10, "Scrolling", _BS | COLOR | DIRECTION),
    Effect(11, "Rolling", _BS | COLOR | DIRECTION),
    Effect(12, "Rotating", _BS | COLOR | DIRECTION),
    Effect(13, "Explode", _BS | COLOR),
    Effect(14, "Launch", _BS | COLOR),
    Effect(15, "Ripples", _BS | COLOR),
    Effect(16, "Flowing", _BS | COLOR | DIRECTION),
    Effect(17, "Pulsating", _BS | COLOR),
    Effect(18, "Tilt", _BS | COLOR | DIRECTION),
    Effect(19, "Shuttle", _BS | COLOR),
]

CUSTOM_MODE = 0x80  # per-key colours
MAX_LEVEL = 5       # brightness and speed both go 0..5


def _level(value, what):
    if not 0 <= value <= MAX_LEVEL:
        raise ValueError(f"{what} must be 0-{MAX_LEVEL}, got {value}")
    return value


def _light_init():
    return Step(_packet((0x04, 0x13), {8: 0x01}), True)


def lighting(effect, color=(255, 255, 255), brightness=5, speed=3,
             direction=0, rainbow=False):
    """Switch the backlight to one of the built-in effects."""
    if not 0 <= effect < len(EFFECTS):
        raise ValueError(f"unknown effect {effect}")
    _level(brightness, "brightness")
    _level(speed, "speed")

    at = {14: 0x55, 15: 0xAA}
    if effect != 0:
        r, g, b = color
        at.update({1: r, 2: g, 3: b, 8: int(bool(rainbow)), 9: brightness,
                   10: speed, 11: int(bool(direction))})
    data = _packet((effect,), at)
    return [_begin(), _light_init(), Step(data, False), _apply(), _finalize()]


def per_key(colors, brightness=5):
    """Custom lighting. `colors` maps key index -> (r, g, b); keys that are
    left out stay dark."""
    _level(brightness, "brightness")

    # the keyboard has to be put in custom mode first
    mode = _packet((CUSTOM_MODE,), {9: brightness, 14: 0x55, 15: 0xAA})
    steps = [_begin(), _light_init(), Step(mode, False), _apply(), _finalize()]

    table = bytearray(TABLE_SIZE)
    for index, (r, g, b) in colors.items():
        if not 1 <= index <= MAX_SLOT:
            raise ValueError(f"bad key index {index}")
        table[index * 4:index * 4 + 4] = bytes((index, r, g, b))
    table[-2:] = b"\x55\xAA"

    steps += [_begin(), Step(_packet((0x04, 0x23), {8: 0x09}), True)]
    chunks = _chunks(bytes(table))
    for i, chunk in enumerate(chunks):
        steps.append(Step(chunk, i == len(chunks) - 1))
    steps += [_apply(), _finalize(readback=True)]
    return steps


# --- key remapping ---------------------------------------------------------

def remap(slots):
    """Replace the remap table. `slots` maps key index -> 4 bytes (see
    remap.py); keys that are left out go back to normal, so an empty dict
    resets everything."""
    table = bytearray(TABLE_SIZE)
    for index, slot in slots.items():
        if not 1 <= index <= MAX_SLOT:
            raise ValueError(f"bad key index {index}")
        if len(slot) != 4:
            raise ValueError("a slot is 4 bytes")
        table[index * 4:index * 4 + 4] = slot
    # byte order of the trailer is the other way round here
    table[-2:] = b"\xAA\x55"

    steps = [_begin(), Step(_packet((0x04, 0x11), {8: 0x09}), True)]
    steps += [Step(chunk, False) for chunk in _chunks(bytes(table))]
    steps += [_apply(), _finalize(readback=True)]
    return steps


# --- screen ----------------------------------------------------------------

def clock(now):
    """Set the clock shown on the LCD. `now` is a datetime."""
    data = _packet((0x00, 0x01, 0x5A), {
        3: now.year % 100,
        4: now.month,
        5: now.day,
        6: now.hour,
        7: now.minute,
        8: now.second,
        10: now.isoweekday() % 7,  # sunday = 0
        62: 0x55,
        63: 0xAA,
    })
    return [_begin(), Step(_packet((0x04, 0x28), {8: 0x01}), True),
            Step(data, True), _apply()]
