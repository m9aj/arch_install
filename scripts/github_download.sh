#!/usr/bin/env bash
set -euo pipefail

REPO="https://github.com/m9aj/arch_install.git"

usage() {
    cat <<EOF
Download the arch_install project from GitHub.

Usage:
  bash github_download.sh [destination] [branch]

Arguments:
  destination   Local directory to clone into (default: arch_install)
  branch        Git branch to checkout (default: main)

Examples:
  bash github_download.sh                        # clone main → ./arch_install
  bash github_download.sh arch_install dev       # clone dev branch
  bash github_download.sh ~/my_install dev       # custom destination + branch
EOF
}

case "${1:-}" in
    help|--help|-h)
        usage
        exit 0
        ;;
esac

DEST="${1:-arch_install}"
BRANCH="${2:-main}"

if ! command -v git &>/dev/null; then
    echo "git not found — installing..."
    pacman -Sy --noconfirm git
fi

if [[ -d "$DEST/.git" ]]; then
    echo "Repo already exists at '$DEST', pulling latest..."
    git -C "$DEST" fetch origin
    git -C "$DEST" checkout "$BRANCH"
    git -C "$DEST" pull origin "$BRANCH"
else
    echo "Cloning $REPO ($BRANCH) → $DEST"
    git clone -b "$BRANCH" "$REPO" "$DEST"
fi

chmod +x "$DEST/arch-install"

# Change ownership of the downloaded folder to ajay:users
# (Works in the Arch install environment too where user 'ajay' does not exist yet)
TARGET_USER="1000"
if id "ajay" &>/dev/null; then
    TARGET_USER="ajay"
fi

TARGET_GROUP=""
if getent group users &>/dev/null; then
    TARGET_GROUP="users"
fi

if [ -n "$TARGET_GROUP" ]; then
    chown -R "$TARGET_USER:$TARGET_GROUP" "$DEST" 2>/dev/null || sudo chown -R "$TARGET_USER:$TARGET_GROUP" "$DEST" 2>/dev/null || true
else
    chown -R "$TARGET_USER" "$DEST" 2>/dev/null || sudo chown -R "$TARGET_USER" "$DEST" 2>/dev/null || true
fi

echo ""
echo "Ready. To start Phase 1:"
echo "  cd $DEST && ./arch-install <profile>"
