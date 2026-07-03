"""Best-effort window position persistence via raw X11.

GTK4 removed portable window-positioning APIs (no set_position, no reliable
get_position) because Wayland doesn't let clients know or control their
absolute screen position. On X11 we can still do it by talking to the X
server directly through python-xlib. This is a no-op under Wayland.

Positioning has to happen *after* the window is mapped: the window manager's
own initial-placement policy overrides any position set before/at map time,
but honors a plain move request once the window is already on screen.
"""
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("GdkX11", "4.0")
from gi.repository import Gdk, GdkX11, GLib

_xlib_display = None
_is_x11 = None


def is_x11():
    global _is_x11
    if _is_x11 is None:
        _is_x11 = isinstance(Gdk.Display.get_default(), GdkX11.X11Display)
    return _is_x11


def _get_xlib_display():
    global _xlib_display
    if _xlib_display is None:
        from Xlib import display as xlib_display

        _xlib_display = xlib_display.Display()
    return _xlib_display


def _get_xlib_window(gtk_window):
    surface = gtk_window.get_surface()
    if surface is None:
        return None
    return _get_xlib_display().create_resource_object("window", surface.get_xid())


def get_position(gtk_window):
    if not is_x11():
        return None
    try:
        xwin = _get_xlib_window(gtk_window)
        if xwin is None:
            return None
        root = _get_xlib_display().screen().root
        reply = root.translate_coords(xwin, 0, 0)
        return reply.x, reply.y
    except Exception:
        return None


def move_window(gtk_window, x, y):
    if not is_x11():
        return

    def _do_move():
        try:
            xwin = _get_xlib_window(gtk_window)
            if xwin is not None:
                xwin.configure(x=x, y=y)
                _get_xlib_display().sync()
        except Exception:
            pass
        return GLib.SOURCE_REMOVE

    GLib.idle_add(_do_move)


class _PositionTracker:
    """Watches ConfigureNotify events for registered windows and reports
    live position changes, so a drag is saved the moment it happens instead
    of only at checkpoints like close/hide."""

    def __init__(self):
        self._callbacks = {}
        self._io_watch_id = None

    def watch(self, gtk_window, on_move):
        if not is_x11():
            return
        xwin = _get_xlib_window(gtk_window)
        if xwin is None:
            return
        from Xlib import X

        xwin.change_attributes(event_mask=X.StructureNotifyMask)
        _get_xlib_display().sync()
        self._callbacks[xwin.id] = on_move
        self._ensure_watching()

    def unwatch(self, gtk_window):
        xwin = _get_xlib_window(gtk_window)
        if xwin is not None:
            self._callbacks.pop(xwin.id, None)

    def _ensure_watching(self):
        if self._io_watch_id is not None:
            return
        fd = _get_xlib_display().fileno()
        self._io_watch_id = GLib.io_add_watch(fd, GLib.IO_IN, self._on_io)

    def _on_io(self, _source, _condition):
        from Xlib import X

        disp = _get_xlib_display()
        while disp.pending_events():
            ev = disp.next_event()
            if ev.type == X.ConfigureNotify:
                callback = self._callbacks.get(ev.window.id)
                if callback is not None:
                    root = disp.screen().root
                    reply = root.translate_coords(ev.window, 0, 0)
                    callback(reply.x, reply.y)
        return GLib.SOURCE_CONTINUE


_tracker = _PositionTracker()


def watch_position(gtk_window, on_move):
    """on_move(x, y) is called whenever gtk_window's absolute screen
    position changes, e.g. from the user dragging it."""
    _tracker.watch(gtk_window, on_move)


def unwatch_position(gtk_window):
    _tracker.unwatch(gtk_window)
