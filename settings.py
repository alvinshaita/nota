"""Persistence for app preferences (distinct from note data)."""
import json
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "nota"
CONFIG_FILE = CONFIG_DIR / "settings.json"

LEFT_CLICK_ACTIONS = ["toggle", "new_note", "nothing"]

# key -> CSS font-family value (None = don't override, use the app's default)
FONT_CHOICES = {
    "system": None,
    "virgil": "Virgil",
}
FONT_LABELS = {
    "system": "System Default",
    "virgil": "Virgil",
}

# List of note ids that were open last time visibility was deliberately
# changed (via a tray menu action or a note's own close button). None means
# "no preference recorded yet" -- defaults to showing every note.
DEFAULT_SETTINGS = {
    "left_click_action": "toggle",
    "font_family": "system",
    "open_note_ids": None,
}


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
