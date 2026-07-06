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
        """Notes in a stable display order that only shifts when notes are
        added/removed -- self.app.notes itself gets reshuffled to track
        window stacking order, which shouldn't affect this list's layout."""
        notes_by_id = {n["id"]: n for n in self.app.notes}
        current_ids = set(notes_by_id)

        self._id_order = [i for i in self._id_order if i in current_ids]
        seen = set(self._id_order)
        for note in self.app.notes:
            if note["id"] not in seen:
                self._id_order.append(note["id"])
                seen.add(note["id"])

        return [notes_by_id[i] for i in self._id_order]

    def _refresh(self):
        groups, ungrouped = storage.groups_and_notes(self._ordered_notes())
        open_ids = self.app.get_open_note_ids()

        signature = [(name, tuple(n["id"] for n in notes)) for name, notes in groups.items()]
        if ungrouped:
            signature.append((None, tuple(n["id"] for n in ungrouped)))

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
