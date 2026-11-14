"""Packet builders for the 2.4G receiver.

Over the receiver there is no begin/apply conversation like on the cable.
Every setting is one or more 32-byte frames:

    command, length, chunk number, up to 28 bytes of data, checksum

The checksum is the sum of the other 31 bytes. The receiver echoes the
first three bytes back once it has taken a frame. Small settings fit in one
frame; the two per-key tables are cut into 21 chunks.

This was worked out from the vendor's Windows software and by trying it on
one keyboard, so treat it as experimental.
"""

from . import protocol

FRAME_SIZE = 32
CHUNK_SIZE = 28

LIGHTING = 0x05
CLOCK = 0x0C
REMAP = 0x10
COLORS = 0x14
BATTERY = 0x20

TRAILER = b"\xAA\x55"


def frame(command, data=b"", index=0):
    data = bytes(data)
    if len(data) > CHUNK_SIZE:
        raise ValueError("too much data for one frame")
    buf = bytearray(FRAME_SIZE)
    buf[0] = command
    buf[1] = len(data)
    buf[2] = index
    buf[3:3 + len(data)] = data
    buf[31] = sum(buf[:31]) & 0xFF
    return bytes(buf)


def _table(command, table):
    table[-2:] = TRAILER
    return [frame(command, table[start:start + CHUNK_SIZE], number)
            for number, start in enumerate(range(0, len(table), CHUNK_SIZE))]


def _light(mode, color=(0, 0, 0), brightness=0, speed=0, direction=0,
           rainbow=False):
    # same 16 bytes the cable protocol sends as its data packet
    data = bytearray(16)
    data[0] = mode
    data[1:4] = bytes(color)
    data[8] = int(bool(rainbow))
    data[9] = brightness
    data[10] = speed
    data[11] = int(bool(direction))
    data[14:16] = TRAILER
    return frame(LIGHTING, data)


def lighting(effect, color=(255, 255, 255), brightness=5, speed=3,
             direction=0, rainbow=False):
    protocol.check_lighting(effect, brightness, speed)
    if effect == 0:
        return [_light(0)]
    return [_light(effect, color, brightness, speed, direction, rainbow)]


def per_key(colors, brightness=5):
    protocol.check_lighting(0, brightness, 0)
    return ([_light(protocol.CUSTOM_MODE, brightness=brightness)]
            + _table(COLORS, protocol.color_table(colors)))


def remap(slots):
    return _table(REMAP, protocol.slot_table(slots))


def clock(now):
    data = bytearray(16)
    data[1] = 0x01
    data[2] = 0x5A
    data[3] = now.year % 100
    data[4] = now.month
    data[5] = now.day
    data[6] = now.hour
    data[7] = now.minute
    data[8] = now.second
    data[10] = now.isoweekday() % 7   # sunday = 0
    data[14:16] = TRAILER
    return [frame(CLOCK, data)]


def battery_query():
    return frame(BATTERY, b"\x00")


def battery_level(reply):
    """Charge in percent from the answer to battery_query(), or None if the
    keyboard didn't say."""
    level = reply[3]
    return min(level, 100) if level else None
