# Fantasy GM

Fantasy GM is a single-user fantasy basketball decision-support application.
Milestone 0 established the local development foundation: PostgreSQL, FastAPI,
React/Vite, Alembic, environment examples, and a database-backed health check.
Milestone 1 adds the Players vertical slice with a deterministic local fixture
dataset.
Milestone 2 adds the singleton League Configuration slice for local ESPN points
league settings.
Milestone 3 adds normalized season player projections and league-scored
projection display.

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

Backend tests use PostgreSQL through Docker Compose:

```powershell
docker compose run --rm backend pytest
```

## Migrations

Alembic is initialized and reads the database URL from the backend settings:

```powershell
docker compose run --rm backend alembic upgrade head
```

## Seed Local Players

The player seed command inserts or updates deterministic local development
fixtures. Fixture IDs are not NBA or ESPN identifiers.

```powershell
docker compose run --rm backend python -m app.players.seed
```

The seed is idempotent and does not delete unrelated player rows.

## Seed Local League

The league seed command inserts or updates the singleton local development
league configuration, scoring rules, and roster slots. Fixture keys and IDs are
local development data and are not ESPN identifiers.

```powershell
docker compose run --rm backend python -m app.leagues.seed
```

The seed is idempotent and does not delete unrelated scoring-rule or roster-slot
rows.

## Seed Local Projections

The projections seed command inserts or updates one deterministic manual local
development projection source and one manual season projection set. Fixture
values are local development data. Future real imports should create new
immutable projection sets rather than updating historical imported sets.

Run the player and league seeds before projection scoring:

```powershell
docker compose run --rm backend python -m app.players.seed
docker compose run --rm backend python -m app.leagues.seed
docker compose run --rm backend python -m app.projections.seed
```

The projection seed is idempotent and does not delete unrelated projection
sources, projection sets, or projection rows.

## Players API

List players:

```powershell
Invoke-RestMethod "http://localhost:8000/players"
```

Search and filter players:

```powershell
Invoke-RestMethod "http://localhost:8000/players?search=jokic&team=DEN&position=C&active=true"
```

The list response includes matching `total` before pagination:

```json
{
  "items": [],
  "total": 0,
  "limit": 50,
  "offset": 0
}
```

## League API

Get the singleton league configuration:

```powershell
Invoke-RestMethod "http://localhost:8000/league"
```

If no league is configured, the API returns HTTP 404:

```json
{
  "detail": "league configuration not found"
}
```

Save the singleton league configuration:

```powershell
Invoke-RestMethod "http://localhost:8000/league" -Method Put -ContentType "application/json" -Body $json
```

`PUT /league` replaces the singleton league, scoring rules, and roster slots in
one database transaction. The frontend exposes this through the League Settings
view at `http://localhost:5173`.

## Projections API

List projection sources and sets:

```powershell
Invoke-RestMethod "http://localhost:8000/projection-sources"
Invoke-RestMethod "http://localhost:8000/projection-sets"
```

Get one projection set:

```powershell
Invoke-RestMethod "http://localhost:8000/projection-sets/1"
```

List projected players scored with the current singleton league configuration:

```powershell
Invoke-RestMethod "http://localhost:8000/projection-sets/1/players?sort=projected_fantasy_points&direction=desc"
```

Supported player-projection filters are `search`, `team`, `position`, `limit`,
`offset`, `sort`, and `direction`. Public sort keys include
`minutes_per_game`, `fantasy_points_per_game`, and
`projected_fantasy_points`.

If the singleton league configuration is missing, projected-player scoring
returns HTTP 409:

```json
{
  "detail": "league configuration required"
}
```

## Projection Scoring Note

Fantasy points are derived from the current singleton league scoring rules, not
stored on projection rows. Projection sorting by `fantasy_points_per_game` or
`projected_fantasy_points` currently calculates the matching rows in the
application and sorts them in memory. That is intentional and acceptable for the
current NBA-scale dataset. A larger future version may move this to
database-side optimization or precomputed valuation data.

The projection scoring logic should stay local to the projections feature until
a second feature, such as replacement-level valuation or roster analysis, needs
the same calculation.
