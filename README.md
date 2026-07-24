# Fantasy GM

Fantasy GM is a single-user fantasy basketball decision-support application.
Milestone 0 establishes the local development foundation only: PostgreSQL,
FastAPI, React/Vite, Alembic, environment examples, and a database-backed health
check.

Existing product and architecture documentation lives under `docs/` and
`research/`.

## Prerequisites

- Docker Desktop with Docker Compose
- Git

Local Node and Python installs are optional for Milestone 0 because the
documented workflow runs through Docker Compose.

## Environment

Copy the safe example file before starting the stack:

```powershell
Copy-Item .env.example .env
```

Real `.env` files are ignored by Git. Do not commit secrets.

Address types:

- Browser-facing frontend: `http://localhost:5173`
- Browser-facing backend: `http://localhost:8000`
- Swagger docs: `http://localhost:8000/docs`
- Docker-internal database hostname: `db`
- Docker-internal backend hostname for the Vite proxy: `backend`

## Start Locally

```powershell
docker compose up --build
```

Then open:

- Frontend: `http://localhost:5173`
- Backend health: `http://localhost:8000/health`
- FastAPI Swagger: `http://localhost:8000/docs`

The frontend calls `/api/health`. Vite proxies `/api` to the backend and strips
the `/api` prefix, so `/api/health` reaches FastAPI as `/health`.

## Expected Health Response

`GET /health` performs a real PostgreSQL query through SQLAlchemy:

```json
{
  "status": "ok",
  "database": "connected"
}
```

If PostgreSQL is unavailable, the API returns HTTP 503 with:

```json
{
  "detail": "database unavailable"
}
```

## Tests

Focused backend unit tests do not require a live PostgreSQL instance:

```powershell
docker compose run --rm backend pytest
```

## Migrations

Alembic is initialized and reads the database URL from the backend settings:

```powershell
docker compose run --rm backend alembic upgrade head
```

No fantasy domain tables are part of Milestone 0.
