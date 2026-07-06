#!/usr/bin/env bash
# Installs Nota for the current user: places the icon under the standard
# hicolor theme so it resolves on any system/theme, regenerates nota.desktop
# with the correct Exec path for wherever this repo actually lives, and
# symlinks that into the user's applications menu. Safe to re-run.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ICON_DIR="$HOME/.local/share/icons/hicolor"
APPS_DIR="$HOME/.local/share/applications"

echo "Installing Nota from $REPO_DIR"

# --- Python dependency check -------------------------------------------
missing_system_deps=()
python3 -c "import gi; gi.require_version('Gtk', '4.0'); from gi.repository import Gtk" \
    2>/dev/null || missing_system_deps+=("gir1.2-gtk-4.0")
python3 -c "import gi; gi.require_version('Gtk', '3.0'); from gi.repository import Gtk" \
    2>/dev/null || missing_system_deps+=("gir1.2-gtk-3.0")
python3 -c "import gi; gi.require_version('Adw', '1'); from gi.repository import Adw" \
    2>/dev/null || missing_system_deps+=("gir1.2-adw-1")

if [ "${#missing_system_deps[@]}" -gt 0 ]; then
    echo "Missing system packages (install with your package manager):"
    printf '  %s\n' "${missing_system_deps[@]}"
    echo "On Debian/Ubuntu: sudo apt install ${missing_system_deps[*]}"
fi

python3 -c "import Xlib" 2>/dev/null || {
    echo "Installing python-xlib for the current user..."
    pip3 install --user python-xlib
}

# --- Icon -----------------------------------------------------------------
for size in 16 24 32 48 256; do
    dest="$ICON_DIR/${size}x${size}/apps"
    mkdir -p "$dest"
    cp "$REPO_DIR/icons/nota-${size}.png" "$dest/nota.png"
done
command -v gtk-update-icon-cache >/dev/null 2>&1 && \
    gtk-update-icon-cache -f "$ICON_DIR" >/dev/null 2>&1 || true

# --- Desktop entry ----------------------------------------------------------
# (rm first: this path may currently be a symlink back into the repo from an
# earlier manual setup -- writing through it would clobber the repo's own
# nota.desktop instead of just the installed copy)
mkdir -p "$APPS_DIR"
rm -f "$APPS_DIR/nota.desktop"
sed "s|^Exec=.*|Exec=python3 $REPO_DIR/main.py|" "$REPO_DIR/nota.desktop.example" \
    > "$APPS_DIR/nota.desktop"

echo "Done. Nota should now appear in your application menu with its own icon."
