import datetime

import pytest

from aula_f108 import protocol


def heads(steps):
    return [s.payload[:2].hex() for s in steps]


def test_packets_are_64_bytes():
    for steps in (protocol.lighting(7), protocol.per_key({1: (1, 2, 3)}),
                  protocol.clock(datetime.datetime(2026, 1, 1))):
        assert all(len(s.payload) == 64 for s in steps)


def test_lighting_sequence():
    steps = protocol.lighting(7, (255, 0, 128), brightness=4, speed=2)
    assert heads(steps) == ["0418", "0413", "07ff", "0402", "04f0"]
    assert [s.readback for s in steps] == [True, True, False, True, False]
    assert steps[1].payload[8] == 1

    data = steps[2].payload
    assert data[:4] == bytes([7, 255, 0, 128])
    assert data[8:12] == bytes([0, 4, 2, 0])
    assert data[14:16] == b"\x55\xaa"
    assert not any(data[16:])


def test_lighting_rainbow_and_direction():
    data = protocol.lighting(10, direction=1, rainbow=True)[2].payload
    assert data[8] == 1
    assert data[11] == 1


def test_lighting_off_carries_no_settings():
    data = protocol.lighting(0, (9, 9, 9), brightness=5, speed=5)[2].payload
    assert not any(data[:14])
    assert data[14:16] == b"\x55\xaa"


@pytest.mark.parametrize("kwargs", [
    {"effect": 20}, {"effect": -1},
    {"effect": 1, "brightness": 6}, {"effect": 1, "speed": -1},
])
def test_lighting_rejects_out_of_range(kwargs):
    with pytest.raises(ValueError):
        protocol.lighting(**kwargs)


def test_per_key_table():
    steps = protocol.per_key({1: (255, 0, 0), 123: (0, 0, 255)}, brightness=3)

    # custom mode first, then the colour table
    assert steps[2].payload[0] == protocol.CUSTOM_MODE
    assert steps[2].payload[9] == 3
    assert heads(steps[:5]) == ["0418", "0413", "8000", "0402", "04f0"]
    assert heads(steps[5:7]) == ["0418", "0423"]
    assert steps[6].payload[8] == 9

    chunks = steps[7:-2]
    assert len(chunks) == 9
    assert [s.readback for s in chunks] == [False] * 8 + [True]
    table = b"".join(s.payload for s in chunks)
    assert len(table) == 576
    assert table[4:8] == bytes([1, 255, 0, 0])
    assert table[492:496] == bytes([123, 0, 0, 255])
    assert table[-2:] == b"\x55\xaa"
    # nothing else is lit
    assert sum(1 for b in table[:-2] if b) == 4

    assert heads(steps[-2:]) == ["0402", "04f0"]
    assert steps[-1].readback


def test_per_key_rejects_bad_index():
    for index in (0, 143, 200):
        with pytest.raises(ValueError):
            protocol.per_key({index: (1, 1, 1)})


def test_clock():
    # 2026-11-14 is a saturday
    steps = protocol.clock(datetime.datetime(2026, 11, 14, 16, 5, 9))
    assert heads(steps) == ["0418", "0428", "0001", "0402"]
    assert all(s.readback for s in steps)
    data = steps[2].payload
    assert data[:11] == bytes([0, 1, 0x5A, 26, 11, 14, 16, 5, 9, 0, 6])
    assert data[62:] == b"\x55\xaa"


def test_clock_sunday_is_zero():
    data = protocol.clock(datetime.datetime(2026, 11, 15))[2].payload
    assert data[10] == 0
