#!/usr/bin/env bash
# Builds a .deb package for Nota. Run from the repo root:
#   ./build-deb.sh
# Produces nota_<version>_all.deb in the repo root. Requires dpkg-deb
# (present by default on Debian/Ubuntu).
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG_NAME="nota"
VERSION="$(cat "$REPO_DIR/VERSION")"
BUILD_ROOT="$REPO_DIR/build/deb"
STAGING="$BUILD_ROOT/${PKG_NAME}_${VERSION}_all"

echo "Building ${PKG_NAME} ${VERSION}..."

rm -rf "$STAGING"
mkdir -p "$STAGING/DEBIAN"
mkdir -p "$STAGING/usr/bin"
mkdir -p "$STAGING/usr/lib/nota"
mkdir -p "$STAGING/usr/share/applications"
mkdir -p "$STAGING/usr/share/doc/nota"
for size in 16 24 32 48 256; do
    mkdir -p "$STAGING/usr/share/icons/hicolor/${size}x${size}/apps"
done

# --- App source -------------------------------------------------------
cp "$REPO_DIR"/*.py "$STAGING/usr/lib/nota/"
cp -r "$REPO_DIR/fonts" "$STAGING/usr/lib/nota/fonts"
rm -f "$STAGING/usr/lib/nota/fonts/VIRGIL-LICENSE.md"

# --- Launcher on PATH ------------------------------------------------------
cat > "$STAGING/usr/bin/nota" <<'LAUNCHER'
#!/bin/sh
exec python3 /usr/lib/nota/main.py "$@"
LAUNCHER
chmod 755 "$STAGING/usr/bin/nota"

# --- Desktop entry + icons -------------------------------------------------
cp "$REPO_DIR/packaging/deb/nota.desktop" "$STAGING/usr/share/applications/nota.desktop"
for size in 16 24 32 48 256; do
    cp "$REPO_DIR/icons/nota-${size}.png" \
       "$STAGING/usr/share/icons/hicolor/${size}x${size}/apps/nota.png"
done

# --- Docs -------------------------------------------------------------
cp "$REPO_DIR/packaging/deb/copyright" "$STAGING/usr/share/doc/nota/copyright"
cp "$REPO_DIR/fonts/VIRGIL-LICENSE.md" "$STAGING/usr/share/doc/nota/VIRGIL-LICENSE.md"

# --- Control files ----------------------------------------------------
sed "s/__VERSION__/$VERSION/" "$REPO_DIR/packaging/deb/control.template" \
    > "$STAGING/DEBIAN/control"
cp "$REPO_DIR/packaging/deb/postinst" "$STAGING/DEBIAN/postinst"
cp "$REPO_DIR/packaging/deb/postrm" "$STAGING/DEBIAN/postrm"
chmod 755 "$STAGING/DEBIAN/postinst" "$STAGING/DEBIAN/postrm"

# --- Build --------------------------------------------------------------
OUT="$REPO_DIR/${PKG_NAME}_${VERSION}_all.deb"
dpkg-deb --build --root-owner-group "$STAGING" "$OUT"
echo "Built $OUT"
