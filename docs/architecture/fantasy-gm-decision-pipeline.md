# Fantasy GM — Decision Pipeline

**Phase:** -1  
**Status:** Draft for review

## Purpose

Define how raw information becomes a recommendation.

The pipeline is intentionally one-way. Each stage has a single responsibility and
produces outputs consumed by the next stage.

---

# Guiding Principles

1. Every stage has one responsibility.
2. Outputs are immutable once published.
3. Later stages never modify earlier stages.
4. Every output records provenance and model versions.
5. Every recommendation must be reproducible.

---

# High-Level Pipeline

```text
External Sources
      │
      ▼
Ingestion
      │
      ▼
Normalization
      │
      ▼
Historical Storage
      │
      ▼
Feature Engineering
      │
      ▼
Projection
      │
      ▼
Confidence
      │
      ▼
Risk
      │
      ▼
Valuation
      │
      ▼
Decision
      │
      ▼
Recommendation
      │
      ▼
Explanation
      │
      ▼
Evaluation
```

---

# Stage Contracts

## 1. Ingestion

Consumes:
- APIs
- News
- League data

Produces:
- Raw source records

Never:
- Cleans
- Predicts
- Deduplicates

---

## 2. Normalization

Consumes raw records.

Produces canonical Fantasy GM records.

Responsibilities:

- identity resolution
- unit normalization
- schema validation
- source attribution

Never:

- forecasts
- recommendations

---

## 3. Historical Storage

Persists append-only history.

Responsibilities:

- preserve observations
- preserve corrections
- preserve timestamps

Never:

- compute "current" state by mutation

---

## 4. Feature Engineering

Transforms historical facts into model inputs.

Examples:

- rolling averages
- usage trends
- pace
- schedule density
- injury-derived features

Produces:

Feature Set

---

## 5. Projection Engine

Consumes Feature Set.

Produces:

Fantasy GM Projection

Only answers:

> "What is likely to happen?"

Never:

- draft
- add
- trade
- rank

---

## 6. Confidence Engine

Evaluates projection reliability.

Signals may include:

- missing data
- model agreement
- injury uncertainty
- role stability

Produces:

Confidence Assessment

---

## 7. Risk Engine

Evaluates downside.

Examples:

- injury
- minutes volatility
- suspension
- role instability

Produces:

Risk Assessment

Confidence != Risk.

---

## 8. Valuation Engine

The first stage aware of league context.

Consumes:

- projection
- confidence
- risk
- scoring rules
- replacement level
- roster scarcity

Produces:

Player Valuation

Answers:

> "How valuable is this player here?"

---

## 9. Decision Engine

Consumes:

- valuations
- decision context
- available alternatives

Produces:

Decision

Answers:

> "What should the manager do?"

It never recalculates projections.

---

## 10. Recommendation Builder

Turns decisions into user-facing recommendations.

Includes:

- chosen action
- confidence
- alternatives
- expiration
- supporting evidence

---

## 11. Explanation Builder

Explains *why*.

Sources:

- evidence
- market differences
- schedule
- scarcity
- uncertainty

No new analysis occurs here.

---

## 12. Evaluation Engine

Runs after outcomes occur.

Measures:

- projection accuracy
- calibration
- decision quality
- regret
- benchmark comparison

Evaluation never alters historical recommendations.

---

# Information Flow Rules

Only forward movement is allowed.

```text
Facts
 ↓
Features
 ↓
Forecasts
 ↓
Values
 ↓
Decisions
 ↓
Recommendations
 ↓
Evaluations
```

No stage may depend on outputs from a later stage.

---

# Inputs by Stage

| Stage | Primary Inputs |
|--------|----------------|
| Ingestion | External APIs |
| Normalization | Raw records |
| Feature Engineering | Historical facts |
| Projection | Feature Set |
| Confidence | Projection + feature quality |
| Risk | Projection + uncertainty signals |
| Valuation | Projection + confidence + risk + league |
| Decision | Valuation + context + alternatives |
| Recommendation | Decision |
| Explanation | Recommendation evidence |
| Evaluation | Outcomes |

---

# Anti-Patterns

Do NOT:

- let the Decision Engine edit projections
- let the Projection Engine know waiver rules
- let the Market layer calculate player value
- overwrite historical outputs
- embed explanations inside prediction logic

---

# Benchmarks

Evaluation should compare against:

- ESPN rankings
- ADP
- Highest projected player
- Simple heuristic strategies
- Previous Fantasy GM versions

Success is measured by **decision quality**, not projection error alone.

---

# Candidate ADRs

1. Pipeline stages have one responsibility.
2. Data flows only forward.
3. Valuation is separate from Projection.
4. Recommendation is separate from Valuation.
5. Evaluation never mutates historical artifacts.

---

# Completion Criteria

The pipeline is complete when:

- every stage has one owner
- every stage has explicit inputs and outputs
- stage boundaries are respected
- recommendations are reproducible
- evaluations can be run without future information
