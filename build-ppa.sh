#!/usr/bin/env bash
# Builds a signed Debian source package for uploading to a Launchpad PPA.
#
# The package is built from a clean `git archive` of HEAD, never from the
# working directory itself: a "3.0 (native)" source tarball packs everything
# in the directory it's built from, which would publish untracked local files
# (build output, .deb files, tool config, personal files). So commit
# everything you want to ship before running this.
#
# Prerequisites (one-time):
#   sudo apt install devscripts debhelper dput
#   a GPG key generated and registered with your Launchpad account
#
# Usage:
#   ./build-ppa.sh                              # build + sign only
#   ./build-ppa.sh --upload ppa:username/nota   # build, sign, and upload
#   ./build-ppa.sh --no-sign                    # unsigned build, for checking locally
#
# Output (.dsc, .tar.xz, _source.changes, ...) goes to build/ppa/.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

usage() {
    echo "Usage: ./build-ppa.sh [--upload ppa:username/nota | --no-sign]" >&2
}

PPA=""
SIGN_ARGS=()
while [ $# -gt 0 ]; do
    case "$1" in
        --upload)
            PPA="${2:-}"
            if [ -z "$PPA" ]; then usage; exit 1; fi
            shift 2
            ;;
        --no-sign) SIGN_ARGS=(-us -uc); shift ;;
        *) usage; exit 1 ;;
    esac
done

if [ -n "$PPA" ] && [ "${#SIGN_ARGS[@]}" -gt 0 ]; then
    echo "Launchpad only accepts signed uploads -- drop --no-sign to upload." >&2
    exit 1
fi

# --- Sanity checks --------------------------------------------------------
# The archive is built from HEAD, so uncommitted edits would silently be left
# out of the package. Mode-only differences (e.g. after copying the checkout
# between machines) are ignored: git archive uses the committed modes anyway.
if ! git -c core.fileMode=false diff --quiet HEAD --; then
    echo "Uncommitted changes to tracked files (they wouldn't be in the package)." >&2
    echo "Commit or stash them first:" >&2
    git -c core.fileMode=false status --short --untracked-files=no >&2
    exit 1
fi

if [ -n "$(git ls-files --others --exclude-standard)" ]; then
    echo "Note: these untracked files will NOT be in the package:"
    git ls-files --others --exclude-standard | sed 's/^/  /'
fi

PKG="$(dpkg-parsechangelog -S Source)"
VER="$(dpkg-parsechangelog -S Version)"
if [ "$VER" != "$(cat VERSION)" ]; then
    echo "Version mismatch: debian/changelog says $VER, VERSION says $(cat VERSION)." >&2
    echo "Bump both together (dch -v <version> updates the changelog)." >&2
    exit 1
fi

# --- Build ------------------------------------------------------------------
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

git -c tar.umask=0022 archive --format=tar --prefix="$PKG/" HEAD | tar -x -C "$WORK"
(cd "$WORK/$PKG" && debuild -S -sa ${SIGN_ARGS[@]+"${SIGN_ARGS[@]}"})

# debuild writes its output next to the source tree; keep it under build/.
OUT_DIR="$REPO_DIR/build/ppa"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR/${PKG}_${VER}"[._]*
find "$WORK" -maxdepth 1 -type f -name "${PKG}_${VER}[._]*" -exec cp {} "$OUT_DIR/" \;
CHANGES_FILE="$OUT_DIR/${PKG}_${VER}_source.changes"

echo "Built $CHANGES_FILE"

if [ -n "$PPA" ]; then
    dput "$PPA" "$CHANGES_FILE"
else
    echo "Upload with: ./build-ppa.sh --upload ppa:<your-launchpad-username>/nota"
fi
