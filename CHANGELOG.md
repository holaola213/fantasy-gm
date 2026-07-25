# Changelog

## [Unreleased]

Use this section for work completed after the latest release boundary.

## [0.3.0] - In Progress

### Added

- Projection provider abstraction for normalized provider output.
- Immutable projection snapshots with persisted `ProjectionSet` and
  `PlayerProjection` rows.
- Provider-local player identity through `(source_id, source_player_id)`.
- Projection import activation scoped to source, season, and projection type.
- Projection import preview/dry-run planning.
- Structured projection import diagnostics.
- Projection import result summaries with player, identity, eligibility, and
  projection-row counts.
- Projection import documentation and example CSV.
- Projection pipeline ADRs.

### Changed

- CSV imports now support UTF-8 with BOM, reordered columns, quoted values,
  blank lines, trimmed headers and values, and warning diagnostics for unknown
  extra columns.
- Projection import preview and persistence share database-dependent planning
  logic.

### Documentation

- README now presents Fantasy GM as versioned software with v0.3-dev status and
  a projection pipeline diagram.
- ROADMAP now groups milestones into release-oriented tracks.

## [0.2.0]

### Added

- Manual snake draft lifecycle, fantasy teams, draft picks, and persisted draft
  state.
- Draft Assistant MVP with user roster summary and available-player context.
- Draft intelligence signals for next user pick, availability outlook,
  positional scarcity, and value-drop awareness.
- Draft recommendation UI polish.

## [0.1.0]

### Added

- Local Docker Compose development stack.
- PostgreSQL-backed FastAPI health endpoint.
- React/Vite frontend.
- Alembic migrations.
- Players vertical slice.
- Singleton league configuration.
- Normalized player projections.
- League-specific player valuation over replacement.
- Deterministic recommendation foundation.
