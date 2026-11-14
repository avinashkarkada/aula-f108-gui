from aula_f108 import keys, protocol


def test_unique_keys():
    assert len(keys.KEYS) == 104
    assert len(keys.BY_NAME) == 104
    assert len(keys.BY_INDEX) == 104
    assert len({k.hid for k in keys.KEYS}) == 104


def test_indices_fit_the_table():
    assert all(1 <= k.index <= protocol.MAX_SLOT for k in keys.KEYS)


def test_layout_has_no_overlaps():
    for a in keys.KEYS:
        assert a.x + a.w <= keys.WIDTH and a.y + a.h <= keys.HEIGHT
        for b in keys.KEYS:
            if a is b:
                continue
            apart = (a.x + a.w <= b.x or b.x + b.w <= a.x or
                     a.y + a.h <= b.y or b.y + b.h <= a.y)
            assert apart, (a.name, b.name)


def test_key_at():
    assert keys.key_at(0.5, 0.5).name == "esc"
    assert keys.key_at(5.0, 5.5).name == "space"
    assert keys.key_at(22.0, 3.6).name == "numplus"   # tall key, lower half
    assert keys.key_at(1.5, 0.5) is None              # gap after esc
