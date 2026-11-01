#!/usr/bin/env python3
import os
import sys

# Nota's tray icon (Gtk.StatusIcon / XEmbed) and its window positioning and
# stacking (x11_utils) are X11-only, and silently do nothing under a native
# Wayland backend -- leaving Nota running with no tray icon and nothing on
# screen. Wayland sessions ship XWayland, so run as an X11 client there too.
# This must happen before GTK is imported; tray.py inherits it via the
# environment. setdefault keeps an explicit GDK_BACKEND from the user.
os.environ.setdefault("GDK_BACKEND", "x11")

from app import NotaApplication  # noqa: E402 (must follow the GDK_BACKEND setup)


def main():
    launched_via_autostart = "--autostart" in sys.argv
    argv = [a for a in sys.argv if a != "--autostart"]
    app = NotaApplication(launched_via_autostart=launched_via_autostart)
    return app.run(argv)


if __name__ == "__main__":
    sys.exit(main())
