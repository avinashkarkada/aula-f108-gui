import json

from aula_f108 import store


def test_defaults_when_nothing_saved(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert store.load() == store.DEFAULTS
    assert store.load() is not store.DEFAULTS


def test_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    data = store.load()
    data["lighting"]["effect"] = 7
    data["per_key"]["colors"] = {"esc": [255, 0, 0]}
    store.save(data)
    assert store.load() == data


def test_old_file_gets_new_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    target = tmp_path / "aula-f108" / "settings.json"
    target.parent.mkdir()
    target.write_text(json.dumps({"lighting": {"effect": 3}}))
    data = store.load()
    assert data["lighting"]["effect"] == 3
    assert data["lighting"]["speed"] == store.DEFAULTS["lighting"]["speed"]
    assert data["per_key"] == store.DEFAULTS["per_key"]


def test_broken_file_is_ignored(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    target = tmp_path / "aula-f108" / "settings.json"
    target.parent.mkdir()
    target.write_text("{not json")
    assert store.load() == store.DEFAULTS
