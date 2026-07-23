# ADR 0001: Use React with TypeScript and Vite

## Status

Accepted

## Context

Fantasy GM Version 1 is a private, highly interactive draft-intelligence dashboard for one expert user.

The application will have a dedicated FastAPI backend responsible for business logic, integrations, persistence, and recommendation generation.

The frontend does not currently require search-engine optimization, server-side rendering, public content pages, or frontend-owned backend routes.

## Decision

Use React with TypeScript and Vite for the Fantasy GM frontend.

The frontend will be a client-side application that communicates with the FastAPI backend through a versioned REST API.

## Alternatives Considered

### Next.js

Next.js provides full-stack React capabilities, server rendering, routing, and server-side application features.

It was not selected because Fantasy GM already has a dedicated FastAPI backend, and the Version 1 product does not require server-side rendering or public search-indexed pages. Using Next.js would introduce overlapping server responsibilities without a clear current benefit.

### Plain JavaScript

Plain JavaScript was not selected because TypeScript provides stronger contracts for API responses, player data, draft state, and recommendation explanations.

## Consequences

### Positive

- Clear frontend/backend separation
- Small and understandable frontend architecture
- Fast local development
- Strong TypeScript support
- Easy static production builds
- No duplicated backend layer

### Negative

- Routing and server-state libraries must be selected separately
- Server-side rendering is not included
- A future public website may require a separate application or architectural reconsideration

## Revisit When

Reconsider this decision if Fantasy GM later requires:

- Significant public and search-indexed content
- Server-side rendered application pages
- A TypeScript-owned backend
- A unified public website and application architecture
