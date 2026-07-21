# Agora Upgrade Patch

This repository includes one upgrade path for both manual production upgrades and governance-triggered deployments. It preserves the PostgreSQL volume and the administrator-managed AI provider settings stored in Agora.

## Run the upgrade

From the production checkout:

```bash
bash scripts/upgrade.sh
```

The helper performs these steps in order:

1. Acquires a local upgrade lock so two upgrades cannot run concurrently.
2. Creates a PostgreSQL custom-format backup in `.agora-backups/` when the database is already running.
3. Runs `git pull --ff-only`; local divergence or merge conflicts stop the upgrade.
4. Builds the new backend and frontend images without replacing running application services.
5. Starts PostgreSQL and Redis if necessary and waits for PostgreSQL readiness.
6. Runs `alembic upgrade head` in a one-shot container before application replacement.
7. Runs `docker compose up --detach --remove-orphans` without deleting named volumes.
8. Checks the backend, frontend, and nginx from inside their containers.

The existing `deploy.sh` launches its detached deployment container and delegates to this same helper. No second deployment path or migration order is maintained.

## Preflight only

```bash
DEPLOY_DRY_RUN=1 bash scripts/upgrade.sh
```

This checks Git, Docker, Compose, and the resolved Compose configuration without pulling, building, migrating, or recreating services.

## Controlled overrides

- `DEPLOY_SKIP_PULL=1`: use the current checkout, useful for local package verification.
- `DEPLOY_SKIP_BACKUP=1`: skip the backup only when an operator has already created and verified one.
- `AGORA_BACKUP_DIR=/secure/path`: store backups outside the checkout.
- `COMPOSE_PROJECT_NAME=agora`: select the existing Compose project explicitly.

## Failure handling

- A backup failure stops before pulling or changing services.
- A build or migration failure stops before application service replacement.
- A failed health check leaves the backup path in the logs for operator recovery.
- The helper never runs `docker compose down`, `down -v`, or removes the `pgdata` volume.
- Database downgrades are not attempted automatically. Restore the recorded backup only after diagnosing the failed release and confirming the intended schema version.

Administrator AI provider settings remain in PostgreSQL and take priority over environment variables. The upgrade helper neither reads nor prints saved API keys.
