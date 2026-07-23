# ADR 0002: Use PostgreSQL with SQLAlchemy and Alembic

## Status

Accepted

## Context

Fantasy GM Version 1 stores draft history, recommendation history, league settings,
player projections, temporal records, and evaluation data.

The application is designed around reproducible recommendations and historical
analysis rather than simple CRUD operations.

## Decision

Use PostgreSQL as the primary database.

Use SQLAlchemy 2.x as the ORM.

Use Alembic for all schema migrations.

The database schema is treated as source code and all structural changes must be
implemented through version-controlled migrations.

## Alternatives Considered

### SQLite

SQLite offers a very simple setup and is excellent for prototypes.

It was not selected because Fantasy GM relies on richer relational queries,
temporal history, future analytical workloads, and long-term maintainability.
The additional operational overhead of PostgreSQL is minimal when using Docker.

## Consequences

### Positive

- Industry-standard relational database
- Excellent SQL capabilities
- Strong indexing and query optimization
- Supports future analytical features
- Reliable migration workflow
- Better long-term scalability

### Negative

- Requires a database server (managed locally through Docker Compose)
- Slightly more initial setup than SQLite

## Revisit When

Reconsider this decision if Fantasy GM becomes an offline-only desktop
application with no need for advanced querying or historical analysis.
