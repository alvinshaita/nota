#!/usr/bin/env python3
"""Standalone GTK3 tray icon process.

Runs separately from the main app because GtkStatusIcon (GTK3, the legacy
XEmbed tray protocol) cannot be loaded in the same process as GTK4 -- gi only
allows one version of a given namespace per process. It talks to the main
app over the D-Bus service the app exports (see dbus_common.py).

GtkStatusIcon is deprecated upstream but is what gives us real distinct
left-click ("activate") vs right-click ("popup-menu") signals, matching how
xpad's tray icon behaves; the modern AppIndicator/StatusNotifierItem stack
routes single clicks of any button through the shell's own menu instead.

The right-click menu lists groups and their notes read straight from
notes.json (storage.py has no GTK dependency, so it's safe to import here
even though this process runs GTK3 rather than the main app's GTK4).
"""
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gio, GLib, Gtk

import dbus_common
import settings as settings_module
import storage

ICON_NAME = "nota"


def get_proxy():
    return Gio.DBusProxy.new_for_bus_sync(
        Gio.BusType.SESSION,
        Gio.DBusProxyFlags.NONE,
        None,
        dbus_common.BUS_NAME,
        dbus_common.OBJECT_PATH,
        dbus_common.INTERFACE_NAME,
        None,
    )


def call(proxy, method_name, arg=None):
    try:
        variant = GLib.Variant("(s)", (arg,)) if arg is not None else None
        proxy.call_sync(method_name, variant, Gio.DBusCallFlags.NONE, -1, None)
    except GLib.Error as e:
        print(f"nota tray: D-Bus call {method_name} failed: {e}")


def on_activate(icon, proxy):
    action = settings_module.load_settings().get("left_click_action")
    if action == "menu":
        # Same menu as a right-click. The menu lives in this process, so open
        # it here rather than round-tripping through the app.
        on_popup_menu(icon, 1, Gtk.get_current_event_time(), proxy)
    else:
        call(proxy, "LeftClickActivate")


def _add_note_items(menu, notes, proxy, open_ids):
    for note in notes:
        item = Gtk.CheckMenuItem(label=storage.note_title(note))
        item.set_active(note["id"] in open_ids)
        item.connect("toggled", lambda _w, nid=note["id"]: call(proxy, "ToggleNote", nid))
        menu.append(item)


def on_popup_menu(icon, button, activate_time, proxy):
    notes = storage.active_notes(storage.load_notes())
    groups, ungrouped = storage.groups_and_notes(notes)
    saved_open_ids = settings_module.load_settings().get("open_note_ids")
    open_ids = set(saved_open_ids) if saved_open_ids is not None else {n["id"] for n in notes}

    menu = Gtk.Menu()

    new_item = Gtk.MenuItem(label="New Note")
    new_item.connect("activate", lambda *_: call(proxy, "NewNote"))
    menu.append(new_item)

    menu.append(Gtk.SeparatorMenuItem())

    all_item = Gtk.MenuItem(label="All Notes")
    all_item.connect("activate", lambda *_: call(proxy, "OpenAllNotes"))
    menu.append(all_item)

    close_all_item = Gtk.MenuItem(label="Close All Notes")
    close_all_item.connect("activate", lambda *_: call(proxy, "CloseAllNotes"))
    menu.append(close_all_item)

    if groups or ungrouped:
        menu.append(Gtk.SeparatorMenuItem())

    for group_name, group_notes in groups.items():
        group_item = Gtk.MenuItem(label=group_name)
        submenu = Gtk.Menu()

        open_only_item = Gtk.MenuItem(label=f"Open only “{group_name}”")
        open_only_item.connect("activate", lambda _w, g=group_name: call(proxy, "OpenGroupOnly", g))
        submenu.append(open_only_item)

        open_add_item = Gtk.MenuItem(label=f"Open all in “{group_name}”")
        open_add_item.connect("activate", lambda _w, g=group_name: call(proxy, "OpenGroup", g))
        submenu.append(open_add_item)

        submenu.append(Gtk.SeparatorMenuItem())
        _add_note_items(submenu, group_notes, proxy, open_ids)

        submenu.show_all()
        group_item.set_submenu(submenu)
        menu.append(group_item)

    if ungrouped:
        ungrouped_item = Gtk.MenuItem()
        ungrouped_label = Gtk.Label(label="ungrouped")
        ungrouped_label.set_markup("<i>ungrouped</i>")
        ungrouped_label.set_xalign(0)
        ungrouped_item.add(ungrouped_label)
        ungrouped_submenu = Gtk.Menu()
        _add_note_items(ungrouped_submenu, ungrouped, proxy, open_ids)
        ungrouped_submenu.show_all()
        ungrouped_item.set_submenu(ungrouped_submenu)
        menu.append(ungrouped_item)

    menu.append(Gtk.SeparatorMenuItem())

    manage_item = Gtk.MenuItem(label="Manage Notes…")
    manage_item.connect("activate", lambda *_: call(proxy, "ShowNoteManager"))
    menu.append(manage_item)

    settings_item = Gtk.MenuItem(label="Settings")
    settings_item.connect("activate", lambda *_: call(proxy, "ShowSettings"))
    menu.append(settings_item)

    menu.append(Gtk.SeparatorMenuItem())

    quit_item = Gtk.MenuItem(label="Quit")
    quit_item.connect("activate", lambda *_: call(proxy, "Quit"))
    menu.append(quit_item)

    menu.show_all()
    menu.popup(None, None, Gtk.StatusIcon.position_menu, icon, button, activate_time)


def main():
    proxy = get_proxy()
    icon = Gtk.StatusIcon.new_from_icon_name(ICON_NAME)
    icon.set_tooltip_text("Nota")
    icon.connect("activate", on_activate, proxy)
    icon.connect("popup-menu", on_popup_menu, proxy)
    Gtk.main()


if __name__ == "__main__":
    main()
