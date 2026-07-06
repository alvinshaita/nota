"""The Nota application: owns all open note windows and the tray IPC service."""
import subprocess
import sys
import time
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib

import dbus_common
import fonts_util
import settings as settings_module
import storage
import x11_utils
from note_manager_window import NoteManagerWindow
from note_window import NoteWindow
from settings_window import SettingsWindow

STACKING_SAVE_DELAY_MS = 800
TRASH_PURGE_CHECK_INTERVAL_SECONDS = 3600

APP_ID = dbus_common.BUS_NAME

NEW_NOTE_BASE_X = 100
NEW_NOTE_BASE_Y = 100
NEW_NOTE_CASCADE_STEP = 30
NEW_NOTE_CASCADE_STEPS = 10


class NotaApplication(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.notes = []
        self.windows = {}
        self.notes_visible = True
        self.settings_window = None
        self.note_manager_window = None
        self._tray_process = None
        self._dbus_reg_id = None
        self._stacking_save_source_id = None
        self._cascade_index = 0

        new_action = Gio.SimpleAction.new("new-note", None)
        new_action.connect("activate", lambda *_: self.create_note())
        self.add_action(new_action)
        self.set_accels_for_action("app.new-note", ["<Primary>n"])

        self.connect("shutdown", self._on_shutdown)

    def do_startup(self):
        Adw.Application.do_startup(self)
        fonts_util.ensure_installed()
        self._launch_tray()
        x11_utils.watch_stacking_order(self._on_stacking_changed)
        GLib.timeout_add_seconds(TRASH_PURGE_CHECK_INTERVAL_SECONDS, self._periodic_purge)

    def do_activate(self):
        if not self.windows:
            self.notes = storage.load_notes()
            if not self.notes:
                self.notes = [storage.new_note(text="Welcome to Nota! Type here.")]
            purged = storage.purge_expired(self.notes)
            if len(purged) != len(self.notes):
                self.notes = purged
                self.save_all()
            active = storage.active_notes(self.notes)
            saved = settings_module.load_settings().get("open_note_ids")
            target = set(saved) if saved is not None else {n["id"] for n in active}
            for note in active:
                self._open_window(note, visible=note["id"] in target)

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
                              _interface_name, method_name, parameters, invocation):
        if method_name == "LeftClickActivate":
            self.handle_left_click()
        elif method_name == "NewNote":
            self.create_note()
        elif method_name == "ShowSettings":
            self.show_settings()
        elif method_name == "ShowNoteManager":
            self.show_note_manager()
        elif method_name == "Quit":
            self.quit()
        elif method_name == "OpenAllNotes":
            self.open_all_notes()
        elif method_name == "CloseAllNotes":
            self.close_all_notes()
        elif method_name == "OpenGroup":
            (group,) = parameters.unpack()
            self.open_group_add(group)
        elif method_name == "OpenGroupOnly":
            (group,) = parameters.unpack()
            self.open_group_only(group)
        elif method_name == "OpenNote":
            (note_id,) = parameters.unpack()
            self.open_note(note_id)
        elif method_name == "ToggleNote":
            (note_id,) = parameters.unpack()
            self.toggle_note(note_id)
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
        if self.notes_visible:
            saved = settings_module.load_settings().get("open_note_ids")
            target = saved if saved is not None else [n["id"] for n in self.notes]
            self._apply_visible_set(target)
        else:
            for window in self.windows.values():
                window.sync_state()
                window.set_visible(False)
            self.save_all()

    def _currently_visible_ids(self):
        return [
            n["id"] for n in self.notes
            if self.windows.get(n["id"]) is not None and self.windows[n["id"]].get_visible()
        ]

    def get_open_note_ids(self):
        return set(self._currently_visible_ids())

    def _persist_open_ids(self, ids):
        valid_ids = {n["id"] for n in self.notes}
        current = settings_module.load_settings()
        current["open_note_ids"] = [i for i in ids if i in valid_ids]
        settings_module.save_settings(current)

    def sync_open_ids(self):
        """Recompute and persist the open set from actual current visibility.
        Call after any visibility change that doesn't already go through
        _apply_visible_set (e.g. a note's own close button)."""
        self._persist_open_ids(self._currently_visible_ids())

    def _apply_visible_set(self, target_ids):
        target_set = set(target_ids)
        for note in self.notes:
            window = self.windows.get(note["id"])
            if window is None:
                continue
            was_visible = window.get_visible()
            if note["id"] in target_set:
                if not was_visible:
                    window.present_at_position()
            elif was_visible:
                window.sync_state()
                window.set_visible(False)
        self.notes_visible = True
        self._persist_open_ids(target_set)
        self.save_all()
        if self.note_manager_window is not None:
            self.note_manager_window._refresh()
            # Newly-shown note windows map asynchronously (round-trip through
            # the WM) and can land on top of the stack after this point --
            # _on_stacking_changed re-raises the manager once that settles.
            self.note_manager_window.present()

    def open_all_notes(self):
        self._apply_visible_set({n["id"] for n in self.notes})

    def close_all_notes(self):
        for window in self.windows.values():
            window.sync_state()
            window.set_visible(False)
        self.notes_visible = False
        self.save_all()

    def open_group_only(self, group):
        ids = {n["id"] for n in self.notes if n.get("group") == group}
        self._apply_visible_set(ids)

    def open_group_add(self, group):
        current = set(self._currently_visible_ids())
        ids = {n["id"] for n in self.notes if n.get("group") == group}
        self._apply_visible_set(current | ids)

    def open_note(self, note_id):
        current = set(self._currently_visible_ids())
        self._apply_visible_set(current | {note_id})

    def toggle_note(self, note_id):
        window = self.windows.get(note_id)
        if window is None:
            return
        current = set(self._currently_visible_ids())
        if note_id in current:
            current.discard(note_id)
        else:
            current.add(note_id)
        self._apply_visible_set(current)

    def get_all_groups(self):
        return sorted({n["group"] for n in storage.active_notes(self.notes) if n.get("group")})

    def _periodic_purge(self):
        purged = storage.purge_expired(self.notes)
        if len(purged) != len(self.notes):
            self.notes = purged
            self.save_all()
            if self.note_manager_window is not None:
                self.note_manager_window._refresh()
        return GLib.SOURCE_CONTINUE

    def apply_font_setting(self):
        key = settings_module.load_settings().get("font_family", "system")
        family = settings_module.FONT_CHOICES.get(key)
        for window in self.windows.values():
            window.apply_font(family)

    def apply_line_spacing_setting(self):
        current = settings_module.load_settings()
        pixels_above = current.get("pixels_above_lines", 0)
        pixels_inside_wrap = current.get("pixels_inside_wrap", 0)
        line_height = current.get("line_height", 1.0)
        for window in self.windows.values():
            window.apply_line_spacing(pixels_above, pixels_inside_wrap, line_height)

    def apply_font_size_setting(self):
        size = settings_module.load_settings().get("font_size", 0)
        for window in self.windows.values():
            window.apply_font_size(size)

    def apply_auto_bullet_setting(self):
        enabled = settings_module.load_settings().get("auto_bullet_lists", True)
        for window in self.windows.values():
            window.apply_auto_bullet_lists(enabled)

    def _on_stacking_changed(self):
        xid_to_id = {}
        for note_id, window in self.windows.items():
            if window.get_visible():
                xid = x11_utils.get_xid(window)
                if xid is not None:
                    xid_to_id[xid] = note_id

        if self.note_manager_window is not None and self.note_manager_window.get_visible():
            manager_xid = x11_utils.get_xid(self.note_manager_window)
            if manager_xid is not None:
                combined_order = x11_utils.get_stacking_order(
                    list(xid_to_id.keys()) + [manager_xid]
                )
                if combined_order and combined_order[-1] != manager_xid:
                    x11_utils.raise_window(self.note_manager_window)

        order = x11_utils.get_stacking_order(list(xid_to_id.keys()))
        if not order:
            return
        id_order = [xid_to_id[xid] for xid in order]
        id_order_set = set(id_order)
        notes_by_id = {n["id"]: n for n in self.notes}
        untouched = [n for n in self.notes if n["id"] not in id_order_set]
        reordered = [notes_by_id[i] for i in id_order]
        self.notes = untouched + reordered
        self._queue_save_all()

    def _queue_save_all(self):
        if self._stacking_save_source_id is not None:
            GLib.source_remove(self._stacking_save_source_id)
        self._stacking_save_source_id = GLib.timeout_add(
            STACKING_SAVE_DELAY_MS, self._debounced_save_all
        )

    def _debounced_save_all(self):
        self._stacking_save_source_id = None
        self.save_all()
        return GLib.SOURCE_REMOVE

    def show_settings(self):
        if self.settings_window is None:
            self.settings_window = SettingsWindow(self)
            self.settings_window.connect("close-request", self._on_settings_closed)
        self.settings_window.present()

    def _on_settings_closed(self, *_args):
        self.settings_window = None
        return False

    def show_note_manager(self):
        if self.note_manager_window is None:
            self.note_manager_window = NoteManagerWindow(self)
            self.note_manager_window.connect("close-request", self._on_note_manager_closed)
        else:
            self.note_manager_window._refresh()
        self.note_manager_window.present()

    def _on_note_manager_closed(self, *_args):
        self.note_manager_window = None
        return False

    def create_note(self):
        x, y = self._next_cascade_position()
        current_settings = settings_module.load_settings()
        width = current_settings.get("default_note_width", 260)
        height = current_settings.get("default_note_height", 260)
        note = storage.new_note(x=x, y=y, width=width, height=height)
        self.notes.append(note)
        self._open_window(note)
        self.notes_visible = True
        self.sync_open_ids()
        self.save_all()

    def _next_cascade_position(self):
        self._cascade_index = (self._cascade_index + 1) % NEW_NOTE_CASCADE_STEPS
        offset = self._cascade_index * NEW_NOTE_CASCADE_STEP
        return NEW_NOTE_BASE_X + offset, NEW_NOTE_BASE_Y + offset

    def _open_window(self, note, visible=True):
        window = NoteWindow(self, note, on_delete=self.delete_note)
        self.windows[note["id"]] = window
        if visible:
            window.present_at_position()

    def delete_note(self, note_id):
        self.windows.pop(note_id, None)
        for note in self.notes:
            if note["id"] == note_id:
                note["deleted_at"] = time.time()
                break
        self.sync_open_ids()
        self.save_all()
        if self.note_manager_window is not None:
            self.note_manager_window._refresh()

    def restore_note(self, note_id):
        note = next((n for n in self.notes if n["id"] == note_id), None)
        if note is None:
            return
        note.pop("deleted_at", None)
        self._open_window(note, visible=False)
        self.save_all()
        if self.note_manager_window is not None:
            self.note_manager_window._refresh()

    def permanently_delete_note(self, note_id):
        self.notes = [n for n in self.notes if n["id"] != note_id]
        self.save_all()
        if self.note_manager_window is not None:
            self.note_manager_window._refresh()

    def save_all(self):
        storage.save_notes(self.notes)

    def _on_shutdown(self, *_args):
        for window in self.windows.values():
            window.sync_state()
        self.save_all()
        if self._tray_process is not None:
            self._tray_process.terminate()
