# ADR 0005: Provider-Local Player Identity

- Status: Accepted
- Date: 2026-07-24

## Context

Projection providers use their own player identifiers, and Fantasy GM does not
yet implement canonical cross-provider identity resolution.

## Decision

`(source_id, source_player_id)` is the authoritative provider identity.

`source_player_id` is trimmed, case-sensitive, opaque, and provider-local. No
canonical cross-provider identity resolution is implemented yet.

Exact-name fallback is a constrained bootstrap mechanism:

- Zero matches may create a player.
- Exactly one match may reuse a player.
- Multiple matches fail.

## Consequences

Multiple providers may identify the same real player with different local IDs.
Future canonical identity work can layer on top of provider-local identity
without changing immutable projection snapshots.

## Alternatives Considered

- Globally unique `source_player_id`.
- Case-insensitive provider IDs.
- Fuzzy name matching.
- Immediate canonical identity service.
