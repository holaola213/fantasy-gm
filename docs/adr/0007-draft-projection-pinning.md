# ADR 0007: Draft Projection Pinning

- Status: Accepted
- Date: 2026-07-24

## Context

A draft can span multiple imports or activation changes. Recommendations for a
draft must remain tied to the projection assumptions that existed when the draft
was created.

## Decision

Drafts persist `projection_set_id`. A draft does not silently switch to newer
projections. Recommendations for that draft use the pinned snapshot.

## Consequences

Draft history is deterministic. Old drafts may intentionally use outdated data.
Explicit rebase or copy behavior may be added later.

## Alternatives Considered

- Always use the active projection set.
- Automatically upgrade drafts.
- Copy all projections into draft-specific rows.
