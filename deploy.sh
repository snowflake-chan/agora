#!/bin/bash
# Auto-deploy after an approved governance PR is merged.
#
# The backend container must not run Compose directly: Compose is a client-side
# orchestrator and would be killed midway through recreating its own container.
# The first invocation therefore launches a detached helper container, which is
# outside the Compose project and survives the backend restart.

set -Eeuo pipefail

REPO_DIR="${REPO_DIR:-/repo}"
DEPLOY_LOCK_NAME="${DEPLOY_LOCK_NAME:-agora-deploy}"

log() {
    printf '[deploy] %s\n' "$*"
}

if [ "${DEPLOY_HELPER:-0}" != "1" ]; then
    command -v docker >/dev/null || {
        log "ERROR: docker CLI is not installed in the backend image"
        exit 1
    }

    container_id="${HOSTNAME:-}"
    [ -n "$container_id" ] || {
        log "ERROR: cannot determine the current container ID"
        exit 1
    }

    host_repo_dir="$(docker inspect \
        --format '{{range .Mounts}}{{if eq .Destination "/repo"}}{{.Source}}{{end}}{{end}}' \
        "$container_id")"
    compose_project="$(docker inspect \
        --format '{{index .Config.Labels "com.docker.compose.project"}}' \
        "$container_id")"
    backend_image="$(docker inspect --format '{{.Config.Image}}' "$container_id")"

    [ -n "$host_repo_dir" ] || {
        log "ERROR: could not resolve the host repository mount"
        exit 1
    }
    [ -n "$compose_project" ] || {
        log "ERROR: could not resolve the Compose project name"
        exit 1
    }

    # A fixed name is an inexpensive deployment lock. If a deployment is
    # already running, docker run fails instead of racing another git pull.
    log "Launching deployment helper for project $compose_project"
    helper_mode=(--detach --rm)
    if [ "${DEPLOY_KEEP_HELPER:-0}" = "1" ]; then
        helper_mode=(--detach)
    fi
    if [ "${DEPLOY_DRY_RUN:-0}" = "1" ]; then
        # Foreground mode lets CI/operators see the helper's prerequisite
        # checks without changing the repository or Compose project.
        helper_mode=(--rm)
    fi
    docker run "${helper_mode[@]}" \
        --name "$DEPLOY_LOCK_NAME" \
        --label "com.agora.deploy.project=$compose_project" \
        --volume /var/run/docker.sock:/var/run/docker.sock \
        --volume "$host_repo_dir:/repo" \
        --env DEPLOY_HELPER=1 \
        --env REPO_DIR=/repo \
        --env HOST_REPO_DIR="$host_repo_dir" \
        --env COMPOSE_PROJECT_NAME="$compose_project" \
        --env DEPLOY_DRY_RUN="${DEPLOY_DRY_RUN:-0}" \
        --env DEPLOY_SKIP_PULL="${DEPLOY_SKIP_PULL:-0}" \
        --env DEPLOY_KEEP_HELPER="${DEPLOY_KEEP_HELPER:-0}" \
        "$backend_image" \
        /bin/bash /repo/deploy.sh
    exit 0
fi

command -v git >/dev/null || {
    log "ERROR: git is not installed in the deployment helper"
    exit 1
}

if docker compose version >/dev/null 2>&1; then
    compose=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
    compose=(docker-compose)
else
    log "ERROR: Docker Compose is not installed in the deployment helper"
    exit 1
fi

if [ "${DEPLOY_DRY_RUN:-0}" = "1" ]; then
    log "Dry run completed; Git and Compose are available"
    exit 0
fi

git config --global --add safe.directory "$REPO_DIR"
cd "$REPO_DIR"

if [ "${DEPLOY_SKIP_PULL:-0}" = "1" ]; then
    log "Skipping git pull for local deployment verification"
else
    log "Pulling the latest code with fast-forward only"
    git pull --ff-only
fi

log "Building updated service images"
"${compose[@]}" \
    --project-name "$COMPOSE_PROJECT_NAME" \
    --project-directory "$REPO_DIR" \
    build

log "Recreating the Compose project"
"${compose[@]}" \
    --project-name "$COMPOSE_PROJECT_NAME" \
    --project-directory "$REPO_DIR" \
    up --detach --remove-orphans

log "Deployment completed"
