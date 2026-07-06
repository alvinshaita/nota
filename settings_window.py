import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

import settings as settings_module

LEFT_CLICK_LABELS = {
    "toggle": "Show / hide all notes",
    "new_note": "Create a new note",
    "nothing": "Do nothing",
}


class SettingsWindow(Adw.Window):
    def __init__(self, app):
        super().__init__(application=app, title="Nota Settings")
        self.app = app
        self.set_default_size(420, 500)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(root)

        header = Gtk.HeaderBar()
        header.set_title_widget(Gtk.Label(label="Nota Settings"))
        root.append(header)

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.stack.set_vexpand(True)

        switcher = Gtk.StackSwitcher()
        switcher.set_stack(self.stack)
        switcher.set_halign(Gtk.Align.CENTER)
        switcher.set_margin_top(10)
        switcher.set_margin_bottom(6)
        root.append(switcher)

        root.append(self.stack)

        settings_now = settings_module.load_settings()

        tray_page = self._add_page("tray", "Tray")
        tray_group = Adw.PreferencesGroup(title="Tray Icon")
        tray_page.append(tray_group)

        combo = Adw.ComboRow(title="Left-click action")
        model = Gtk.StringList()
        actions = settings_module.LEFT_CLICK_ACTIONS
        for action in actions:
            model.append(LEFT_CLICK_LABELS[action])
        combo.set_model(model)

        current = settings_now.get("left_click_action", "toggle")
        combo.set_selected(actions.index(current) if current in actions else 0)
        combo.connect("notify::selected", self._on_left_click_changed, actions)
        tray_group.add(combo)

        appearance_page = self._add_page("appearance", "Appearance")

        appearance_group = Adw.PreferencesGroup(title="Appearance")
        appearance_page.append(appearance_group)

        font_combo = Adw.ComboRow(title="Note font")
        font_model = Gtk.StringList()
        fonts = list(settings_module.FONT_CHOICES.keys())
        for key in fonts:
            font_model.append(settings_module.FONT_LABELS[key])
        font_combo.set_model(font_model)

        current_font = settings_now.get("font_family", "system")
        font_combo.set_selected(fonts.index(current_font) if current_font in fonts else 0)
        font_combo.connect("notify::selected", self._on_font_changed, fonts)
        appearance_group.add(font_combo)

        self._add_spin_row(
            appearance_group, "Font size (0 = system default)",
            settings_now.get("font_size", 0),
            0, 72, 1, 0, "font_size", self.app.apply_font_size_setting,
        )

        new_note_group = Adw.PreferencesGroup(title="New Notes")
        appearance_page.append(new_note_group)

        self._add_spin_row(
            new_note_group, "Default width",
            settings_now.get("default_note_width", 260),
            100, 1000, 10, 0, "default_note_width", None,
        )
        self._add_spin_row(
            new_note_group, "Default height",
            settings_now.get("default_note_height", 260),
            100, 1000, 10, 0, "default_note_height", None,
        )

        layout_page = self._add_page("layout", "Text Layout")

        layout_group = Adw.PreferencesGroup(title="Text Layout")
        layout_page.append(layout_group)

        self._add_spin_row(
            layout_group, "Pixels above lines",
            settings_now.get("pixels_above_lines", 0),
            0, 50, 1, 0, "pixels_above_lines", self.app.apply_line_spacing_setting,
        )
        self._add_spin_row(
            layout_group, "Pixels inside wrap",
            settings_now.get("pixels_inside_wrap", 0),
            0, 50, 1, 0, "pixels_inside_wrap", self.app.apply_line_spacing_setting,
        )
        self._add_spin_row(
            layout_group, "Line height",
            settings_now.get("line_height", 1.0),
            1.0, 3.0, 0.1, 2, "line_height", self.app.apply_line_spacing_setting,
        )

        editing_group = Adw.PreferencesGroup(title="Editing")
        layout_page.append(editing_group)

        self._add_switch_row(
            editing_group, "Auto-convert \"- \" to bullet lists",
            settings_now.get("auto_bullet_lists", True),
            "auto_bullet_lists", self.app.apply_auto_bullet_setting,
        )

    def _add_page(self, name, title):
        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=18,
            margin_top=18, margin_bottom=18, margin_start=18, margin_end=18,
        )
        scroller = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        scroller.set_child(box)
        self.stack.add_titled(scroller, name, title)
        return box

    def _add_switch_row(self, group, title, value, key, apply_callback):
        row = Adw.ActionRow(title=title)
        switch = Gtk.Switch(active=value, valign=Gtk.Align.CENTER)
        switch.connect("notify::active", self._on_switch_changed, key, apply_callback)
        row.add_suffix(switch)
        row.set_activatable_widget(switch)
        group.add(row)
        return switch

    def _on_switch_changed(self, switch, _param, key, apply_callback):
        current = settings_module.load_settings()
        current[key] = switch.get_active()
        settings_module.save_settings(current)
        if apply_callback is not None:
            apply_callback()

    def _add_spin_row(self, group, title, value, lower, upper, step, digits, key, apply_callback):
        row = Adw.ActionRow(title=title)
        adjustment = Gtk.Adjustment(value=value, lower=lower, upper=upper, step_increment=step)
        spin = Gtk.SpinButton(adjustment=adjustment, digits=digits, valign=Gtk.Align.CENTER)
        spin.connect("value-changed", self._on_spin_changed, key, apply_callback)
        row.add_suffix(spin)
        row.set_activatable_widget(spin)
        group.add(row)
        return spin

    def _on_spin_changed(self, spin, key, apply_callback):
        current = settings_module.load_settings()
        value = spin.get_value_as_int() if spin.get_digits() == 0 else spin.get_value()
        current[key] = value
        settings_module.save_settings(current)
        if apply_callback is not None:
            apply_callback()

    def _on_left_click_changed(self, combo, _param, actions):
        selected = actions[combo.get_selected()]
        current = settings_module.load_settings()
        current["left_click_action"] = selected
        settings_module.save_settings(current)

    def _on_font_changed(self, combo, _param, fonts):
        selected = fonts[combo.get_selected()]
        current = settings_module.load_settings()
        current["font_family"] = selected
        settings_module.save_settings(current)
        self.app.apply_font_setting()
