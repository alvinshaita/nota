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


def new_note(x=100, y=100, width=260, height=260, color=DEFAULT_COLOR, text="", group=None):
    return {
        "id": str(uuid.uuid4()),
        "text": text,
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "color": color,
        "group": group,
    }


def note_title(note):
    first_line = next((line.strip() for line in note.get("text", "").splitlines() if line.strip()), "")
    if not first_line:
        return "Untitled note"
    return first_line[:40]


def groups_and_notes(notes):
    """Returns (groups_dict, ungrouped_list). groups_dict maps group name
    to its list of notes, sorted by group name."""
    groups = {}
    ungrouped = []
    for note in notes:
        group = note.get("group")
        if group:
            groups.setdefault(group, []).append(note)
        else:
            ungrouped.append(note)
    return dict(sorted(groups.items())), ungrouped
