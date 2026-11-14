import datetime

import pytest

from aula_f108 import wireless


def test_frame_layout():
    f = wireless.frame(0x14, b"\x01\x02\x03", index=7)
    assert len(f) == 32
    assert f[:6] == bytes([0x14, 3, 7, 1, 2, 3])
    assert not any(f[6:31])
    assert f[31] == (0x14 + 3 + 7 + 1 + 2 + 3) & 0xFF


def test_frame_checksum_wraps():
    f = wireless.frame(0xFF, bytes([0xFF] * 28), index=0xFF)
    assert f[31] == sum(f[:31]) & 0xFF


def test_frame_refuses_too_much_data():
    with pytest.raises(ValueError):
        wireless.frame(0x14, bytes(29))


# The next three are frames that were sent to a real keyboard and did what
# they should.

def test_lighting_matches_a_frame_that_worked():
    (f,) = wireless.lighting(1, (0, 255, 0), brightness=5, speed=3)
    assert f.hex() == ("05100001" "00ff0000" "00000000" "05030000"
                       "00aa5500" "00000000" "00000000" "0000001c")


def test_clock_matches_a_frame_that_worked():
    (f,) = wireless.clock(datetime.datetime(2026, 11, 14, 3, 33, 0))
    assert f.hex() == ("0c100000" "015a1a0b" "0e032100" "00060000"
                       "00aa5500" "00000000" "00000000" "000000d3")


def test_battery_query_matches_a_frame_that_worked():
    assert wireless.battery_query().hex() == "200100" + "00" * 28 + "21"


def test_battery_level():
    reply = bytes.fromhex("2001005e") + bytes(28)
    assert wireless.battery_level(reply) == 0x5E
    assert wireless.battery_level(bytes.fromhex("20010000") + bytes(28)) is None


def test_lighting_off_is_all_zero():
    (f,) = wireless.lighting(0, (9, 9, 9), brightness=5, speed=5)
    assert f[:3] == bytes([0x05, 0x10, 0])
    assert not any(f[3:17])
    assert f[17:19] == b"\xaa\x55"


def test_lighting_options():
    (f,) = wireless.lighting(10, (1, 2, 3), 4, 2, direction=1, rainbow=True)
    data = f[3:19]
    assert data[0] == 10 and data[1:4] == bytes([1, 2, 3])
    assert data[8:12] == bytes([1, 4, 2, 1])


@pytest.mark.parametrize("kwargs", [
    {"effect": 20}, {"effect": 1, "brightness": 6}, {"effect": 1, "speed": -1},
])
def test_lighting_rejects_out_of_range(kwargs):
    with pytest.raises(ValueError):
        wireless.lighting(**kwargs)


def reassemble(frames, command):
    table = b""
    for number, f in enumerate(frames):
        assert f[0] == command and f[2] == number
        assert f[31] == sum(f[:31]) & 0xFF
        table += f[3:3 + f[1]]
    return table


def test_per_key():
    frames = wireless.per_key({1: (255, 0, 0), 123: (0, 0, 255)}, brightness=3)
    mode, chunks = frames[0], frames[1:]

    # custom mode first, with the brightness
    assert mode[:4] == bytes([0x05, 0x10, 0, 0x80])
    assert mode[12] == 3

    assert len(chunks) == 21
    assert [f[1] for f in chunks] == [28] * 20 + [16]
    table = reassemble(chunks, 0x14)
    assert len(table) == 576
    assert table[4:8] == bytes([1, 255, 0, 0])
    assert table[492:496] == bytes([123, 0, 0, 255])
    assert table[-2:] == b"\xaa\x55"
    assert sum(1 for b in table[:-2] if b) == 4


def test_remap():
    frames = wireless.remap({55: bytes.fromhex("02010000")})
    assert len(frames) == 21
    table = reassemble(frames, 0x10)
    assert table[220:224] == bytes.fromhex("02010000")
    assert table[-2:] == b"\xaa\x55"
    assert sum(1 for b in table[:-2] if b) == 2


def test_empty_remap_clears_the_table():
    assert not any(reassemble(wireless.remap({}), 0x10)[:-2])


def test_bad_indices_are_refused():
    with pytest.raises(ValueError):
        wireless.per_key({0: (1, 1, 1)})
    with pytest.raises(ValueError):
        wireless.remap({200: bytes(4)})
