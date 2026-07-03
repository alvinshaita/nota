"""The Nota application: owns all open note windows and the tray IPC service."""
import subprocess
import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib

import dbus_common
import settings as settings_module
import storage
from note_window import NoteWindow
from settings_window import SettingsWindow

APP_ID = dbus_common.BUS_NAME


class NotaApplication(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.notes = []
        self.windows = {}
        self.notes_visible = True
        self.settings_window = None
        self._tray_process = None
        self._dbus_reg_id = None

        new_action = Gio.SimpleAction.new("new-note", None)
        new_action.connect("activate", lambda *_: self.create_note())
        self.add_action(new_action)
        self.set_accels_for_action("app.new-note", ["<Primary>n"])

        self.connect("shutdown", self._on_shutdown)

    def do_startup(self):
        Adw.Application.do_startup(self)
        self._launch_tray()

    def do_activate(self):
        if not self.windows:
            self.notes = storage.load_notes()
            if not self.notes:
                self.notes = [storage.new_note(text="Welcome to Nota! Type here.")]
            for note in self.notes:
                self._open_window(note)

    def do_dbus_register(self, connection, object_path):
        if not Adw.Application.do_dbus_register(self, connection, object_path):
            return False
        node_info = Gio.DBusNodeInfo.new_for_xml(dbus_common.INTROSPECTION_XML)
        self._dbus_reg_id = connection.register_object(
            object_path, node_info.interfaces[0], self._on_dbus_method_call
        )
        return True

    def do_dbus_unregister(self, connection, object_path):
        if self._dbus_reg_id is not None:
            connection.unregister_object(self._dbus_reg_id)
            self._dbus_reg_id = None
        Adw.Application.do_dbus_unregister(self, connection, object_path)

    def _on_dbus_method_call(self, _connection, _sender, _object_path,
                              _interface_name, method_name, _parameters, invocation):
        if method_name == "LeftClickActivate":
            self.handle_left_click()
        elif method_name == "NewNote":
            self.create_note()
        elif method_name == "ShowSettings":
            self.show_settings()
        elif method_name == "Quit":
            self.quit()
        invocation.return_value(None)

    def _launch_tray(self):
        tray_path = Path(__file__).resolve().parent / "tray.py"
        self._tray_process = subprocess.Popen([sys.executable, str(tray_path)])

    def handle_left_click(self):
        action = settings_module.load_settings().get("left_click_action", "toggle")
        if action == "toggle":
            self.toggle_visibility()
        elif action == "new_note":
            self.create_note()

    def toggle_visibility(self):
        self.notes_visible = not self.notes_visible
        for window in self.windows.values():
            if self.notes_visible:
                window.present_at_position()
            else:
                window.sync_state()
                window.set_visible(False)
        if not self.notes_visible:
            self.save_all()

    def show_settings(self):
        if self.settings_window is None:
            self.settings_window = SettingsWindow(self)
            self.settings_window.connect("close-request", self._on_settings_closed)
        self.settings_window.present()

    def _on_settings_closed(self, *_args):
        self.settings_window = None
        return False

    def create_note(self):
        note = storage.new_note()
        self.notes.append(note)
        self._open_window(note)
        self.notes_visible = True
        self.save_all()

    def _open_window(self, note):
        window = NoteWindow(self, note, on_delete=self.delete_note)
        self.windows[note["id"]] = window
        window.present_at_position()

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
        if self._tray_process is not None:
            self._tray_process.terminate()
