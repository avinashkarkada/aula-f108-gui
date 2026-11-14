"""Talking to the keyboard through hidraw.

No libusb needed: the kernel already exposes the vendor interfaces as
/dev/hidraw nodes. The keyboard can be reached two ways and they don't
work alike:

  cable     64-byte feature reports, sent with two ioctls
  receiver  32-byte reports, plain write() and read()

connect() picks whichever is there and gives back an object with the same
methods either way.
"""

import fcntl
import glob
import os
import select
import threading
import time
from collections import namedtuple

from . import protocol, wireless

WIRED_ID = (0x0C45, 0x800A)
DONGLE_ID = (0x05AC, 0x024F)   # the 2.4G receiver pretends to be an Apple keyboard
CONFIG_INTERFACE = 3           # same number on both

USB = "usb"
DONGLE = "dongle"

COMMAND_DELAY = 0.035

# receiver timing: how long to wait for the echo of a frame and how often
# to send it again when none comes (a frame gets lost now and then)
ECHO_WAIT = 0.25
RESENDS = 4
FRAME_GAP = 0.002

SYSFS_HIDRAW = "/sys/class/hidraw"

Link = namedtuple("Link", "kind path")

# one conversation with the keyboard at a time
_lock = threading.Lock()


class KeyboardError(Exception):
    pass


class NotFound(KeyboardError):
    pass


class AccessDenied(KeyboardError):
    pass


def _ioc(direction, nr, size):
    return (direction << 30) | (size << 16) | (ord("H") << 8) | nr


def _set_feature(size):
    return _ioc(3, 0x06, size)


def _get_feature(size):
    return _ioc(3, 0x07, size)


def _read(path):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return ""


def _scan(sysfs=SYSFS_HIDRAW):
    """Yield (vendor, product, interface, node name) for every hidraw device
    that sits on USB."""
    for entry in sorted(glob.glob(os.path.join(sysfs, "hidraw*"))):
        hid_dir = os.path.realpath(os.path.join(entry, "device"))
        ids = None
        for line in _read(os.path.join(hid_dir, "uevent")).splitlines():
            if line.startswith("HID_ID="):
                # HID_ID=0003:00000C45:0000800A
                parts = line.split("=", 1)[1].split(":")
                if len(parts) == 3:
                    ids = (int(parts[1], 16), int(parts[2], 16))
        if ids is None:
            continue
        iface = _read(os.path.join(os.path.dirname(hid_dir), "bInterfaceNumber"))
        if not iface:
            continue
        yield ids[0], ids[1], int(iface, 16), os.path.basename(entry)


def find(sysfs=SYSFS_HIDRAW):
    """Where the keyboard can be configured, as a Link.

    The cable wins when both are plugged in: a keyboard that shows up on
    USB is in USB mode and isn't listening to the receiver.
    """
    dongle = None
    for vendor, product, iface, node in _scan(sysfs):
        if iface != CONFIG_INTERFACE:
            continue
        if (vendor, product) == WIRED_ID:
            return Link(USB, "/dev/" + node)
        if (vendor, product) == DONGLE_ID:
            dongle = Link(DONGLE, "/dev/" + node)
    if dongle:
        return dongle
    raise NotFound("Keyboard not found. Plug in the USB cable or the 2.4G "
                   "receiver.")


def _open(path, flags):
    try:
        return os.open(path, flags)
    except PermissionError:
        raise AccessDenied(f"No permission to open {path}. Install the udev "
                           "rule from the udev/ folder and replug.") from None
    except OSError as e:
        raise KeyboardError(f"Could not open {path}: {e}") from None


class _Base:
    kind = None
    _fd = None

    def close(self):
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def lighting(self, effect, color=(255, 255, 255), brightness=5, speed=3,
                 direction=0, rainbow=False):
        self.send(self._packets.lighting(effect, color, brightness, speed,
                                         direction, rainbow))

    def per_key(self, colors, brightness=5):
        self.send(self._packets.per_key(colors, brightness))

    def remap(self, slots):
        self.send(self._packets.remap(slots))

    def clock(self, now):
        self.send(self._packets.clock(now))

    def battery(self):
        """Charge in percent, or None when it can't be read."""
        return None


class Keyboard(_Base):
    """The keyboard on its USB cable."""

    kind = USB
    _packets = protocol

    def __init__(self, path):
        self.path = path
        self._fd = _open(path, os.O_RDWR)

    def _set(self, payload):
        # leading zero is the report id, the interface doesn't use one
        buf = bytearray(b"\x00" + payload)
        fcntl.ioctl(self._fd, _set_feature(len(buf)), buf)

    def _get(self):
        buf = bytearray(65)
        fcntl.ioctl(self._fd, _get_feature(len(buf)), buf)
        return bytes(buf[1:])

    def send(self, steps, progress=None):
        """Run a list of protocol steps. `progress` is called with
        (done, total) after each packet."""
        total = len(steps)
        try:
            for i, step in enumerate(steps, 1):
                self._set(step.payload)
                time.sleep(COMMAND_DELAY)
                if step.readback:
                    reply = self._get()
                    time.sleep(COMMAND_DELAY)
                    # commands come back with their first two bytes echoed;
                    # anything else means the keyboard isn't following along
                    if (step.payload[0] == 0x04
                            and reply[:2] != step.payload[:2]):
                        raise KeyboardError(
                            "The keyboard didn't confirm the change. Replug "
                            "the cable and try again.")
                if progress:
                    progress(i, total)
        except OSError as e:
            raise KeyboardError(f"Lost contact with the keyboard: {e}") from None


class Dongle(_Base):
    """The keyboard through its 2.4G receiver."""

    kind = DONGLE
    _packets = wireless

    def __init__(self, path):
        self.path = path
        self._fd = _open(path, os.O_RDWR | os.O_NONBLOCK)

    def _write(self, frame):
        os.write(self._fd, b"\x00" + frame)     # no report id here either

    def _poll(self, timeout):
        """One report from the receiver, or None if nothing came in time."""
        ready, _, _ = select.select([self._fd], [], [], timeout)
        if not ready:
            return None
        try:
            return os.read(self._fd, 64)
        except BlockingIOError:
            return None

    def _exchange(self, frame):
        """Send a frame and wait for its echo, trying again a few times."""
        for _ in range(RESENDS + 1):
            while self._poll(0) is not None:    # drop anything stale
                pass
            self._write(frame)
            deadline = time.monotonic() + ECHO_WAIT
            while True:
                left = deadline - time.monotonic()
                if left <= 0:
                    break
                reply = self._poll(left)
                if reply is not None and reply[:3] == frame[:3]:
                    return reply
        raise KeyboardError("No answer through the receiver. Check that the "
                            "keyboard is switched on and in 2.4G mode.")

    def send(self, frames, progress=None):
        total = len(frames)
        try:
            for i, frame in enumerate(frames, 1):
                self._exchange(frame)
                time.sleep(FRAME_GAP)
                if progress:
                    progress(i, total)
        except OSError as e:
            raise KeyboardError(f"Lost contact with the receiver: {e}") from None

    def battery(self):
        try:
            reply = self._exchange(wireless.battery_query())
        except OSError as e:
            raise KeyboardError(f"Lost contact with the receiver: {e}") from None
        return wireless.battery_level(reply)


def connect(sysfs=SYSFS_HIDRAW):
    link = find(sysfs)
    return (Keyboard if link.kind == USB else Dongle)(link.path)


def run(job):
    """Open the keyboard, call job(keyboard) and close it again. Use this
    rather than connect() when other threads may be talking to it too."""
    with _lock:
        with connect() as keyboard:
            return job(keyboard)
