import pytest

from aula_f108 import keys, protocol, remap


@pytest.mark.parametrize("binding, expected", [
    ("a", "02000400"),
    ("lctrl", "02010000"),
    ("rshift", "02200000"),
    ("ctrl+c", "02010600"),
    ("alt+tab", "02042b00"),
    ("super+d", "02080700"),
    ("ctrl+shift+esc", "02032900"),
    ("ctrl+lalt", "02050000"),
    ("media:play", "03cd0000"),
    ("media:voldown", "03ea0000"),
    ("mouse:lclick", "07010000"),
    ("mouse:scrolldown", "0700ff00"),
    (" Ctrl+C ", "02010600"),
])
def test_slot(binding, expected):
    assert remap.slot(binding).hex() == expected


@pytest.mark.parametrize("binding", [
    "", "nokey", "hyper+a", "media:rewind", "mouse:", "sound:mute", "fn",
    "ctrl+fn",
])
def test_slot_rejects(binding):
    with pytest.raises(ValueError):
        remap.slot(binding)


def test_describe():
    assert remap.describe("lctrl") == "Left Ctrl"
    assert remap.describe("ctrl+shift+c") == "Ctrl + Shift + C"
    assert remap.describe("media:mute") == "Mute"
    assert remap.describe("mouse:rclick") == "Right click"


def test_every_key_has_a_title():
    titles = [remap.title(k) for k in keys.KEYS]
    assert all(titles)
    assert len(set(titles)) == len(titles)


def test_table():
    slots = remap.table({"capslock": "lctrl", "f1": "media:play"})
    assert slots == {55: bytes.fromhex("02010000"), 2: bytes.fromhex("03cd0000")}


def test_table_refuses_fn_and_unknown_keys():
    with pytest.raises(ValueError):
        remap.table({"fn": "a"})
    with pytest.raises(ValueError):
        remap.table({"nokey": "a"})


def test_remap_packets():
    steps = protocol.remap(remap.table({"capslock": "lctrl"}))
    assert [s.payload[:2].hex() for s in steps[:2]] == ["0418", "0411"]
    assert steps[1].payload[8] == 9
    chunks = steps[2:-2]
    assert len(chunks) == 9 and not any(s.readback for s in chunks)
    table = b"".join(s.payload for s in chunks)
    assert table[220:224] == bytes.fromhex("02010000")
    assert table[-2:] == b"\xaa\x55"
    assert sum(1 for b in table[:-2] if b) == 2
    assert [s.payload[:2].hex() for s in steps[-2:]] == ["0402", "04f0"]
    assert steps[-1].readback


def test_empty_remap_clears_the_table():
    table = b"".join(s.payload for s in protocol.remap({})[2:-2])
    assert not any(table[:-2])
