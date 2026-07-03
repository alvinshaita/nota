"""Persistence for app preferences (distinct from note data)."""
import json
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "nota"
CONFIG_FILE = CONFIG_DIR / "settings.json"

LEFT_CLICK_ACTIONS = ["toggle", "new_note", "nothing"]
DEFAULT_SETTINGS = {"left_click_action": "toggle"}


def load_settings():
    if not CONFIG_FILE.exists():
        return dict(DEFAULT_SETTINGS)
    with CONFIG_FILE.open("r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            return dict(DEFAULT_SETTINGS)
    merged = dict(DEFAULT_SETTINGS)
    merged.update(data)
    return merged


def save_settings(settings):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG_FILE.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)
    tmp.replace(CONFIG_FILE)
