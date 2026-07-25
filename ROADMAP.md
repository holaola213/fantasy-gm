# Fantasy GM Roadmap

Fantasy GM is moving from milestone-only development toward release-oriented
planning. Future release scopes are tentative unless marked complete.

## v0.1 - Core Recommendation Foundation

Status: Complete

- Milestone 0 - Local infrastructure with Docker Compose, PostgreSQL, FastAPI,
  React/Vite, Alembic, and health checks
- Milestone 1 - Players vertical slice
- Milestone 2 - Singleton ESPN-style league configuration
- Milestone 3 - Normalized player projections
- Milestone 5 - League-specific player valuation over replacement
- Milestone 8 - Deterministic recommendation engine groundwork

## v0.2 - Draft Foundation

Status: Complete

- Milestone 4 - Manual snake draft state, fantasy teams, draft picks, and draft
  lifecycle
- Milestone 6 - Draft Assistant MVP
- Milestone 7 - Next-pick context, availability outlook, positional scarcity,
  and value-drop awareness
- Milestone 9 - Draft Assistant UX polish

## v0.3 - Production Projection Pipeline

Status: In Progress

- Milestone 10 - Projection Provider Architecture
- Milestone 11 - Projection Import and Immutable Snapshots
- Milestone 12 - Production projection preview, diagnostics, importer
  documentation, and ADRs

## v0.4 - Explainable Recommendations

Status: Tentative

Possible scope:

- Recommendation explanations
- Confidence
- Decision factors
- Recommendation transparency

## v0.5 - Multi-Provider Intelligence

Status: Tentative

Possible scope:

- Multiple projection providers
- Provider comparisons
- Aggregated or consensus projections
- Cross-provider identity strategy

## v0.6 - League Integration

Status: Tentative

Possible scope:

- ESPN league configuration/import
- Roster and league synchronization
- League-specific draft setup

## v0.7 - Draft Analytics

Status: Tentative

Possible scope:

- Wait cost
- Positional scarcity
- Tier breaks
- Draft runs
- Post-draft analysis

## v1.0 - Public MVP

Status: Tentative

A complete, usable, explainable ESPN fantasy basketball draft decision-support
application.
