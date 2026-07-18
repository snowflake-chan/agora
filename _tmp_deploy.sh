#!/bin/bash
# Auto-deploy: pull latest code and rebuild containers
# Called by the backend after a successful PR merge vote.

set -e

REPO_DIR="${REPO_DIR:-/repo}"
cd "$REPO_DIR"

echo "[deploy] Pulling latest from git..."
git pull

echo "[deploy] Rebuilding and restarting containers..."
docker compose up -d --build

echo "[deploy] Done."
