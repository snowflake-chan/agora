#!/bin/bash
# Auto-deploy: pull latest code and rebuild containers
# Called by the backend after a successful PR merge vote.
#
# NOTE: The last command (docker compose up -d --build) replaces this
# container, so this script never reaches the final echo. That's OK
# because Docker daemon continues the operation after we're killed.

set -e

REPO_DIR="${REPO_DIR:-/repo}"

# Git safety — the repo is mounted from the host, owned by a different UID
git config --global safe.directory "$REPO_DIR"

cd "$REPO_DIR"

echo "[deploy] Pulling latest from git..."
git pull

echo "[deploy] Rebuilding and restarting containers... (self-destruct imminent)"

# This kills this container — but Docker daemon finishes the job
docker compose up -d --build

# Never reached
echo "[deploy] Done."
