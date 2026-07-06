"""Persistence for notes: one JSON file listing all notes and their state."""
import json
import time
import uuid
from pathlib import Path

DATA_DIR = Path.home() / ".local" / "share" / "nota"
DATA_FILE = DATA_DIR / "notes.json"

DEFAULT_COLOR = "#f9e08a"

TRASH_RETENTION_DAYS = 7


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
        "title": "",
        "text": text,
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "color": color,
        "group": group,
        "formatting": {},
    }


def note_title(note):
    title = note.get("title", "").strip()
    if title:
        return title[:40]
    first_line = next((line.strip() for line in note.get("text", "").splitlines() if line.strip()), "")
    if not first_line:
        return "Untitled note"
    return first_line[:40]


def active_notes(notes):
    return [n for n in notes if not n.get("deleted_at")]


def deleted_notes(notes):
    return [n for n in notes if n.get("deleted_at")]


def purge_expired(notes, days=TRASH_RETENTION_DAYS):
    """Drops notes soft-deleted more than `days` ago. Returns a new list --
    doesn't mutate the input."""
    cutoff = time.time() - days * 24 * 3600
    return [n for n in notes if not n.get("deleted_at") or n["deleted_at"] >= cutoff]


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
