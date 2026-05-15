#!/usr/bin/env bash
# Download the arch_install project from GitHub.
# Usage: bash get.sh [destination]
# Default destination: ./arch_install

set -euo pipefail

REPO="https://github.com/m9aj/arch_install.git"
DEST="${1:-arch_install}"

if ! command -v git &>/dev/null; then
    echo "git not found — installing..."
    pacman -Sy --noconfirm git
fi

if [[ -d "$DEST/.git" ]]; then
    echo "Repo already exists at '$DEST', pulling latest..."
    git -C "$DEST" pull
else
    echo "Cloning $REPO → $DEST"
    git clone "$REPO" "$DEST"
fi

chmod +x "$DEST/arch-install"

echo ""
echo "Ready. To start Phase 1:"
echo "  cd $DEST && ./arch-install <profile>"
