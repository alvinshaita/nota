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


def get_xid(gtk_window):
    surface = gtk_window.get_surface()
    if surface is None:
        return None
    return surface.get_xid()


def get_stacking_order(xids):
    """Returns the given xids reordered to match their actual current
    on-screen stacking, bottom to top (last = topmost). xids not currently
    mapped are dropped. None if unavailable (e.g. non-EWMH WM, Wayland)."""
    if not is_x11():
        return None
    try:
        from Xlib import X

        disp = _get_xlib_display()
        root = disp.screen().root
        atom = disp.intern_atom("_NET_CLIENT_LIST_STACKING")
        prop = root.get_full_property(atom, X.AnyPropertyType)
        if prop is None:
            return None
        xid_set = set(xids)
        return [xid for xid in prop.value if xid in xid_set]
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


def raise_window(gtk_window):
    """Force gtk_window to the top of the X11 stack via a raw ConfigureWindow
    restack, bypassing GTK's present()/gdk_toplevel_focus() -- mutter's
    focus-stealing prevention silently ignores present() calls that don't
    originate from direct user input, which a plain restack isn't subject to."""
    if not is_x11():
        return
    try:
        from Xlib import X

        xwin = _get_xlib_window(gtk_window)
        if xwin is not None:
            xwin.configure(stack_mode=X.Above)
            _get_xlib_display().sync()
    except Exception:
        pass


class _EventRouter:
    """Watches X11 events relevant to note windows and dispatches them:

    - ConfigureNotify per window -> live position changes (dragging).
    - PropertyNotify on root for _NET_CLIENT_LIST_STACKING -> raise/lower
      (which window is on top of which).

    Both share one X connection and one GLib io watch on its socket.
    """

    def __init__(self):
        self._position_callbacks = {}
        self._stacking_callback = None
        self._io_watch_id = None
        self._stacking_atom = None

    def watch_position(self, gtk_window, on_move):
        if not is_x11():
            return
        xwin = _get_xlib_window(gtk_window)
        if xwin is None:
            return
        from Xlib import X

        xwin.change_attributes(event_mask=X.StructureNotifyMask)
        _get_xlib_display().sync()
        self._position_callbacks[xwin.id] = on_move
        self._ensure_watching()

    def unwatch_position(self, gtk_window):
        xwin = _get_xlib_window(gtk_window)
        if xwin is not None:
            self._position_callbacks.pop(xwin.id, None)

    def watch_stacking_order(self, on_change):
        if not is_x11():
            return
        from Xlib import X

        disp = _get_xlib_display()
        root = disp.screen().root
        root.change_attributes(event_mask=X.PropertyChangeMask)
        disp.sync()
        self._stacking_atom = disp.intern_atom("_NET_CLIENT_LIST_STACKING")
        self._stacking_callback = on_change
        self._ensure_watching()

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
                callback = self._position_callbacks.get(ev.window.id)
                if callback is not None:
                    root = disp.screen().root
                    reply = root.translate_coords(ev.window, 0, 0)
                    callback(reply.x, reply.y)
            elif ev.type == X.PropertyNotify and ev.atom == self._stacking_atom:
                if self._stacking_callback is not None:
                    self._stacking_callback()
        return GLib.SOURCE_CONTINUE


_router = _EventRouter()


def watch_position(gtk_window, on_move):
    """on_move(x, y) is called whenever gtk_window's absolute screen
    position changes, e.g. from the user dragging it."""
    _router.watch_position(gtk_window, on_move)


def unwatch_position(gtk_window):
    _router.unwatch_position(gtk_window)


def watch_stacking_order(on_change):
    """on_change() is called whenever any window's stacking (raise/lower)
    changes anywhere on the desktop; call get_stacking_order() to read it."""
    _router.watch_stacking_order(on_change)
