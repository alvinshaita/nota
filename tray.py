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
"""
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gio, GLib, Gtk

import dbus_common

ICON_NAME = "notes-app"


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


def call(proxy, method_name):
    try:
        proxy.call_sync(method_name, None, Gio.DBusCallFlags.NONE, -1, None)
    except GLib.Error as e:
        print(f"nota tray: D-Bus call {method_name} failed: {e}")


def on_activate(_icon, proxy):
    call(proxy, "LeftClickActivate")


def on_popup_menu(icon, button, activate_time, proxy):
    menu = Gtk.Menu()

    new_item = Gtk.MenuItem(label="New Note")
    new_item.connect("activate", lambda *_: call(proxy, "NewNote"))
    menu.append(new_item)

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
