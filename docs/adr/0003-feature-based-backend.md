# ADR 0003: Organize the Backend by Business Features

## Status

Accepted

## Context

Fantasy GM is centered around business capabilities such as drafting,
recommendations, players, projections, leagues, and evaluations.

As the application grows, organizing code by technical layers alone
(models, services, repositories, etc.) would scatter each feature across
multiple directories, making navigation and maintenance more difficult.

## Decision

Organize the backend by business features (vertical slices).

Each feature owns its API routes, business logic, schemas, repositories,
and tests where appropriate.

Shared infrastructure will live in a dedicated `shared` module.

## Proposed Structure

```text
backend/
├── app/
│   ├── draft/
│   ├── players/
│   ├── projections/
│   ├── recommendations/
│   ├── leagues/
│   ├── evaluations/
│   ├── shared/
│   │   ├── config/
│   │   ├── database/
│   │   ├── exceptions/
│   │   ├── logging/
│   │   └── utils/
│   └── main.py
├── alembic/
├── tests/
├── pyproject.toml
└── Dockerfile
```

## Alternatives Considered

### Layered Architecture

```
api/
services/
repositories/
models/
schemas/
```

This approach is familiar and works well for smaller projects, but it
spreads a single feature across multiple directories and makes feature
development less cohesive.

## Consequences

### Positive

- Code is organized around the business domain.
- Easier to navigate and extend.
- Recommendation Engine remains self-contained.
- Strong alignment with the architecture and product documents.
- Easier onboarding for future contributors.

### Negative

- Some patterns are less familiar to developers accustomed to traditional
  layered architectures.
- Shared utilities must be managed carefully to avoid duplication.

## Revisit When

Reconsider this decision if Fantasy GM evolves into multiple independent
services with clearly separated deployment boundaries.
