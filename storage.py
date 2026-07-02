"""Persistence for notes: one JSON file listing all notes and their state."""
import json
import uuid
from pathlib import Path

DATA_DIR = Path.home() / ".local" / "share" / "nota"
DATA_FILE = DATA_DIR / "notes.json"

DEFAULT_COLOR = "#f9e08a"


def _ensure_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_notes():
    _ensure_dir()
    if not DATA_FILE.exists():
        return []
    with DATA_FILE.open("r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def save_notes(notes):
    _ensure_dir()
    tmp = DATA_FILE.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(notes, f, indent=2)
    tmp.replace(DATA_FILE)


def new_note(x=100, y=100, width=260, height=260, color=DEFAULT_COLOR, text=""):
    return {
        "id": str(uuid.uuid4()),
        "text": text,
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "color": color,
    }
