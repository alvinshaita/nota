<p align="center">
  <img src="icons/nota-256.png" alt="Nota logo" width="128" height="128">
</p>

<h1 align="center">Nota</h1>

<p align="center">
  Simple GTK4/libadwaita sticky notes for the Linux desktop, with a tray icon
  for quick access.
</p>

---

## Requirements

- Python 3 with PyGObject
- GTK4, GTK3, and libadwaita GObject-introspection typelibs
- [`python-xlib`](https://pypi.org/project/python-xlib/)

On Debian/Ubuntu these are all distro packages (the `.deb` below pulls them
in automatically):

```bash
sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-gtk-3.0 gir1.2-adw-1 python3-xlib
```

## Install from a `.deb` (Debian/Ubuntu)

```bash
./build-deb.sh                              # produces nota_<version>_all.deb
sudo apt install ./nota_<version>_all.deb
```

Use `apt install ./<file>.deb` rather than `dpkg -i`: apt also installs the
dependencies listed above. Nota then appears in your application menu, and
`nota` is on your `PATH`.

## Install from a checkout

```bash
./install.sh
```

This is safe to re-run any time (e.g. after moving the repo). It:

- checks for the system packages above and prints the `apt install` command
  for any that are missing
- installs the app icon into `~/.local/share/icons/hicolor/*/apps/nota.png`
  (all standard sizes) so it shows up regardless of your system's icon theme
- generates `~/.local/share/applications/nota.desktop` with `Exec=` pointing
  at wherever this repo actually lives, so Nota shows up in your application
  menu

## Manual setup (without `install.sh`)

If you'd rather do it by hand, or just want to see what the installer does:

**1. Install the icon** (one copy per size, run from the repo root):

```bash
mkdir -p ~/.local/share/icons/hicolor/{16x16,24x24,32x32,48x48,256x256}/apps
cp icons/nota-16.png  ~/.local/share/icons/hicolor/16x16/apps/nota.png
cp icons/nota-24.png  ~/.local/share/icons/hicolor/24x24/apps/nota.png
cp icons/nota-32.png  ~/.local/share/icons/hicolor/32x32/apps/nota.png
cp icons/nota-48.png  ~/.local/share/icons/hicolor/48x48/apps/nota.png
cp icons/nota-256.png ~/.local/share/icons/hicolor/256x256/apps/nota.png
```

**2. Add the desktop entry** so it shows up in your application menu. Start
from the template and point its `Exec=` line at this checkout:

```bash
cp nota.desktop.example nota.desktop
# edit nota.desktop: Exec=python3 "/absolute/path/to/nota/main.py"
mkdir -p ~/.local/share/applications
cp nota.desktop ~/.local/share/applications/nota.desktop
```

A symlink works too instead of `cp`, and has the advantage of always
reflecting edits to the repo's copy of `nota.desktop` without re-copying:

```bash
ln -sf "$(pwd)/nota.desktop" ~/.local/share/applications/nota.desktop
```

Note that `nota.desktop`'s `Exec=` line needs a plain absolute path (Desktop
Entry files aren't run through a shell, so `~` and `$HOME` don't expand
there; keep the double quotes if the path contains spaces) — if you move the
repo, update that path to match, or just re-run `install.sh`, which
regenerates it automatically.

If the icon doesn't show up right away, try refreshing the icon cache:

```bash
gtk-update-icon-cache -f ~/.local/share/icons/hicolor
```

## Uninstall

- **`.deb`:** `sudo apt remove nota`
- **Checkout install:**

  ```bash
  rm -f ~/.local/share/applications/nota.desktop
  rm -f ~/.local/share/icons/hicolor/*/apps/nota.png
  ```

Nota also creates these per-user files, which neither of the above removes:

- `~/.config/autostart/nota.desktop` — the "start on login" entry (toggle it
  in Settings). After `apt remove` it's skipped automatically; for a checkout
  install, delete it or switch the setting off before removing.
- `~/.local/share/fonts/nota/` — the bundled Virgil font.
- `~/.local/share/nota/` and `~/.config/nota/` — your notes and settings.
  Only delete these if you don't want to keep your notes.

## Building packages

- `./build-deb.sh` builds the standalone `.deb` described above (needs only
  `dpkg-deb`).
- `./build-ppa.sh` builds a signed source package for a Launchpad PPA from the
  committed `HEAD` (commit first — uncommitted changes aren't included). Add
  `--upload ppa:<user>/nota` to upload, or `--no-sign` for a local test build.
  See the script header for prerequisites.
- Bump `VERSION` and `debian/changelog` together; both scripts refuse to
  build if they disagree.

## Development notes

Nota is a single-instance `GApplication` registered on D-Bus
(`com.github.nota`). If it's already running, launching `python3 main.py`
again won't start a new process or pick up code changes — it just
re-activates the existing instance. To restart after making changes:

```bash
# 1. Quit the running instance
gdbus call --session --dest com.github.nota --object-path /com/github/nota \
    --method com.github.nota.Notes.Quit

# 2. Confirm both processes actually exited
pgrep -af "main.py|tray.py"

# 3. Start fresh
python3 main.py
```

`main.py` also spawns a separate `tray.py` process (GTK3, for the legacy
tray icon protocol) — quitting the app via the method above cleanly stops
both.
