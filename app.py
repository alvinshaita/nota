"""The Nota application: owns all open note windows."""
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib

import storage
from note_window import NoteWindow

APP_ID = "com.github.nota"


class NotaApplication(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.notes = []
        self.windows = {}

        new_action = Gio.SimpleAction.new("new-note", None)
        new_action.connect("activate", lambda *_: self.create_note())
        self.add_action(new_action)
        self.set_accels_for_action("app.new-note", ["<Primary>n"])

        self.connect("shutdown", self._on_shutdown)

    def do_activate(self):
        if not self.windows:
            self.notes = storage.load_notes()
            if not self.notes:
                self.notes = [storage.new_note(text="Welcome to Nota! Type here.")]
            for note in self.notes:
                self._open_window(note)

    def create_note(self):
        note = storage.new_note()
        self.notes.append(note)
        self._open_window(note)
        self.save_all()

    def _open_window(self, note):
        window = NoteWindow(self, note, on_delete=self.delete_note)
        self.windows[note["id"]] = window
        window.present()

    def delete_note(self, note_id):
        self.notes = [n for n in self.notes if n["id"] != note_id]
        self.windows.pop(note_id, None)
        self.save_all()

    def save_all(self):
        storage.save_notes(self.notes)

    def _on_shutdown(self, *_args):
        for window in self.windows.values():
            window.sync_state()
        self.save_all()
