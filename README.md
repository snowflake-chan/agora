# Agora

Agora is a full-stack social platform where conversation, discovery, and product change happen in public. Posts, replies, Guild discussions, and GitHub-backed change proposals share one feed; proposals move through discussion, voting, tallying, and (when enabled) deployment.

## Stack

- **Frontend:** Astro SSR, Svelte 5, TypeScript, pnpm
- **Backend:** FastAPI, SQLAlchemy 2, Alembic, Uvicorn
- **Data:** PostgreSQL and Redis
- **Operations:** Docker Compose and Nginx

## Run locally

Copy the example configuration, review every value, and start the complete stack:

```powershell
Copy-Item .env.example .env
docker compose up --build -d
docker compose ps
```

The default port is `http://localhost:8080`. The maintained local test profile may set `AGORA_HTTP_PORT=8082` in `.env`.

```powershell
docker compose logs -f backend frontend nginx
docker compose down
```

Do not commit `.env` or reuse production credentials locally.

## Development

Frontend development requires Node.js `>=22.12.0`:

```powershell
Set-Location frontend
pnpm install
pnpm astro dev --background
pnpm test
pnpm build
```

Backend development requires Python 3.12, PostgreSQL, and Redis:

```powershell
Set-Location backend
python -m pip install -r requirements-dev.txt
alembic upgrade head
python -m pytest tests/ -v --tb=short
```

## Product surfaces

- **Feed:** For you, Trending, Following, and Latest views with SSE updates.
- **Conversation:** Posts, replies, likes, shares, follows, notifications, and revision history.
- **Guilds:** Membership, roles, discussions, and Guild-scoped proposals.
- **Governance:** Draft → voting → passed/rejected → merged/failed. Votes are `for`, `against`, or `abstain`; approval requires a strict majority of all votes.
- **AI tools:** Contextual summaries, translations, poll assistance, writing assistance, semantic political-content review, caching, quotas, and output-only safety handling.
- **Public feeds:** RSS 2.0 and JSON Feed 1.1 endpoints under `/api/v1/public/`.

## Repository map

```text
frontend/             Astro pages, Svelte components, stores, i18n, API helpers
backend/app/          FastAPI routers, models, services, and background jobs
backend/tests/        Backend and governance regression tests
backend/alembic/      Retry-safe database migrations
docker-compose.yml    Local and production service topology
deploy.sh             Production deployment helper
```

## Contribution rules

Start from the latest `main`, create one focused `codex/<topic>` branch, and open a pull request targeting `main`. Include the user-visible result, risks, and verification. Production changes must also pass Agora's proposal and voting flow; do not bypass governance or alter vote results manually.

New interface copy must be supplied in English, Japanese, and Traditional Chinese. Database changes require an Alembic migration, not only an ORM edit. Preserve SSE behavior, responsive layouts, empty/error states, and the existing default visual language.

## License

No license has been declared yet. Treat the repository as all-rights-reserved until one is added.
