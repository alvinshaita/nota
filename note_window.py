"""A single sticky note window."""
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Graphene", "1.0")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Graphene, Pango

import settings as settings_module
import storage
import x11_utils

AUTOSAVE_DELAY_MS = 800

FORMAT_TAGS = ["bold", "italic", "underline", "strikethrough"]
FORMAT_SHORTCUTS = {
    "bold": ["<Primary>b"],
    "italic": ["<Primary>i"],
    "underline": ["<Primary>u"],
    "strikethrough": ["<Primary><Shift>x"],
}

UNDERLINE_COLOR = Gdk.RGBA()
UNDERLINE_COLOR.parse("#2b2b2b")


class FormattedTextView(Gtk.TextView):
    """Plain Gtk.TextView, except underline is hand-drawn via the snapshot
    layer API instead of relying on Pango's underline attribute -- which,
    in this environment's GTK4/Pango build, silently fails to render unless
    the run also has another attribute (e.g. bold) changing. Strikethrough,
    bold and italic all render fine through the normal Pango path; this
    workaround is scoped to underline only."""

    def do_snapshot_layer(self, layer, snapshot):
        if layer != Gtk.TextViewLayer.ABOVE_TEXT:
            return
        buf = self.get_buffer()
        tag = buf.get_tag_table().lookup("underline")
        if tag is None:
            return
        it = buf.get_start_iter()
        in_range = False
        range_start = None
        while True:
            has = it.has_tag(tag)
            if has and not in_range:
                range_start = it.copy()
                in_range = True
            elif not has and in_range:
                self._draw_underline_range(snapshot, range_start, it)
                in_range = False
            if not it.forward_char():
                break
        if in_range:
            self._draw_underline_range(snapshot, range_start, buf.get_end_iter())

    def _draw_underline_range(self, snapshot, start_it, end_it):
        bold_tag = self.get_buffer().get_tag_table().lookup("bold")
        it = start_it.copy()
        seg_x = seg_y = seg_h = seg_bold = None
        seg_right = None
        while it.compare(end_it) < 0:
            rect = self.get_iter_location(it)
            wx, wy = self.buffer_to_window_coords(Gtk.TextWindowType.WIDGET, rect.x, rect.y)
            is_bold = bold_tag is not None and it.has_tag(bold_tag)
            if seg_x is None:
                seg_x, seg_y, seg_h, seg_bold = wx, wy, rect.height, is_bold
            elif wy != seg_y or is_bold != seg_bold:
                self._append_underline_rect(snapshot, seg_x, seg_y, seg_right - seg_x, seg_h, seg_bold)
                seg_x, seg_y, seg_h, seg_bold = wx, wy, rect.height, is_bold
            seg_right = wx + rect.width
            if not it.forward_char():
                break
        if seg_x is not None:
            self._append_underline_rect(snapshot, seg_x, seg_y, seg_right - seg_x, seg_h, seg_bold)

    def _append_underline_rect(self, snapshot, x, y, width, height, is_bold=False):
        thickness = 2 if is_bold else 1
        rect = Graphene.Rect.alloc()
        rect.init(x, y + height * 0.4, max(width, 1), thickness)
        snapshot.append_color(UNDERLINE_COLOR, rect)

BULLET_GLYPHS = ["•", "◦", "▪"]
BULLET_INDENT_PX_PER_LEVEL = 24

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

        self.title_entry = Gtk.Entry()
        self.title_entry.set_placeholder_text("Title")
        self.title_entry.set_text(self.note.get("title", ""))
        self.title_entry.set_has_frame(False)
        self.title_entry.set_hexpand(True)
        self.title_entry.add_css_class("note-title")
        self.title_entry.set_margin_start(10)
        self.title_entry.set_margin_end(10)
        self.title_entry.set_margin_bottom(2)
        self.title_entry.connect("changed", self._on_title_changed)
        self.title_entry.connect("activate", self._on_title_activate)
        root.append(self.title_entry)

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

        self.text_view = FormattedTextView(
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

        current_settings = settings_module.load_settings()
        # _apply_formatting (called from _setup_formatting below) needs to
        # restore saved bullet-depth tags, which requires these two -- set
        # them before _setup_formatting() runs rather than in
        # _setup_auto_bullet_lists() further down, which is too late.
        self._auto_bullet_lists = current_settings.get("auto_bullet_lists", True)
        self._vary_bullet_symbols = current_settings.get("vary_bullet_symbols", True)

        self._setup_formatting()

        self._font_family = None
        self._line_height = 1.0
        self._font_size = 0
        self._apply_color(self.note.get("color", storage.DEFAULT_COLOR))
        self.apply_font(settings_module.FONT_CHOICES.get(
            current_settings.get("font_family", "system")
        ))
        self.apply_line_spacing(
            current_settings.get("pixels_above_lines", 0),
            current_settings.get("pixels_inside_wrap", 0),
            current_settings.get("line_height", 1.0),
        )
        self.apply_font_size(current_settings.get("font_size", 0))
        self._setup_auto_bullet_lists(
            current_settings.get("auto_bullet_lists", True),
            current_settings.get("vary_bullet_symbols", True),
        )

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

    def _setup_formatting(self):
        buf = self.text_view.get_buffer()
        buf.create_tag("bold", weight=Pango.Weight.BOLD)
        buf.create_tag("italic", style=Pango.Style.ITALIC)
        buf.create_tag("underline")
        buf.create_tag("strikethrough", strikethrough=True)
        self._apply_formatting(self.note.get("formatting"))

        action_group = Gio.SimpleActionGroup()
        shortcut_controller = Gtk.ShortcutController()
        shortcut_controller.set_scope(Gtk.ShortcutScope.LOCAL)
        for name in FORMAT_TAGS:
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", self._on_toggle_format, name)
            action_group.add_action(action)
            for accel in FORMAT_SHORTCUTS[name]:
                trigger = Gtk.ShortcutTrigger.parse_string(accel)
                named_action = Gtk.NamedAction.new(f"format.{name}")
                shortcut_controller.add_shortcut(Gtk.Shortcut.new(trigger, named_action))
        self.text_view.insert_action_group("format", action_group)
        self.text_view.add_controller(shortcut_controller)

        menu_model = Gio.Menu()
        menu_model.append("Bold", "format.bold")
        menu_model.append("Italic", "format.italic")
        menu_model.append("Underline", "format.underline")
        menu_model.append("Strikethrough", "format.strikethrough")
        self.text_view.set_extra_menu(menu_model)

    def _on_toggle_format(self, _action, _param, tag_name):
        buf = self.text_view.get_buffer()
        bounds = buf.get_selection_bounds()
        if not bounds:
            return
        start, end = bounds
        tag = buf.get_tag_table().lookup(tag_name)
        if self._selection_fully_tagged(buf, tag, start, end):
            buf.remove_tag(tag, start, end)
        else:
            buf.apply_tag(tag, start, end)
        self._queue_autosave()

    def _selection_fully_tagged(self, buf, tag, start, end):
        it = start.copy()
        while it.compare(end) < 0:
            if not it.has_tag(tag):
                return False
            if not it.forward_char():
                break
        return True

    def _all_bullet_tag_names(self, buf):
        names = []

        def _collect(tag, *_args):
            name = tag.get_property("name") or ""
            if name.startswith("bullet-depth-"):
                names.append(name)

        buf.get_tag_table().foreach(_collect)
        return names

    def _serialize_formatting(self):
        buf = self.text_view.get_buffer()
        result = {}
        for name in FORMAT_TAGS + self._all_bullet_tag_names(buf):
            tag = buf.get_tag_table().lookup(name)
            ranges = []
            it = buf.get_start_iter()
            in_range = False
            range_start = 0
            while True:
                has = it.has_tag(tag)
                if has and not in_range:
                    range_start = it.get_offset()
                    in_range = True
                elif not has and in_range:
                    ranges.append([range_start, it.get_offset()])
                    in_range = False
                if not it.forward_char():
                    break
            if in_range:
                ranges.append([range_start, buf.get_end_iter().get_offset()])
            if ranges:
                result[name] = ranges
        return result

    def _apply_formatting(self, formatting):
        buf = self.text_view.get_buffer()
        for name, ranges in (formatting or {}).items():
            if name.startswith("bullet-depth-"):
                try:
                    depth = int(name.rsplit("-", 1)[1])
                except ValueError:
                    continue
                tag = self._bullet_tag_for_depth(depth)
            else:
                tag = buf.get_tag_table().lookup(name)
            if tag is None:
                continue
            for start_off, end_off in ranges:
                start_it = buf.get_iter_at_offset(start_off)
                end_it = buf.get_iter_at_offset(end_off)
                buf.apply_tag(tag, start_it, end_it)

    def _apply_color(self, hex_color):
        self.note["color"] = hex_color
        self._refresh_css()

    def apply_font(self, font_family):
        self._font_family = font_family
        self._refresh_css()

    def apply_line_spacing(self, pixels_above_lines, pixels_inside_wrap, line_height):
        self.text_view.set_pixels_above_lines(pixels_above_lines)
        self.text_view.set_pixels_inside_wrap(pixels_inside_wrap)
        self._line_height = line_height
        self._refresh_css()

    def apply_font_size(self, size):
        self._font_size = size
        self._refresh_css()

    def _setup_auto_bullet_lists(self, enabled, vary_symbols):
        self._auto_bullet_lists = enabled
        self._vary_bullet_symbols = vary_symbols
        self.text_view.get_buffer().connect_after("insert-text", self._on_text_inserted)
        key_controller = Gtk.EventControllerKey.new()
        key_controller.connect("key-pressed", self._on_text_key_pressed)
        self.text_view.add_controller(key_controller)
        self._bullet_key_controller = key_controller

    def apply_auto_bullet_lists(self, enabled):
        self._auto_bullet_lists = enabled

    def apply_vary_bullet_symbols(self, enabled):
        self._vary_bullet_symbols = enabled

    def _bullet_glyph_for_depth(self, depth):
        if self._vary_bullet_symbols:
            return BULLET_GLYPHS[depth % len(BULLET_GLYPHS)]
        return BULLET_GLYPHS[0]

    def _measure_text_width_px(self, text):
        layout = self.text_view.create_pango_layout(text)
        width, _height = layout.get_pixel_size()
        return width

    def _bullet_tag_for_depth(self, depth):
        """Gets (or lazily creates) the shared TextTag that gives a bullet
        line at this depth its hanging indent: wrapped continuation lines
        align under the bullet's text rather than restarting at the note's
        left edge, since plain leading-space characters only affect a
        paragraph's first visual line, not its wrapped ones."""
        tag_table = self.text_view.get_buffer().get_tag_table()
        name = f"bullet-depth-{depth}"
        tag = tag_table.lookup(name)
        if tag is None:
            glyph = self._bullet_glyph_for_depth(depth)
            # Measure the marker's actual rendered width rather than
            # guessing a fixed pixel value -- a hardcoded estimate drifts
            # off by a character or so depending on font/glyph, so wrapped
            # lines land under the wrong letter of the bullet's own text.
            hang_px = self._measure_text_width_px(glyph + " ")
            tag = Gtk.TextTag.new(name)
            tag.set_property("left-margin", depth * BULLET_INDENT_PX_PER_LEVEL + hang_px)
            tag.set_property("indent", -hang_px)
            tag_table.add(tag)
        return tag

    def _bullet_depth_at_iter(self, it):
        for tag in it.get_tags():
            name = tag.get_property("name") or ""
            if name.startswith("bullet-depth-"):
                try:
                    return int(name.rsplit("-", 1)[1])
                except ValueError:
                    pass
        return 0

    def _set_line_bullet_depth(self, buf, line_start, depth):
        line_end = line_start.copy()
        line_end.forward_to_line_end()
        for tag in list(line_start.get_tags()):
            name = tag.get_property("name") or ""
            if name.startswith("bullet-depth-"):
                buf.remove_tag(tag, line_start, line_end)
        buf.apply_tag(self._bullet_tag_for_depth(depth), line_start, line_end)

    def _clear_line_bullet_tag(self, buf, line_start):
        line_end = line_start.copy()
        line_end.forward_to_line_end()
        for tag in list(line_start.get_tags()):
            name = tag.get_property("name") or ""
            if name.startswith("bullet-depth-"):
                buf.remove_tag(tag, line_start, line_end)

    def _parse_bullet_line(self, line_start, line_text_up_to_cursor):
        """If the line starts with a bullet marker (any known glyph + a
        space), returns (depth, prefix_len). Otherwise returns None. Depth
        comes from the line's hanging-indent tag, not the text itself."""
        for glyph in BULLET_GLYPHS:
            marker = glyph + " "
            if line_text_up_to_cursor.startswith(marker):
                return self._bullet_depth_at_iter(line_start), len(marker)
        return None

    def _on_text_inserted(self, buf, location, text, _length):
        if not self._auto_bullet_lists:
            return
        line_start = location.copy()
        line_start.set_line_offset(0)

        if text == " ":
            prefix = buf.get_text(line_start, location, False)
            if prefix == "- ":
                glyph = self._bullet_glyph_for_depth(0)
                buf.delete(line_start, location)
                buf.insert(line_start, glyph + " ")
                # line_start isn't guaranteed revalidated by the delete/
                # insert above (only iters directly passed to them are) --
                # refetch a fresh one from the cursor mark before tagging.
                fresh_start = buf.get_iter_at_mark(buf.get_insert())
                fresh_start.set_line_offset(0)
                self._set_line_bullet_depth(buf, fresh_start, 0)
                return

        # The hanging-indent tag only ever gets applied to exactly the
        # bullet marker at the moment it's created -- GTK doesn't
        # automatically extend a custom tag to text typed afterward. So as
        # more text is typed into an already-bulleted line, keep
        # re-covering the *whole* current line with the tag; otherwise only
        # the marker itself stays tagged and the rest of a wrapped line
        # loses its hanging indent (confirmed via saved formatting ranges
        # showing only the 2-char marker tagged despite a full sentence
        # having been typed after it).
        fresh_start = buf.get_iter_at_mark(buf.get_insert())
        fresh_start.set_line_offset(0)
        fresh_end = fresh_start.copy()
        fresh_end.forward_to_line_end()
        line_text_now = buf.get_text(fresh_start, fresh_end, False)
        for glyph in BULLET_GLYPHS:
            if line_text_now.startswith(glyph + " "):
                depth = self._bullet_depth_at_iter(fresh_start)
                self._set_line_bullet_depth(buf, fresh_start, depth)
                break

    def _on_text_key_pressed(self, _controller, keyval, _keycode, state):
        if not self._auto_bullet_lists:
            return False
        buf = self.text_view.get_buffer()
        cursor = buf.get_iter_at_mark(buf.get_insert())
        line_start = cursor.copy()
        line_start.set_line_offset(0)
        line_text = buf.get_text(line_start, cursor, False)
        parsed = self._parse_bullet_line(line_start, line_text)

        if keyval in (Gdk.KEY_Tab, Gdk.KEY_KP_Tab, Gdk.KEY_ISO_Left_Tab):
            if parsed is None:
                return False
            depth, prefix_len = parsed
            outdent = keyval == Gdk.KEY_ISO_Left_Tab or bool(state & Gdk.ModifierType.SHIFT_MASK)
            if outdent:
                if depth == 0:
                    return True
                new_depth = depth - 1
            else:
                new_depth = depth + 1
            new_glyph = self._bullet_glyph_for_depth(new_depth)
            prefix_start = line_start.copy()
            prefix_end = line_start.copy()
            prefix_end.forward_chars(prefix_len)
            buf.delete(prefix_start, prefix_end)
            buf.insert(prefix_start, new_glyph + " ")
            fresh_start = buf.get_iter_at_mark(buf.get_insert())
            fresh_start.set_line_offset(0)
            self._set_line_bullet_depth(buf, fresh_start, new_depth)
            self.text_view.scroll_mark_onscreen(buf.get_insert())
            return True

        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            if parsed is None:
                return False
            depth, prefix_len = parsed
            if line_text[prefix_len:].strip() == "":
                # Empty bullet -- exit the list by stripping the bullet
                # marker, staying on this same line (regardless of nesting
                # depth) rather than also advancing to a new one (returning
                # True suppresses the default Enter handling, which would
                # otherwise insert a redundant blank line here).
                buf.delete(line_start, cursor)
                self._clear_line_bullet_tag(buf, line_start)
                self.text_view.scroll_mark_onscreen(buf.get_insert())
                return True
            glyph = self._bullet_glyph_for_depth(depth)
            buf.insert(cursor, "\n" + glyph + " ")
            new_line_start = buf.get_iter_at_mark(buf.get_insert())
            new_line_start.set_line_offset(0)
            self._set_line_bullet_depth(buf, new_line_start, depth)
            self.text_view.scroll_mark_onscreen(buf.get_insert())
            return True

        if keyval == Gdk.KEY_BackSpace:
            if parsed is None:
                return False
            depth, prefix_len = parsed
            if len(line_text) != prefix_len:
                # Cursor isn't right at the start of the bullet's content --
                # let backspace behave normally (delete the previous char).
                return False
            prefix_start = line_start.copy()
            if depth == 0:
                # Top-level bullet -- strip the marker, leaving plain text.
                buf.delete(prefix_start, cursor)
                fresh_start = buf.get_iter_at_mark(buf.get_insert())
                fresh_start.set_line_offset(0)
                self._clear_line_bullet_tag(buf, fresh_start)
                self.text_view.scroll_mark_onscreen(buf.get_insert())
                return True
            new_depth = depth - 1
            new_glyph = self._bullet_glyph_for_depth(new_depth)
            buf.delete(prefix_start, cursor)
            buf.insert(prefix_start, new_glyph + " ")
            fresh_start = buf.get_iter_at_mark(buf.get_insert())
            fresh_start.set_line_offset(0)
            self._set_line_bullet_depth(buf, fresh_start, new_depth)
            self.text_view.scroll_mark_onscreen(buf.get_insert())
            return True

        return False

    def _refresh_css(self):
        hex_color = self.note.get("color", storage.DEFAULT_COLOR)
        font_rule = f'font-family: "{self._font_family}";' if self._font_family else ""
        line_height_rule = (
            f"line-height: {self._line_height};" if self._line_height != 1.0 else ""
        )
        font_size_rule = f"font-size: {self._font_size}pt;" if self._font_size else ""
        css = f"""
        .{self._css_class} {{ background-color: {hex_color}; }}
        .{self._css_class} textview.note-text,
        .{self._css_class} textview.note-text text {{
            background-color: {hex_color};
            color: #2b2b2b;
            {font_rule}
            {line_height_rule}
            {font_size_rule}
        }}
        .{self._css_class} entry.note-title,
        .{self._css_class} entry.note-title text {{
            background-color: {hex_color};
            color: #2b2b2b;
            font-weight: bold;
            font-size: 1.1em;
            {font_rule}
        }}
        .{self._css_class} entry.note-title {{
            box-shadow: none;
            border: none;
            padding-left: 2px;
            padding-right: 2px;
        }}
        """
        self._css_provider.load_from_data(css.encode())
        display = Gdk.Display.get_default()
        Gtk.StyleContext.add_provider_for_display(
            display, self._css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def _on_title_changed(self, entry):
        self.note["title"] = entry.get_text()
        self._queue_autosave()

    def _on_title_activate(self, _entry):
        if self._autosave_source_id is not None:
            GLib.source_remove(self._autosave_source_id)
            self._autosave_source_id = None
        self.sync_state()
        self.app.save_all()
        self.text_view.grab_focus()

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
        self.note["formatting"] = self._serialize_formatting()
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
        title = self.note.get("title", "").strip()
        buf = self.text_view.get_buffer()
        text = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), True).strip()
        if not title and not text:
            self._delete_note()
            return

        dialog = Gtk.Dialog(title="Delete note?", transient_for=self, modal=True)
        dialog.add_buttons(
            "Cancel", Gtk.ResponseType.CANCEL,
            "Delete", Gtk.ResponseType.ACCEPT,
        )
        dialog.get_widget_for_response(Gtk.ResponseType.ACCEPT).add_css_class("destructive-action")

        content = dialog.get_content_area()
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_margin_start(12)
        content.set_margin_end(12)
        label = Gtk.Label(label="This note has content and can't be recovered once deleted.")
        label.set_wrap(True)
        content.append(label)

        dialog.connect("response", self._on_delete_confirm_response)
        dialog.present()

    def _on_delete_confirm_response(self, dialog, response):
        dialog.destroy()
        if response == Gtk.ResponseType.ACCEPT:
            self._delete_note()

    def _delete_note(self):
        self._on_delete(self.note["id"])
        self.destroy()
