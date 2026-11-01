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

# --- Dependency check -------------------------------------------------------
# Everything comes from the distro's packages, python-xlib included: on
# Debian 12+ / Ubuntu 23.04+ the system Python is "externally managed"
# (PEP 668), so `pip install --user` refuses to run there.
missing_system_deps=()
python3 -c "import gi" 2>/dev/null || missing_system_deps+=("python3-gi")
python3 -c "import gi; gi.require_version('Gtk', '4.0'); from gi.repository import Gtk" \
    2>/dev/null || missing_system_deps+=("gir1.2-gtk-4.0")
python3 -c "import gi; gi.require_version('Gtk', '3.0'); from gi.repository import Gtk" \
    2>/dev/null || missing_system_deps+=("gir1.2-gtk-3.0")
python3 -c "import gi; gi.require_version('Adw', '1'); from gi.repository import Adw" \
    2>/dev/null || missing_system_deps+=("gir1.2-adw-1")
python3 -c "import Xlib" 2>/dev/null || missing_system_deps+=("python3-xlib")

if [ "${#missing_system_deps[@]}" -gt 0 ]; then
    echo "Missing system packages -- Nota won't start until they're installed:"
    printf '  %s\n' "${missing_system_deps[@]}"
    echo "On Debian/Ubuntu: sudo apt install ${missing_system_deps[*]}"
fi

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
#
# Exec= isn't run through a shell, so the path is double-quoted to survive
# spaces; it's also escaped for use as a sed replacement (& | \). The
# template's placeholder comments are dropped from the installed copy.
mkdir -p "$APPS_DIR"
rm -f "$APPS_DIR/nota.desktop"
exec_line="Exec=python3 \"$REPO_DIR/main.py\""
exec_line_sed="$(printf '%s' "$exec_line" | sed 's/[&|\\]/\\&/g')"
sed -e '/^#/d' -e "s|^Exec=.*|$exec_line_sed|" "$REPO_DIR/nota.desktop.example" \
    > "$APPS_DIR/nota.desktop"

if [ "${#missing_system_deps[@]}" -gt 0 ]; then
    echo "Done, but install the missing packages listed above before launching Nota."
else
    echo "Done. Nota should now appear in your application menu with its own icon."
fi
