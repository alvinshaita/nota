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


class SettingsWindow(Adw.PreferencesWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Nota Settings")
        self.app = app
        self.set_default_size(420, 300)

        page = Adw.PreferencesPage()
        self.add(page)

        tray_group = Adw.PreferencesGroup(title="Tray Icon")
        page.add(tray_group)

        combo = Adw.ComboRow(title="Left-click action")
        model = Gtk.StringList()
        actions = settings_module.LEFT_CLICK_ACTIONS
        for action in actions:
            model.append(LEFT_CLICK_LABELS[action])
        combo.set_model(model)

        current = settings_module.load_settings().get("left_click_action", "toggle")
        combo.set_selected(actions.index(current) if current in actions else 0)
        combo.connect("notify::selected", self._on_left_click_changed, actions)
        tray_group.add(combo)

        appearance_group = Adw.PreferencesGroup(title="Appearance")
        page.add(appearance_group)

        font_combo = Adw.ComboRow(title="Note font")
        font_model = Gtk.StringList()
        fonts = list(settings_module.FONT_CHOICES.keys())
        for key in fonts:
            font_model.append(settings_module.FONT_LABELS[key])
        font_combo.set_model(font_model)

        current_font = settings_module.load_settings().get("font_family", "system")
        font_combo.set_selected(fonts.index(current_font) if current_font in fonts else 0)
        font_combo.connect("notify::selected", self._on_font_changed, fonts)
        appearance_group.add(font_combo)

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
