# ADR 0004: Immutable Projection Snapshots

- Status: Accepted
- Date: 2026-07-24

## Context

Fantasy GM recommendations and drafts need to remain reproducible after newer
projection imports arrive. Reusing mutable projection rows would make historical
draft decisions difficult to explain.

## Decision

ProjectionSet records represent immutable import snapshots. PlayerProjection
rows are never overwritten by later imports. Re-importing creates another
ProjectionSet. Historical recommendations and drafts must remain reproducible.

## Consequences

Storage usage increases because each successful import persists a new snapshot.
Correction imports create new snapshots rather than editing old ones. Historical
analysis is possible. Cleanup and retention policy may be considered later.

## Alternatives Considered

- Overwrite latest projections.
- Use one mutable projection table.
- Store source files without normalized snapshots.
