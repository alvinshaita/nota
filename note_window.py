"""A single sticky note window."""
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk

import storage

AUTOSAVE_DELAY_MS = 800

PALETTE = [
    "#f9e08a",  # yellow
    "#a8e6a1",  # green
    "#a8d8f9",  # blue
    "#f7a8c4",  # pink
    "#d6b8f5",  # purple
    "#f2f2f2",  # white/grey
]


class NoteWindow(Adw.Window):
    def __init__(self, app, note_data, on_delete):
        super().__init__(application=app)
        self.app = app
        self.note = note_data
        self._on_delete = on_delete
        self._autosave_source_id = None
        self._css_provider = Gtk.CssProvider()
        self._css_class = f"note-{self.note['id'][:8]}"

        self.set_default_size(self.note["width"], self.note["height"])
        self.set_decorated(False)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        root.add_css_class(self._css_class)
        self.set_content(root)

        handle = Gtk.WindowHandle()
        root.append(handle)

        toolbar = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=4,
            margin_top=4,
            margin_bottom=2,
            margin_start=6,
            margin_end=6,
        )
        handle.set_child(toolbar)

        new_btn = Gtk.Button(icon_name="list-add-symbolic")
        new_btn.set_tooltip_text("New note")
        new_btn.add_css_class("flat")
        new_btn.connect("clicked", lambda *_: self.app.create_note())
        toolbar.append(new_btn)

        color_btn = Gtk.MenuButton(icon_name="applications-graphics-symbolic")
        color_btn.set_tooltip_text("Color")
        color_btn.add_css_class("flat")
        color_btn.set_popover(self._build_color_popover())
        toolbar.append(color_btn)

        spacer = Gtk.Box(hexpand=True)
        toolbar.append(spacer)

        delete_btn = Gtk.Button(icon_name="user-trash-symbolic")
        delete_btn.set_tooltip_text("Delete note")
        delete_btn.add_css_class("flat")
        delete_btn.connect("clicked", self._on_delete_clicked)
        toolbar.append(delete_btn)

        close_btn = Gtk.Button(icon_name="window-close-symbolic")
        close_btn.set_tooltip_text("Close (keeps note)")
        close_btn.add_css_class("flat")
        close_btn.connect("clicked", lambda *_: self.close())
        toolbar.append(close_btn)

        scroller = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        root.append(scroller)

        self.text_view = Gtk.TextView(
            wrap_mode=Gtk.WrapMode.WORD_CHAR,
            top_margin=8,
            bottom_margin=8,
            left_margin=10,
            right_margin=10,
        )
        self.text_view.add_css_class("note-text")
        self.text_view.get_buffer().set_text(self.note.get("text", ""))
        self.text_view.get_buffer().connect("changed", self._queue_autosave)
        scroller.set_child(self.text_view)

        self._apply_color(self.note.get("color", storage.DEFAULT_COLOR))

        self.connect("close-request", self._on_close_request)
        self.connect("notify::default-width", self._queue_autosave)
        self.connect("notify::default-height", self._queue_autosave)

    def _build_color_popover(self):
        popover = Gtk.Popover()
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4,
                       margin_top=6, margin_bottom=6, margin_start=6, margin_end=6)
        for hex_color in PALETTE:
            swatch = Gtk.Button()
            swatch.set_size_request(24, 24)
            swatch.add_css_class("flat")
            provider = Gtk.CssProvider()
            provider.load_from_data(
                f"button {{ background-color: {hex_color}; border-radius: 4px; }}".encode()
            )
            swatch.get_style_context().add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            swatch.connect("clicked", self._on_color_chosen, hex_color, popover)
            box.append(swatch)
        popover.set_child(box)
        return popover

    def _on_color_chosen(self, _button, hex_color, popover):
        self._apply_color(hex_color)
        self._queue_autosave()
        popover.popdown()

    def _apply_color(self, hex_color):
        self.note["color"] = hex_color
        css = f"""
        .{self._css_class} {{ background-color: {hex_color}; }}
        .{self._css_class} textview.note-text,
        .{self._css_class} textview.note-text text {{
            background-color: {hex_color};
            color: #2b2b2b;
        }}
        """
        self._css_provider.load_from_data(css.encode())
        display = Gdk.Display.get_default()
        Gtk.StyleContext.add_provider_for_display(
            display, self._css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def _queue_autosave(self, *_args):
        if self._autosave_source_id is not None:
            GLib.source_remove(self._autosave_source_id)
        self._autosave_source_id = GLib.timeout_add(AUTOSAVE_DELAY_MS, self._autosave)

    def _autosave(self):
        self._autosave_source_id = None
        self.sync_state()
        self.app.save_all()
        return GLib.SOURCE_REMOVE

    def sync_state(self):
        buf = self.text_view.get_buffer()
        self.note["text"] = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), True)
        width, height = self.get_default_size()
        if width > 0:
            self.note["width"] = width
        if height > 0:
            self.note["height"] = height

    def _on_close_request(self, *_args):
        self.sync_state()
        self.app.save_all()
        return False

    def _on_delete_clicked(self, *_args):
        self._on_delete(self.note["id"])
        self.close()
