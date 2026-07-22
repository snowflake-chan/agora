#!/bin/bash
# Idempotent production upgrade helper shared by manual and automatic deploys.

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="${REPO_DIR:-$(cd "$SCRIPT_DIR/.." && pwd)}"
default_project_name="$(basename "$REPO_DIR" | tr '[:upper:]' '[:lower:]')"
COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-$default_project_name}"
BACKUP_DIR="${AGORA_BACKUP_DIR:-$REPO_DIR/.agora-backups}"
LOCK_DIR="${AGORA_UPGRADE_LOCK_DIR:-$REPO_DIR/.agora-upgrade.lock}"
BACKUP_FILE=""

log() {
    printf '[upgrade] %s\n' "$*"
}

fail() {
    log "ERROR: $*"
    if [ -n "$BACKUP_FILE" ] && [ -f "$BACKUP_FILE" ]; then
        log "Database backup retained at $BACKUP_FILE"
    fi
    exit 1
}

cleanup() {
    rmdir "$LOCK_DIR" 2>/dev/null || true
}
trap cleanup EXIT

command -v git >/dev/null || fail "git is not installed"
command -v docker >/dev/null || fail "docker is not installed"

if docker compose version >/dev/null 2>&1; then
    compose=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
    compose=(docker-compose)
else
    fail "Docker Compose is not installed"
fi

compose_cmd() {
    "${compose[@]}" \
        --project-name "$COMPOSE_PROJECT_NAME" \
        --project-directory "$REPO_DIR" \
        "$@"
}

[ -d "$REPO_DIR/.git" ] || fail "$REPO_DIR is not a Git checkout"
[ -f "$REPO_DIR/docker-compose.yml" ] || fail "docker-compose.yml is missing"

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
    fail "another upgrade is already running ($LOCK_DIR exists)"
fi

git config --global --add safe.directory "$REPO_DIR"
cd "$REPO_DIR"

if [ "${DEPLOY_DRY_RUN:-0}" = "1" ]; then
    compose_cmd config --quiet
    log "Dry run completed; Git, Docker, Compose, and configuration are ready"
    exit 0
fi

if [ "${DEPLOY_SKIP_BACKUP:-0}" != "1" ]; then
    postgres_id="$(compose_cmd ps --status running --quiet postgres 2>/dev/null || true)"
    if [ -n "$postgres_id" ]; then
        mkdir -p "$BACKUP_DIR"
        chmod 700 "$BACKUP_DIR"
        timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
        BACKUP_FILE="$BACKUP_DIR/agora-$timestamp.dump"
        temporary_backup="$BACKUP_FILE.partial"
        log "Creating PostgreSQL backup"
        if ! compose_cmd exec -T postgres sh -c \
            'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --no-owner --no-acl' \
            >"$temporary_backup"; then
            rm -f "$temporary_backup"
            fail "database backup failed; upgrade was not started"
        fi
        chmod 600 "$temporary_backup"
        mv "$temporary_backup" "$BACKUP_FILE"
        log "Backup completed: $BACKUP_FILE"
    else
        log "PostgreSQL is not running; treating this as a fresh installation"
    fi
else
    log "Skipping database backup because DEPLOY_SKIP_BACKUP=1"
fi

if [ "${DEPLOY_SKIP_PULL:-0}" = "1" ]; then
    log "Skipping git pull"
else
    log "Pulling latest code with fast-forward only"
    git pull --ff-only || fail "git pull was not a fast-forward"
fi

log "Building updated images"
compose_cmd build || fail "image build failed; existing services were not replaced"

log "Ensuring PostgreSQL and Redis are running"
compose_cmd up --detach postgres redis || fail "database services failed to start"

database_ready=0
for _attempt in $(seq 1 30); do
    if compose_cmd exec -T postgres sh -c \
        'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"' >/dev/null 2>&1; then
        database_ready=1
        break
    fi
    sleep 2
done
[ "$database_ready" = "1" ] || fail "PostgreSQL did not become ready"

log "Applying Alembic migrations before service replacement"
compose_cmd run --rm --no-deps backend alembic upgrade head \
    || fail "database migration failed; existing application services remain available"

log "Recreating application services without removing persistent volumes"
compose_cmd up --detach --remove-orphans || fail "service recreation failed"

health_check() {
    service="$1"
    shift
    for _attempt in $(seq 1 30); do
        if compose_cmd exec -T "$service" "$@" >/dev/null 2>&1; then
            return 0
        fi
        sleep 2
    done
    return 1
}

log "Checking backend, frontend, and nginx"
health_check backend python -c \
    'import urllib.request; urllib.request.urlopen("http://127.0.0.1:8000/docs", timeout=5)' \
    || fail "backend health check failed"
health_check frontend node -e \
    'fetch("http://127.0.0.1:4321/").then(r=>{if(!r.ok)process.exit(1)}).catch(()=>process.exit(1))' \
    || fail "frontend health check failed"
health_check nginx wget -qO- http://127.0.0.1/ \
    || fail "nginx health check failed"

log "Upgrade completed successfully"
if [ -n "$BACKUP_FILE" ]; then
    log "Rollback backup: $BACKUP_FILE"
fi
