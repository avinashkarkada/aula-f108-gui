import pytest

from aula_f108 import lcd

Image = pytest.importorskip("PIL.Image")


def solid(color, size=(lcd.WIDTH, lcd.HEIGHT)):
    return Image.new("RGB", size, color)


def test_limit_is_inside_the_slot():
    assert lcd.MAX_FRAMES == 130
    assert lcd.MAX_FRAMES < lcd.SLOT_FRAMES == 141


@pytest.mark.parametrize("color, expected", [
    ((255, 0, 0), b"\x00\xf8"),
    ((0, 255, 0), b"\xe0\x07"),
    ((0, 0, 255), b"\x1f\x00"),
    ((255, 255, 255), b"\xff\xff"),
    ((0, 0, 0), b"\x00\x00"),
    ((8, 4, 8), b"\x21\x08"),
])
def test_rgb565(color, expected):
    raw = lcd.rgb565(solid(color))
    assert len(raw) == lcd.FRAME_SIZE
    assert raw == expected * (lcd.WIDTH * lcd.HEIGHT)


def test_rgb565_pixel_order():
    image = solid((0, 0, 0))
    image.putpixel((1, 0), (255, 0, 0))
    image.putpixel((0, 1), (0, 0, 255))
    raw = lcd.rgb565(image)
    assert raw[2:4] == b"\x00\xf8"
    assert raw[lcd.WIDTH * 2:lcd.WIDTH * 2 + 2] == b"\x1f\x00"


def test_rgb565_wants_the_right_size():
    with pytest.raises(ValueError):
        lcd.rgb565(solid((0, 0, 0), (100, 100)))


@pytest.mark.parametrize("size", [(240, 135), (1920, 1080), (500, 500),
                                  (100, 400), (64, 36), (3, 2)])
def test_fit_always_fills_the_screen(size):
    assert lcd.fit(solid((1, 2, 3), size)).size == (lcd.WIDTH, lcd.HEIGHT)


def test_single_frame_buffer():
    data = lcd.build([solid((255, 0, 0))], [100])
    assert len(data) == 16 * lcd.PAGE_SIZE
    assert data[0] == 1 and data[1] == 50
    assert set(data[2:lcd.HEADER_SIZE]) == {0xFF}
    assert data[lcd.HEADER_SIZE:lcd.HEADER_SIZE + 2] == b"\x00\xf8"
    end = lcd.HEADER_SIZE + lcd.FRAME_SIZE
    assert data[end - 2:end] == b"\x00\xf8"
    assert set(data[end:]) == {0xFF}
    assert lcd.check(data) == 16


def test_delays_are_in_2ms_steps_and_clamped():
    data = lcd.build([solid((0, 0, 0))] * 5, [80, 500, 510, 5000, 0])
    assert list(data[1:6]) == [40, 250, 255, 255, 1]


def test_frames_follow_each_other():
    data = lcd.build([solid((255, 0, 0)), solid((0, 0, 255))], [40, 40])
    second = lcd.HEADER_SIZE + lcd.FRAME_SIZE
    assert data[second - 2:second] == b"\x00\xf8"
    assert data[second:second + 2] == b"\x1f\x00"
    assert lcd.check(data) == 32


def test_the_limit_itself_is_allowed():
    frame = solid((0, 0, 0))
    data = lcd.build([frame] * lcd.MAX_FRAMES)
    assert data[0] == 130
    assert len(data) < lcd.HEADER_SIZE + lcd.FRAME_SIZE * lcd.SLOT_FRAMES


def test_one_frame_over_the_limit_is_refused():
    frame = solid((0, 0, 0))
    with pytest.raises(lcd.TooManyFrames):
        lcd.build([frame] * (lcd.MAX_FRAMES + 1))


def test_no_frames_is_refused():
    with pytest.raises(ValueError):
        lcd.build([])


def test_check_refuses_a_buffer_that_claims_too_many_frames():
    # built by hand, the way a bug elsewhere might
    count = 141
    size = lcd.HEADER_SIZE + lcd.FRAME_SIZE * count
    size = -(-size // lcd.PAGE_SIZE) * lcd.PAGE_SIZE
    data = bytearray(b"\xFF" * size)
    data[0] = count
    data[1:1 + count] = bytes([20] * count)
    with pytest.raises(lcd.TooManyFrames):
        lcd.check(bytes(data))


def test_check_refuses_a_size_that_does_not_match():
    good = lcd.build([solid((0, 0, 0))])
    with pytest.raises(ValueError):
        lcd.check(good + bytes([0xFF] * lcd.PAGE_SIZE))     # longer than it says
    with pytest.raises(ValueError):
        lcd.check(good[:-1])
    with pytest.raises(ValueError):
        lcd.check(b"")
    two = bytearray(good)
    two[0] = 2                                              # says more than it has
    with pytest.raises(ValueError):
        lcd.check(bytes(two))


def test_thin_keeps_short_animations_as_they_are():
    frames, delays = lcd.thin(list("abc"), [10, 20, 30])
    assert frames == list("abc") and delays == [10, 20, 30]


def test_thin_cuts_down_and_keeps_the_running_time():
    frames = list(range(214))
    kept, delays = lcd.thin(frames, [40] * 214)
    assert len(kept) == len(delays) == lcd.MAX_FRAMES
    assert kept[0] == 0 and kept == sorted(kept)
    assert sum(delays) == 214 * 40


def test_load_animation(tmp_path):
    path = tmp_path / "a.gif"
    frames = [solid(c, (120, 120)) for c in ((255, 0, 0), (0, 255, 0), (0, 0, 255))]
    frames[0].save(path, save_all=True, append_images=frames[1:],
                   duration=[40, 80, 120], loop=0)
    loaded, delays, original = lcd.load(path)
    assert original == 3 and delays == [40, 80, 120]
    assert all(f.size == (lcd.WIDTH, lcd.HEIGHT) for f in loaded)
    assert lcd.build(loaded, delays)[0] == 3


def test_load_still_picture(tmp_path):
    path = tmp_path / "a.png"
    solid((10, 20, 30), (800, 600)).save(path)
    loaded, delays, original = lcd.load(path)
    assert original == 1 and len(loaded) == 1
    assert lcd.check(lcd.build(loaded, delays)) == 16


def test_load_long_animation_is_cut_to_the_limit(tmp_path):
    path = tmp_path / "long.gif"
    frames = [solid((i, 255 - i, i // 2), (48, 27)) for i in range(150)]
    frames[0].save(path, save_all=True, append_images=frames[1:],
                   duration=40, loop=0)
    loaded, delays, original = lcd.load(path)
    assert original == 150
    assert len(loaded) == lcd.MAX_FRAMES
    assert sum(delays) == 150 * 40
    assert lcd.build(loaded, delays)[0] == lcd.MAX_FRAMES
