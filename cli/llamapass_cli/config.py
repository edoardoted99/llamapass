import json
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "llamapass"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULTS = {
    "url": "https://llamapass.org",
    "api_key": "",
}


def load():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return {**DEFAULTS, **json.load(f)}
    return dict(DEFAULTS)


def save(cfg):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)


def get(key):
    return load().get(key)


def set_value(key, value):
    cfg = load()
    cfg[key] = value
    save(cfg)
