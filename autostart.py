"""Manages Nota's entry in the XDG autostart directory (~/.config/autostart),
which desktop environments launch automatically after login -- separate from
the app-menu .desktop file in ~/.local/share/applications."""
from pathlib import Path

AUTOSTART_DIR = Path.home() / ".config" / "autostart"
AUTOSTART_FILE = AUTOSTART_DIR / "nota.desktop"

APP_DIR = Path(__file__).resolve().parent

# Where the .deb (build-deb.sh / debian/rules) puts the app and its launcher.
PACKAGED_APP_DIR = Path("/usr/lib/nota")
PACKAGED_LAUNCHER = Path("/usr/bin/nota")

if APP_DIR == PACKAGED_APP_DIR:
    # This per-user file outlives `apt remove nota`. TryExec makes the session
    # skip the entry once the launcher is gone, rather than failing on every
    # login.
    EXEC_LINES = f"TryExec={PACKAGED_LAUNCHER}\nExec={PACKAGED_LAUNCHER} --autostart"
else:
    # Running from a checkout. Exec= isn't run through a shell, so the path is
    # quoted in case it contains spaces.
    EXEC_LINES = f'Exec=python3 "{APP_DIR / "main.py"}" --autostart'

DESKTOP_ENTRY = f"""[Desktop Entry]
Type=Application
Name=Nota
Comment=Simple sticky notes for the desktop
{EXEC_LINES}
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
