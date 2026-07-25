# Architecture Decision Records

Architecture Decision Records document important technical and product
architecture decisions for Fantasy GM.

Accepted ADRs should not be silently rewritten when a decision changes. Future
changes should generally add a new ADR that supersedes or amends the earlier
decision, preserving the historical reasoning.

## Current ADRs

- [0001: Use React with TypeScript and Vite](0001-use-react-with-vite.md)
- [0002: Use PostgreSQL with SQLAlchemy and Alembic](0002-use-postgresql.md)
- [0003: Organize the Backend by Business Features](0003-feature-based-backend.md)
- [0004: Immutable Projection Snapshots](0004-immutable-projection-snapshots.md)
- [0005: Provider-Local Player Identity](0005-provider-local-player-identity.md)
- [0006: Player Eligibility Ownership](0006-player-eligibility-ownership.md)
- [0007: Draft Projection Pinning](0007-draft-projection-pinning.md)
- [0008: Active Projection Set Policy](0008-active-projection-set-policy.md)

Foundation ADRs and projection-pipeline ADRs are both part of the project
history.
