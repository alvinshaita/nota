"""A window listing every group and note with checkboxes, so several notes
can be shown/hidden without the tray menu closing after each click."""
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

import storage


class NoteManagerWindow(Adw.Window):
    def __init__(self, app):
        super().__init__(application=app, title="Manage Notes")
        self.app = app
        self.set_default_size(320, 420)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(root)

        header = Gtk.HeaderBar()
        header.set_title_widget(Gtk.Label(label="Manage Notes"))
        root.append(header)

        self.scroller = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        root.append(self.scroller)

        self.box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=4,
            margin_top=10, margin_bottom=10, margin_start=10, margin_end=10,
        )
        self.scroller.set_child(self.box)

        self._id_order = []
        self._checkboxes = {}
        self._structure_signature = None

        self.connect("show", lambda *_: self._refresh())
        self._refresh()

    def _ordered_notes(self):
        """Active notes in a stable display order that only shifts when notes
        are added/removed -- self.app.notes itself gets reshuffled to track
        window stacking order, which shouldn't affect this list's layout."""
        active = storage.active_notes(self.app.notes)
        notes_by_id = {n["id"]: n for n in active}
        current_ids = set(notes_by_id)

        self._id_order = [i for i in self._id_order if i in current_ids]
        seen = set(self._id_order)
        for note in active:
            if note["id"] not in seen:
                self._id_order.append(note["id"])
                seen.add(note["id"])

        return [notes_by_id[i] for i in self._id_order]

    def _refresh(self):
        groups, ungrouped = storage.groups_and_notes(self._ordered_notes())
        open_ids = self.app.get_open_note_ids()
        trash = sorted(
            storage.deleted_notes(self.app.notes),
            key=lambda n: n.get("deleted_at", 0), reverse=True,
        )

        signature = [(name, tuple(n["id"] for n in notes)) for name, notes in groups.items()]
        if ungrouped:
            signature.append((None, tuple(n["id"] for n in ungrouped)))
        if trash:
            signature.append(("__trash__", tuple(n["id"] for n in trash)))

        titles_by_id = {
            n["id"]: storage.note_title(n)
            for notes in list(groups.values()) + [ungrouped]
            for n in notes
        }

        if signature == self._structure_signature:
            # Same notes/groups/order as last time -- update checkboxes and
            # labels in place instead of rebuilding, so nothing gets destroyed
            # out from under a focused/just-clicked widget (that was causing
            # the list to lose its scroll position and jump to the top).
            for note_id, (check, handler_id) in self._checkboxes.items():
                desired = note_id in open_ids
                if check.get_active() != desired:
                    check.handler_block(handler_id)
                    check.set_active(desired)
                    check.handler_unblock(handler_id)
                title = titles_by_id.get(note_id)
                if title is not None and check.get_label() != title:
                    check.set_label(title)
            return

        vadj = self.scroller.get_vadjustment()
        scroll_value = vadj.get_value()

        child = self.box.get_first_child()
        while child is not None:
            next_child = child.get_next_sibling()
            self.box.remove(child)
            child = next_child
        self._checkboxes = {}

        for group_name, notes in groups.items():
            self.box.append(self._build_group_expander(group_name, notes, open_ids))

        if ungrouped:
            self.box.append(self._build_group_expander(None, ungrouped, open_ids))

        if trash:
            self.box.append(self._build_trash_expander(trash))

        self._structure_signature = signature
        GLib.idle_add(vadj.set_value, scroll_value)

    def _build_group_expander(self, group_name, notes, open_ids):
        expander = Gtk.Expander()
        expander.set_expanded(True)
        if group_name:
            header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)

            name_label = Gtk.EditableLabel(text=group_name)
            name_label.set_hexpand(True)
            name_label.connect("notify::editing", self._on_group_name_editing_changed, group_name)
            header_box.append(name_label)

            rename_btn = Gtk.Button(icon_name="document-edit-symbolic")
            rename_btn.add_css_class("flat")
            rename_btn.set_tooltip_text("Rename group")
            rename_btn.connect("clicked", lambda _b, l=name_label: l.start_editing())
            header_box.append(rename_btn)

            expander.set_label_widget(header_box)
        else:
            label = Gtk.Label()
            label.set_markup("<i>ungrouped</i>")
            expander.set_label_widget(label)

        inner_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=2,
            margin_start=16, margin_top=4, margin_bottom=4,
        )
        for note in notes:
            check = Gtk.CheckButton(label=storage.note_title(note))
            check.set_active(note["id"] in open_ids)
            handler_id = check.connect("toggled", self._on_note_toggled, note["id"])
            self._checkboxes[note["id"]] = (check, handler_id)
            inner_box.append(check)
        expander.set_child(inner_box)
        return expander

    def _on_note_toggled(self, _check, note_id):
        self.app.toggle_note(note_id)

    def _build_trash_expander(self, notes):
        expander = Gtk.Expander()
        expander.set_expanded(False)
        label = Gtk.Label()
        label.set_markup(f"<i>Trash ({len(notes)})</i>")
        expander.set_label_widget(label)

        inner_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=4,
            margin_start=16, margin_top=4, margin_bottom=4,
        )
        for note in notes:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)

            title_label = Gtk.Label(label=storage.note_title(note), xalign=0, hexpand=True)
            row.append(title_label)

            restore_btn = Gtk.Button(icon_name="edit-undo-symbolic")
            restore_btn.add_css_class("flat")
            restore_btn.set_tooltip_text("Restore")
            restore_btn.connect("clicked", self._on_restore_clicked, note["id"])
            row.append(restore_btn)

            delete_btn = Gtk.Button(icon_name="user-trash-symbolic")
            delete_btn.add_css_class("flat")
            delete_btn.set_tooltip_text("Delete forever")
            delete_btn.connect(
                "clicked", self._on_delete_forever_clicked, note["id"], storage.note_title(note)
            )
            row.append(delete_btn)

            inner_box.append(row)

        clear_btn = Gtk.Button(label="Clear Trash")
        clear_btn.add_css_class("destructive-action")
        clear_btn.set_margin_top(6)
        clear_btn.connect("clicked", self._on_clear_trash_clicked, len(notes))
        inner_box.append(clear_btn)

        expander.set_child(inner_box)
        return expander

    def _on_restore_clicked(self, _btn, note_id):
        self.app.restore_note(note_id)

    def _on_clear_trash_clicked(self, _btn, count):
        dialog = Gtk.Dialog(title="Clear trash?", transient_for=self, modal=True)
        dialog.add_buttons(
            "Cancel", Gtk.ResponseType.CANCEL,
            "Clear Trash", Gtk.ResponseType.ACCEPT,
        )
        dialog.get_widget_for_response(Gtk.ResponseType.ACCEPT).add_css_class("destructive-action")

        content = dialog.get_content_area()
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_margin_start(12)
        content.set_margin_end(12)
        note_word = "note" if count == 1 else "notes"
        label = Gtk.Label(
            label=f"Permanently delete all {count} {note_word} in Trash? This cannot be undone."
        )
        label.set_wrap(True)
        content.append(label)

        dialog.connect("response", self._on_clear_trash_response)
        dialog.present()

    def _on_clear_trash_response(self, dialog, response):
        dialog.destroy()
        if response == Gtk.ResponseType.ACCEPT:
            self.app.clear_trash()

    def _on_delete_forever_clicked(self, _btn, note_id, title):
        dialog = Gtk.Dialog(title="Delete forever?", transient_for=self, modal=True)
        dialog.add_buttons(
            "Cancel", Gtk.ResponseType.CANCEL,
            "Delete Forever", Gtk.ResponseType.ACCEPT,
        )
        dialog.get_widget_for_response(Gtk.ResponseType.ACCEPT).add_css_class("destructive-action")

        content = dialog.get_content_area()
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_margin_start(12)
        content.set_margin_end(12)
        label = Gtk.Label(label=f"Permanently delete “{title}”? This cannot be undone.")
        label.set_wrap(True)
        content.append(label)

        dialog.connect("response", self._on_delete_forever_response, note_id)
        dialog.present()

    def _on_delete_forever_response(self, dialog, response, note_id):
        dialog.destroy()
        if response == Gtk.ResponseType.ACCEPT:
            self.app.permanently_delete_note(note_id)

    def _on_group_name_editing_changed(self, label, _pspec, old_name):
        if label.get_editing():
            return
        # Defer past this notify handler -- rebuilding the expander tree
        # (which destroys this same label) from inside its own signal
        # emission is asking for trouble.
        GLib.idle_add(self._rename_group, old_name, label.get_text())

    def _rename_group(self, old_name, new_name):
        new_name = new_name.strip()
        if new_name and new_name != old_name:
            changed = False
            for note in self.app.notes:
                if note.get("group") == old_name:
                    note["group"] = new_name
                    changed = True
            if changed:
                self.app.save_all()
                self._refresh()
        return GLib.SOURCE_REMOVE
