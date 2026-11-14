"""Remembers the last settings that were sent.

The keyboard can't report what it's currently set to, so the app keeps its
own copy and shows that on startup.
"""

import copy
import json
import os

DEFAULTS = {
    "lighting": {
        "effect": 11,
        "color": [255, 255, 255],
        "brightness": 5,
        "speed": 3,
        "reverse": False,
        "rainbow": True,
    },
    "per_key": {
        "brightness": 5,
        "brush": [0, 210, 255],
        "colors": {},
    },
    "remap": {},
}


def path():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "aula-f108", "settings.json")


def load():
    data = copy.deepcopy(DEFAULTS)
    try:
        with open(path()) as f:
            saved = json.load(f)
    except (OSError, ValueError):
        return data
    if isinstance(saved, dict):
        for section, values in saved.items():
            if isinstance(values, dict) and isinstance(data.get(section), dict):
                data[section].update(values)
            else:
                data[section] = values
    return data


def save(data):
    target = path()
    os.makedirs(os.path.dirname(target), exist_ok=True)
    tmp = target + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, target)
