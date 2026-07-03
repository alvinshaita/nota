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
        self.set_default_size(420, 260)

        page = Adw.PreferencesPage()
        self.add(page)

        group = Adw.PreferencesGroup(title="Tray Icon")
        page.add(group)

        combo = Adw.ComboRow(title="Left-click action")
        model = Gtk.StringList()
        actions = settings_module.LEFT_CLICK_ACTIONS
        for action in actions:
            model.append(LEFT_CLICK_LABELS[action])
        combo.set_model(model)

        current = settings_module.load_settings().get("left_click_action", "toggle")
        combo.set_selected(actions.index(current) if current in actions else 0)
        combo.connect("notify::selected", self._on_left_click_changed, actions)
        group.add(combo)

    def _on_left_click_changed(self, combo, _param, actions):
        selected = actions[combo.get_selected()]
        current = settings_module.load_settings()
        current["left_click_action"] = selected
        settings_module.save_settings(current)
