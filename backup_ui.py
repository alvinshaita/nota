"""Shared GTK file-picker flows for exporting/importing note backups, used
from Settings (export all + import), Manage Notes (export a group), and a
note's own window (export just that note)."""
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

import backup


def export_notes_with_picker(parent, notes, default_name):
    dialog = Gtk.FileChooserNative.new(
        "Export Notes", parent, Gtk.FileChooserAction.SAVE, "Export", "Cancel"
    )
    dialog.set_current_name(default_name)
    dialog.connect("response", _on_export_response, notes, parent)
    dialog.show()
    parent._backup_dialog = dialog  # keep alive until the user responds


def _on_export_response(dialog, response, notes, parent):
    if response == Gtk.ResponseType.ACCEPT:
        path = dialog.get_file().get_path()
        try:
            backup.write_backup(path, notes)
        except OSError as e:
            _show_message(parent, "Export failed", str(e))
    dialog.destroy()
    parent._backup_dialog = None


def import_backup_with_picker(parent, app):
    dialog = Gtk.FileChooserNative.new(
        "Import Backup", parent, Gtk.FileChooserAction.OPEN, "Import", "Cancel"
    )
    dialog.connect("response", _on_import_response, app, parent)
    dialog.show()
    parent._backup_dialog = dialog


def _on_import_response(dialog, response, app, parent):
    if response == Gtk.ResponseType.ACCEPT:
        path = dialog.get_file().get_path()
        try:
            count = app.import_backup_from_file(path)
        except (ValueError, OSError) as e:
            _show_message(parent, "Import failed", str(e))
        else:
            note_word = "note" if count == 1 else "notes"
            _show_message(parent, "Import complete", f"Imported {count} {note_word}.")
    dialog.destroy()
    parent._backup_dialog = None


def _show_message(parent, title, message):
    dialog = Gtk.Dialog(title=title, transient_for=parent, modal=True)
    dialog.add_buttons("OK", Gtk.ResponseType.OK)
    content = dialog.get_content_area()
    content.set_margin_top(12)
    content.set_margin_bottom(12)
    content.set_margin_start(12)
    content.set_margin_end(12)
    label = Gtk.Label(label=message)
    label.set_wrap(True)
    content.append(label)
    dialog.connect("response", lambda d, _r: d.destroy())
    dialog.present()
