import pytest

from aula_f108 import device


def add_hidraw(root, node, vendor, product, iface):
    """Fake just enough of sysfs for one hidraw node."""
    usb_if = root / "devices" / f"usb-{node}" / f"1-1:1.{iface}"
    hid = usb_if / f"0003:{vendor:04X}:{product:04X}.0001"
    hid.mkdir(parents=True)
    (usb_if / "bInterfaceNumber").write_text(f"{iface:02x}\n")
    (hid / "uevent").write_text(
        f"DRIVER=hid-generic\nHID_ID=0003:{vendor:08X}:{product:08X}\n")
    cls = root / "class"
    (cls / node).mkdir(parents=True)
    (cls / node / "device").symlink_to(hid)
    return str(cls)


def test_finds_config_interface(tmp_path):
    for i in range(4):
        sysfs = add_hidraw(tmp_path, f"hidraw{i}", 0x0C45, 0x800A, i)
    add_hidraw(tmp_path, "hidraw9", 0x046D, 0xC336, 0)
    assert device.find(sysfs) == "/dev/hidraw3"


def test_dongle_only(tmp_path):
    sysfs = add_hidraw(tmp_path, "hidraw5", 0x05AC, 0x024F, 3)
    with pytest.raises(device.NotFound, match="receiver"):
        device.find(sysfs)


def test_nothing_connected(tmp_path):
    sysfs = add_hidraw(tmp_path, "hidraw0", 0x046D, 0xC336, 0)
    with pytest.raises(device.NotFound, match="not found"):
        device.find(sysfs)


def test_ioctl_numbers():
    # HIDIOCSFEATURE(65) / HIDIOCGFEATURE(65) from linux/hidraw.h
    assert device._set_feature(65) == 0xC0414806
    assert device._get_feature(65) == 0xC0414807


class FakeKeyboard(device.Keyboard):
    """Keyboard that never touches a device. `replies` are handed out for
    each read back; by default it echoes like the real one."""

    def __init__(self, replies=None):
        self.sent = []
        self.replies = replies

    def _set(self, payload):
        self.sent.append(payload)

    def _get(self):
        if self.replies is None:
            return self.sent[-1][:2] + b"\x00\x01" + bytes(60)
        return self.replies.pop(0)


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(device.time, "sleep", lambda s: None)


def test_send_goes_through_every_packet():
    from aula_f108 import protocol
    steps = protocol.lighting(7)
    kb = FakeKeyboard()
    seen = []
    kb.send(steps, progress=lambda done, total: seen.append((done, total)))
    assert kb.sent == [s.payload for s in steps]
    assert seen == [(i, 5) for i in range(1, 6)]


def test_send_notices_a_keyboard_that_does_not_answer():
    from aula_f108 import protocol
    kb = FakeKeyboard(replies=[bytes(64)] * 10)
    with pytest.raises(device.KeyboardError, match="didn't confirm"):
        kb.send(protocol.lighting(7))
    assert len(kb.sent) == 1    # gave up right away


def test_send_accepts_data_echoes():
    # replies to data packets aren't command echoes and must not trip it
    import datetime
    from aula_f108 import protocol
    FakeKeyboard().send(protocol.clock(datetime.datetime(2026, 1, 1)))
    FakeKeyboard().send(protocol.per_key({1: (255, 0, 0)}))


def test_io_errors_become_keyboard_errors():
    from aula_f108 import protocol

    class Unplugged(FakeKeyboard):
        def _set(self, payload):
            raise OSError(19, "No such device")

    with pytest.raises(device.KeyboardError, match="Lost contact"):
        Unplugged().send(protocol.lighting(1))
