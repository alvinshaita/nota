"""Export/import of note backups as full-fidelity JSON files, distinct from
the live notes.json store -- a backup is a standalone file the user chooses
a location for for safekeeping or transfer."""
import json
import time
import uuid

FORMAT_VERSION = 1


def build_backup(notes):
    return {
        "app": "nota",
        "version": FORMAT_VERSION,
        "exported_at": time.time(),
        "notes": notes,
    }


def write_backup(path, notes):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(build_backup(notes), f, indent=2)


def read_backup(path):
    """Returns the list of note dicts from a backup file. Raises ValueError
    if the file isn't a recognizable Nota backup."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict) or data.get("app") != "nota" or not isinstance(data.get("notes"), list):
        raise ValueError("Not a valid Nota backup file")
    return data["notes"]


def notes_for_import(notes):
    """Returns copies of the given notes with fresh ids, ready to append to
    the live note list -- importing must never reuse ids from the backup,
    since those could collide with existing notes or a repeat import of the
    same backup."""
    imported = []
    for note in notes:
        copy = dict(note)
        copy["id"] = str(uuid.uuid4())
        copy.pop("deleted_at", None)
        imported.append(copy)
    return imported
