# ADR 0008: Active Projection Set Policy

- Status: Accepted
- Date: 2026-07-24

## Context

Fantasy GM needs a deterministic default projection set for draft creation while
preserving historical snapshots and allowing different sources, seasons, and
projection types to coexist.

## Decision

At most one active ProjectionSet exists per `(source_id, season,
projection_type)`.

Activation deactivates the prior active set in the same scope. It does not alter
other sources, seasons, or projection types. It does not mutate projection rows.
It does not change drafts already pinned to another set.

The database partial unique index
`uq_projection_sets_one_active_per_source_season_type` enforces the invariant.

## Consequences

Zero active sets are allowed for a scope. Draft creation can fail clearly when no
usable active set exists. Historical snapshots remain available even after
activation changes.

## Alternatives Considered

- Global single active projection set.
- Multiple active sets in the same scope.
- No persisted activation state.
