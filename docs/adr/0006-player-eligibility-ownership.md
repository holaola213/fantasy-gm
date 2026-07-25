# ADR 0006: Player Eligibility Ownership

- Status: Accepted
- Date: 2026-07-24

## Context

Player eligibility is used by the draft assistant and recommendations. The
current application needs a simple source of truth for current eligibility while
preserving immutable projection rows.

## Decision

Player eligibility is current mutable metadata. The latest successful resolved
import replaces that player's current eligibility set. Obsolete positions are
removed. New positions are added. Failed imports roll back eligibility changes.
Historical projection snapshots remain immutable.

## Consequences

Current recommendation logic sees latest eligibility. Historical projection rows
do not independently preserve eligibility. Historical eligibility snapshots may
require a future model if needed.

## Alternatives Considered

- Additive-only eligibility.
- Eligibility stored exclusively per projection.
- Manual-only eligibility management.
