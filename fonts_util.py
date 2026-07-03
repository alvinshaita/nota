"""Installs bundled custom fonts (e.g. the Excalidraw/Virgil hand-drawn font)
so Pango can find them by family name.

GTK4's CSS engine has no @font-face at-rule, and app-scoped runtime loading
via fontconfig's FcConfigAppFontAddFile didn't render correctly in testing
(the family resolved via fc-match but glyphs fell back to a system font).
Installing to the user's standard fonts directory and refreshing the
fontconfig cache is the approach that actually works.
"""
import shutil
import subprocess
from pathlib import Path

BUNDLED_FONTS_DIR = Path(__file__).resolve().parent / "fonts"
INSTALL_DIR = Path.home() / ".local" / "share" / "fonts" / "nota"


def ensure_installed():
    if not BUNDLED_FONTS_DIR.is_dir():
        return
    installed_any = False
    for font_file in BUNDLED_FONTS_DIR.glob("*.ttf"):
        dest = INSTALL_DIR / font_file.name
        if dest.exists() and dest.stat().st_mtime >= font_file.stat().st_mtime:
            continue
        INSTALL_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(font_file, dest)
        installed_any = True
    if installed_any:
        try:
            subprocess.run(["fc-cache", "-f", str(INSTALL_DIR)], capture_output=True, timeout=10)
        except (OSError, subprocess.SubprocessError):
            pass
