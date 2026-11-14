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


def test_finds_cable(tmp_path):
    for i in range(4):
        sysfs = add_hidraw(tmp_path, f"hidraw{i}", 0x0C45, 0x800A, i)
    add_hidraw(tmp_path, "hidraw9", 0x046D, 0xC336, 0)
    assert device.find(sysfs) == (device.USB, "/dev/hidraw3")


def test_finds_receiver(tmp_path):
    for i in range(5):
        sysfs = add_hidraw(tmp_path, f"hidraw{i + 4}", 0x05AC, 0x024F, i)
    assert device.find(sysfs) == (device.DONGLE, "/dev/hidraw7")


def test_cable_wins_over_receiver(tmp_path):
    add_hidraw(tmp_path, "hidraw1", 0x05AC, 0x024F, 3)
    sysfs = add_hidraw(tmp_path, "hidraw5", 0x0C45, 0x800A, 3)
    assert device.find(sysfs).kind == device.USB


def test_other_interfaces_are_not_enough(tmp_path):
    # keystroke interface of the receiver only, no config interface
    sysfs = add_hidraw(tmp_path, "hidraw5", 0x05AC, 0x024F, 0)
    with pytest.raises(device.NotFound):
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

    def __init__(self, replies=None, lose_page=None, opens=True):
        self.sent = []
        self.replies = replies
        self._fd = None
        self.pages = []
        self.lose_page = lose_page
        self.opens = opens
        self.closed = 0
        self._acks = []

    def _screen_open(self, sysfs=None):
        if not self.opens:
            raise device.KeyboardError("The keyboard's screen interface is missing.")

    def _screen_close(self):
        self.closed += 1

    def _screen_write(self, page):
        self.pages.append(page)
        if self.lose_page != len(self.pages):
            self._acks.append(b"\x01\x5a\x02\x00" + bytes(60))

    def _screen_ack(self, timeout):
        return self._acks.pop(0) if self._acks else None

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


class FakeDongle(device.Dongle):
    """Receiver that echoes every frame, except that the frames whose
    position (counting every write) is in `lose` get no answer."""

    def __init__(self, lose=(), dead=False, battery=93):
        self._fd = None
        self.written = []
        self.lose = set(lose)
        self.dead = dead
        self.level = battery
        self._pending = []

    def _write(self, frame):
        self.written.append(frame)
        if self.dead or len(self.written) - 1 in self.lose:
            return
        reply = bytearray(32)
        reply[:3] = frame[:3]
        if frame[0] == 0x20:
            reply[3] = self.level
        self._pending.append(bytes(reply))

    def _poll(self, timeout):
        return self._pending.pop(0) if self._pending else None


@pytest.fixture
def quick(monkeypatch):
    monkeypatch.setattr(device, "ECHO_WAIT", 0.001)


def test_dongle_sends_every_frame_once(quick):
    from aula_f108 import wireless
    frames = wireless.per_key({1: (255, 0, 0)})
    kb = FakeDongle()
    seen = []
    kb.send(frames, progress=lambda done, total: seen.append((done, total)))
    assert kb.written == frames
    assert seen[-1] == (22, 22)


def test_dongle_resends_a_lost_frame(quick):
    from aula_f108 import wireless
    frames = wireless.remap({})
    kb = FakeDongle(lose={3, 4})    # fourth frame lost twice
    kb.send(frames)
    assert len(kb.written) == len(frames) + 2
    assert kb.written[3] == kb.written[4] == kb.written[5] == frames[3]
    # everything still arrives in order
    order = [f for i, f in enumerate(kb.written) if i not in (3, 4)]
    assert order == frames


def test_dongle_gives_up_when_nothing_answers(quick):
    from aula_f108 import wireless
    kb = FakeDongle(dead=True)
    with pytest.raises(device.KeyboardError, match="No answer"):
        kb.send(wireless.lighting(1))
    assert len(kb.written) == device.RESENDS + 1


def test_dongle_ignores_stale_replies(quick):
    from aula_f108 import wireless
    kb = FakeDongle()
    kb._pending.append(bytes(32))   # left over from something earlier
    kb.send(wireless.lighting(1))
    assert len(kb.written) == 1


def test_dongle_battery(quick):
    assert FakeDongle(battery=93).battery() == 93
    assert FakeDongle(battery=0).battery() is None
    assert FakeDongle(battery=120).battery() == 100


def test_cable_has_no_battery_reading():
    assert FakeKeyboard().battery() is None


def test_both_kinds_offer_the_same_actions(quick):
    import datetime
    for kb in (FakeKeyboard(), FakeDongle()):
        kb.lighting(7, (255, 0, 0), 4, 2)
        kb.per_key({1: (1, 2, 3)}, 3)
        kb.remap({55: bytes.fromhex("02010000")})
        kb.clock(datetime.datetime(2026, 1, 1))


def picture(frames=1):
    from aula_f108 import lcd
    Image = pytest.importorskip("PIL.Image")
    frame = Image.new("RGB", (lcd.WIDTH, lcd.HEIGHT), (255, 0, 0))
    return lcd.build([frame] * frames)


def test_picture_upload():
    data = picture(2)
    kb = FakeKeyboard()
    seen = []
    kb.show_image(data, progress=lambda done, total: seen.append((done, total)))
    assert [p[:2].hex() for p in kb.sent] == ["0418", "0472", "0402"]
    header = kb.sent[1]
    assert header[2] == 1 and header[8] | header[9] << 8 == 32
    assert b"".join(kb.pages) == data
    assert seen[0] == (1, 32) and seen[-1] == (32, 32)
    assert kb.closed == 1


def test_picture_upload_stops_when_the_start_is_not_accepted():
    # echoes the command but without the "ok" byte
    kb = FakeKeyboard(replies=[bytes.fromhex("04180000") + bytes(60)])
    with pytest.raises(device.KeyboardError, match="didn't accept"):
        kb.show_image(picture())
    assert kb.pages == []
    assert kb.closed == 1


def test_picture_upload_stops_at_a_page_without_an_answer(monkeypatch):
    monkeypatch.setattr(device, "PAGE_ACK_WAIT", 0)
    kb = FakeKeyboard(lose_page=3)
    with pytest.raises(device.KeyboardError, match="page 3 of 16"):
        kb.show_image(picture())
    assert len(kb.pages) == 3
    assert [p[:2].hex() for p in kb.sent] == ["0418", "0472"]     # no apply
    assert kb.closed == 1


def test_picture_upload_checks_the_buffer_first():
    from aula_f108 import lcd
    kb = FakeKeyboard()
    with pytest.raises(ValueError):
        kb.show_image(picture()[:-1])
    too_many = bytearray(picture())
    too_many[0] = 200
    with pytest.raises(lcd.TooManyFrames):
        kb.show_image(bytes(too_many))
    assert kb.sent == [] and kb.pages == []


def test_picture_upload_needs_the_screen_interface():
    kb = FakeKeyboard(opens=False)
    with pytest.raises(device.KeyboardError, match="screen interface"):
        kb.show_image(picture())
    assert kb.sent == [] and kb.pages == []


def test_no_pictures_through_the_receiver(quick):
    kb = FakeDongle()
    with pytest.raises(device.KeyboardError, match="USB cable"):
        kb.show_image(picture())
    assert kb.written == []


def test_screen_interface_needs_an_interrupt_out_endpoint(tmp_path):
    sysfs = add_hidraw(tmp_path, "hidraw2", 0x0C45, 0x800A, 2)
    kb = FakeKeyboard()
    opener = device.Keyboard._screen_open.__get__(kb)
    with pytest.raises(device.KeyboardError, match="looks different"):
        opener(sysfs)
    # an IN endpoint alone isn't enough either
    usb_if = tmp_path / "devices" / "usb-hidraw2" / "1-1:1.2"
    (usb_if / "ep_84").mkdir()
    (usb_if / "ep_84" / "type").write_text("Interrupt\n")
    (usb_if / "ep_84" / "direction").write_text("in\n")
    with pytest.raises(device.KeyboardError, match="looks different"):
        opener(sysfs)
