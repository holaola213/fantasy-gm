# Fantasy GM — Ubiquitous Language

**Phase:** -1
**Status:** Living Document

## Purpose

Every important term in Fantasy GM has one agreed meaning.

If two developers use the same word, they should mean the same thing.
If two concepts are different, they should have different names.

This document is the project's dictionary.

---

# Core Principles

1. One concept → one name.
2. One name → one meaning.
3. Avoid overloaded words.
4. Prefer explicit names over short names.
5. Business language drives code, documentation, and APIs.

---

# Canonical Terms

## Player

Definition:
A real NBA player. Represents stable identity.

Not:
- Projection
- Fantasy roster spot
- Market asset

Examples:
- Nikola Jokić
- Victor Wembanyama

---

## NBA Team

A real NBA franchise.

Never use:
- Team (when Fantasy Team is intended)

---

## Fantasy Team

A manager-controlled roster inside a Fantasy League Season.

Never call this simply "Team" in documentation.

---

## Fantasy League

The persistent league itself.

Example:
"12-Team ESPN Points League"

---

## Fantasy League Season

One season of a Fantasy League.

Rules belong here, not the League.

---

## Game

One NBA game.

Never means a fantasy matchup.

---

## Matchup

One fantasy scoring contest between Fantasy Teams.

---

## Player Game Performance

Observed statistics from one NBA game.

Fact, not prediction.

---

## Projection

Forecast of future performance over a defined horizon.

Must always identify:
- target period
- scoring system
- model version

Not:
- Value
- Recommendation
- Ranking

---

## External Projection

Projection published by another source.

Never confused with Fantasy GM Projection.

---

## Fantasy GM Projection

Forecast produced by Fantasy GM.

---

## Confidence

Trust in a prediction or recommendation.

Not:
- upside
- probability of success
- risk

---

## Risk

Potential downside or uncertainty.

Not:
- confidence

---

## Valuation

Context-specific estimate of player worth.

Depends on:
- projections
- league rules
- scarcity
- replacement level
- risk

Not:
- projection
- recommendation
- trade offer

---

## Recommendation

Suggested action.

Examples:
- Draft
- Hold
- Add
- Drop
- Trade
- Start

Not:
- ranking
- valuation

---

## Explanation

Evidence supporting a recommendation.

No new calculations occur here.

---

## Evaluation

Retrospective measurement of projection or recommendation quality.

Never influences historical outputs.

---

## Feature Set

Structured analytical inputs to a model.

Not:
- raw source data

---

## Model Version

Immutable version of an analytical model.

Must uniquely identify every generated projection.

---

## Decision Context

Everything required to make a recommendation.

Examples:
- roster
- available players
- waiver priority
- scoring rules
- playoff horizon

---

## Alternative

A viable action that was not selected.

---

## Source Observation

Exactly what an external source reported.

Not:
- canonical truth

---

## Market Snapshot

Fantasy GM's consolidated market view at a moment in time.

Derived from Source Observations.

---

## Snapshot Run

One ingestion session collecting observations.

---

## Information Cutoff

Latest permissible input time for an analytical output.

Critical for backtesting.

---

## Historical Record

Append-only record of facts or observations.

Never silently overwritten.

---

## Current State

Derived representation of the latest historical records.

Not canonical storage.

---

# Words We Avoid

| Avoid | Use Instead |
|-------|-------------|
| Team | NBA Team / Fantasy Team |
| Value | Valuation / Trade Value / Projected Fantasy Points |
| Rank | ESPN Rank / ADP / Fantasy GM Rank |
| Prediction | Projection |
| Stats | Player Game Performance / Historical Statistics |
| Model | Model Version / Projection Model |
| Current | Current State |
| History | Historical Record |

---

# Naming Guidelines

Prefer:

- projected_fantasy_points
- replacement_adjusted_value
- confidence_score
- injury_risk
- fantasy_team
- nba_team
- market_snapshot

Avoid:

- value
- score
- team
- rank
- data
- info
- model

---

# Cross-Document Consistency

These definitions govern:

- ADRs
- Architecture
- Database schema
- APIs
- Code
- Tests
- Documentation

If a term changes meaning, update this document first.

---

# Candidate Glossary Additions

Future terms:

- Replacement Level
- Opportunity Cost
- Scarcity
- Calibration
- Regret
- Expected Value
- Decision Quality
- Benchmark
- Draft Capital
- Trade Package
- Streaming Opportunity
- Playoff Value
- Rest-of-Season Horizon
- Weekly Horizon
- Schedule Density

---

# Rule

If a concept requires the sentence:

"It depends what you mean..."

it probably needs two different terms.
