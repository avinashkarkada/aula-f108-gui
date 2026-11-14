"""Talking to the keyboard through hidraw.

No libusb needed: the kernel already exposes the vendor interface as a
/dev/hidraw node and feature reports can be sent with two ioctls.
"""

import fcntl
import glob
import os
import time

WIRED_ID = (0x0C45, 0x800A)
DONGLE_ID = (0x05AC, 0x024F)   # the 2.4G receiver pretends to be an Apple keyboard
CONFIG_INTERFACE = 3

COMMAND_DELAY = 0.035

SYSFS_HIDRAW = "/sys/class/hidraw"


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
    """Path of the hidraw node used for configuration.

    Raises NotFound if the keyboard isn't connected with the cable. The
    message says so when only the wireless receiver is plugged in, since
    that's the usual reason.
    """
    dongle = False
    for vendor, product, iface, node in _scan(sysfs):
        if (vendor, product) == WIRED_ID and iface == CONFIG_INTERFACE:
            return "/dev/" + node
        if (vendor, product) == DONGLE_ID:
            dongle = True
    if dongle:
        raise NotFound("Only the 2.4G receiver was found. Settings can only "
                       "be changed over the USB cable: plug it in and switch "
                       "the keyboard to USB mode.")
    raise NotFound("Keyboard not found. Connect it with the USB cable and "
                   "switch it to USB mode.")


class Keyboard:
    def __init__(self, path=None):
        self.path = path or find()
        try:
            self._fd = os.open(self.path, os.O_RDWR)
        except PermissionError:
            raise AccessDenied(f"No permission to open {self.path}. Install "
                               "the udev rule from the udev/ folder and "
                               "replug the keyboard.") from None
        except OSError as e:
            raise KeyboardError(f"Could not open {self.path}: {e}") from None

    def close(self):
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

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
                    self._get()
                    time.sleep(COMMAND_DELAY)
                if progress:
                    progress(i, total)
        except OSError as e:
            raise KeyboardError(f"Lost contact with the keyboard: {e}") from None


def send(steps, progress=None):
    with Keyboard() as kb:
        kb.send(steps, progress)
