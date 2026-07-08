"""Manages Nota's entry in the XDG autostart directory (~/.config/autostart),
which desktop environments launch automatically after login -- separate from
the app-menu .desktop file in ~/.local/share/applications."""
from pathlib import Path

AUTOSTART_DIR = Path.home() / ".config" / "autostart"
AUTOSTART_FILE = AUTOSTART_DIR / "nota.desktop"

REPO_DIR = Path(__file__).resolve().parent

DESKTOP_ENTRY = f"""[Desktop Entry]
Type=Application
Name=Nota
Comment=Simple sticky notes for the desktop
Exec=python3 {REPO_DIR}/main.py --autostart
Icon=nota
Terminal=false
X-GNOME-Autostart-enabled=true
"""


def sync(enabled):
    """Makes the autostart file match `enabled`. Safe to call on every
    startup -- a no-op if it already matches."""
    if enabled:
        AUTOSTART_DIR.mkdir(parents=True, exist_ok=True)
        if not AUTOSTART_FILE.exists() or AUTOSTART_FILE.read_text() != DESKTOP_ENTRY:
            AUTOSTART_FILE.write_text(DESKTOP_ENTRY)
    else:
        AUTOSTART_FILE.unlink(missing_ok=True)
