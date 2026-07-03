"""A single sticky note window."""
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, GLib, Gtk

import settings as settings_module
import storage
import x11_utils

AUTOSAVE_DELAY_MS = 800

PALETTE = [
    "#f9e08a",  # yellow
    "#a8e6a1",  # green
    "#a8d8f9",  # blue
    "#f7a8c4",  # pink
    "#d6b8f5",  # purple
    "#f2f2f2",  # white/grey
]

RESIZE_EDGE_THICKNESS = 6
RESIZE_CORNER_SIZE = 14

# (edge, cursor name, halign, valign, width, height)
RESIZE_GRIPS = [
    (Gdk.SurfaceEdge.NORTH, "n-resize", Gtk.Align.FILL, Gtk.Align.START,
     -1, RESIZE_EDGE_THICKNESS),
    (Gdk.SurfaceEdge.SOUTH, "s-resize", Gtk.Align.FILL, Gtk.Align.END,
     -1, RESIZE_EDGE_THICKNESS),
    (Gdk.SurfaceEdge.WEST, "w-resize", Gtk.Align.START, Gtk.Align.FILL,
     RESIZE_EDGE_THICKNESS, -1),
    (Gdk.SurfaceEdge.EAST, "e-resize", Gtk.Align.END, Gtk.Align.FILL,
     RESIZE_EDGE_THICKNESS, -1),
    (Gdk.SurfaceEdge.NORTH_WEST, "nw-resize", Gtk.Align.START, Gtk.Align.START,
     RESIZE_CORNER_SIZE, RESIZE_CORNER_SIZE),
    (Gdk.SurfaceEdge.NORTH_EAST, "ne-resize", Gtk.Align.END, Gtk.Align.START,
     RESIZE_CORNER_SIZE, RESIZE_CORNER_SIZE),
    (Gdk.SurfaceEdge.SOUTH_WEST, "sw-resize", Gtk.Align.START, Gtk.Align.END,
     RESIZE_CORNER_SIZE, RESIZE_CORNER_SIZE),
    (Gdk.SurfaceEdge.SOUTH_EAST, "se-resize", Gtk.Align.END, Gtk.Align.END,
     RESIZE_CORNER_SIZE, RESIZE_CORNER_SIZE),
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

        overlay = Gtk.Overlay()
        overlay.set_child(root)
        for edge, cursor_name, halign, valign, width, height in RESIZE_GRIPS:
            overlay.add_overlay(self._make_resize_grip(edge, cursor_name, halign, valign, width, height))
        self.set_content(overlay)

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

        self._group_popover = self._build_group_popover()
        group_btn = Gtk.MenuButton(icon_name="tag-symbolic")
        group_btn.set_tooltip_text("Add to group")
        group_btn.add_css_class("flat")
        group_btn.set_popover(self._group_popover)
        toolbar.append(group_btn)

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

        self._font_family = None
        self._apply_color(self.note.get("color", storage.DEFAULT_COLOR))
        self.apply_font(settings_module.FONT_CHOICES.get(
            settings_module.load_settings().get("font_family", "system")
        ))

        self.connect("close-request", self._on_close_request)
        self.connect("notify::default-width", self._queue_autosave)
        self.connect("notify::default-height", self._queue_autosave)
        self.connect("realize", self._on_realize)
        self.connect("destroy", lambda *_: x11_utils.unwatch_position(self))

    def present_at_position(self):
        self.present()
        x11_utils.move_window(self, self.note["x"], self.note["y"])

    def _on_realize(self, *_args):
        x11_utils.watch_position(self, self._on_position_changed)

    def _on_position_changed(self, x, y):
        self.note["x"] = x
        self.note["y"] = y
        self._queue_autosave()

    def _make_resize_grip(self, edge, cursor_name, halign, valign, width, height):
        grip = Gtk.Box()
        grip.set_size_request(width, height)
        grip.set_halign(halign)
        grip.set_valign(valign)
        grip.set_cursor(Gdk.Cursor.new_from_name(cursor_name))

        gesture = Gtk.GestureClick.new()
        gesture.set_button(1)
        gesture.connect("pressed", self._on_resize_pressed, edge)
        grip.add_controller(gesture)
        return grip

    def _on_resize_pressed(self, gesture, _n_press, x, y, edge):
        widget = gesture.get_widget()
        surface = self.get_surface()
        device = gesture.get_device()
        button = gesture.get_current_button()
        sx, sy = widget.translate_coordinates(self, x, y)
        surface.begin_resize(edge, device, button, sx, sy, Gdk.CURRENT_TIME)

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

    def _build_group_popover(self):
        popover = Gtk.Popover()
        popover.connect("show", self._refresh_group_popover)
        return popover

    def _refresh_group_popover(self, popover):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2,
                       margin_top=6, margin_bottom=6, margin_start=6, margin_end=6)
        current_group = self.note.get("group")

        none_btn = Gtk.Button(label=("✓ No Group" if not current_group else "No Group"))
        none_btn.add_css_class("flat")
        none_btn.connect("clicked", self._on_group_chosen, None, popover)
        box.append(none_btn)

        groups = self.app.get_all_groups()
        if groups:
            box.append(Gtk.Separator())
            for group in groups:
                label = f"✓ {group}" if group == current_group else group
                btn = Gtk.Button(label=label)
                btn.add_css_class("flat")
                btn.connect("clicked", self._on_group_chosen, group, popover)
                box.append(btn)

        box.append(Gtk.Separator())
        entry_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        entry = Gtk.Entry(placeholder_text="New group…")
        entry.set_hexpand(True)
        add_btn = Gtk.Button(icon_name="list-add-symbolic")
        add_btn.connect("clicked", lambda *_: self._create_group_from_entry(entry, popover))
        entry.connect("activate", lambda *_: self._create_group_from_entry(entry, popover))
        entry_box.append(entry)
        entry_box.append(add_btn)
        box.append(entry_box)

        popover.set_child(box)

    def _create_group_from_entry(self, entry, popover):
        name = entry.get_text().strip()
        if name:
            self._on_group_chosen(None, name, popover)

    def _on_group_chosen(self, _button, group, popover):
        self.note["group"] = group
        self._queue_autosave()
        popover.popdown()

    def _apply_color(self, hex_color):
        self.note["color"] = hex_color
        self._refresh_css()

    def apply_font(self, font_family):
        self._font_family = font_family
        self._refresh_css()

    def _refresh_css(self):
        hex_color = self.note.get("color", storage.DEFAULT_COLOR)
        font_rule = f'font-family: "{self._font_family}";' if self._font_family else ""
        css = f"""
        .{self._css_class} {{ background-color: {hex_color}; }}
        .{self._css_class} textview.note-text,
        .{self._css_class} textview.note-text text {{
            background-color: {hex_color};
            color: #2b2b2b;
            {font_rule}
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
        position = x11_utils.get_position(self)
        if position is not None:
            self.note["x"], self.note["y"] = position

    def _on_close_request(self, *_args):
        self.sync_state()
        self.set_visible(False)
        self.app.sync_open_ids()
        self.app.save_all()
        return True

    def _on_delete_clicked(self, *_args):
        self._on_delete(self.note["id"])
        self.destroy()
