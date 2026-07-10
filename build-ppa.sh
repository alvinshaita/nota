#!/usr/bin/env bash
# Builds a signed Debian source package for uploading to a Launchpad PPA.
#
# Prerequisites (one-time):
#   sudo apt install devscripts debhelper dput
#   a GPG key generated and registered with your Launchpad account
#
# Usage:
#   ./build-ppa.sh                              # build + sign only
#   ./build-ppa.sh --upload ppa:username/nota    # build, sign, and upload
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

debuild -S -sa

PKG="$(dpkg-parsechangelog -S Source)"
VER="$(dpkg-parsechangelog -S Version)"
CHANGES_FILE="$REPO_DIR/../${PKG}_${VER}_source.changes"

echo "Built $CHANGES_FILE"

if [ "${1:-}" = "--upload" ]; then
    PPA="${2:?Usage: ./build-ppa.sh --upload ppa:username/nota}"
    dput "$PPA" "$CHANGES_FILE"
else
    echo "Upload with: ./build-ppa.sh --upload ppa:<your-launchpad-username>/nota"
fi
