# Fantasy GM — Business Capabilities

**Phase:** -1
**Status:** Draft

## Purpose

Business Capabilities describe what Fantasy GM can do, independent of any
technology, programming language, database, model, or API.

Capabilities are long-lived. Services, models, and implementations may change.

---

# Architectural Principle

Fantasy GM is **one intelligent analyst**, not a collection of unrelated tools.

Trade analysis, waiver analysis, draft analysis, lineup advice, and streaming
recommendations are different decision contexts handled by the same analytical
brain.

---

# Capability Map

Fantasy GM
├── Basketball Intelligence
├── Market Intelligence
├── League Intelligence
├── Player Intelligence
├── Decision Intelligence
└── Evaluation Intelligence

---

## 1. Basketball Intelligence

Mission:
Understand the real NBA.

Owns:
- Games
- Teams
- Schedules
- Player performances
- Injuries
- Rotations
- Historical basketball facts

Does NOT own:
- Fantasy scoring
- Trades
- Recommendations

Outputs:
Reliable basketball facts.

---

## 2. Market Intelligence

Mission:
Understand what the fantasy market believes.

Owns:
- ESPN rankings
- ADP
- Ownership
- Availability
- News observations
- Public projections

Does NOT decide whether the market is correct.

Outputs:
Market observations and trends.

---

## 3. League Intelligence

Mission:
Understand the user's fantasy environment.

Owns:
- League rules
- Scoring
- Rosters
- Waivers
- Transactions
- Matchups
- Playoff settings

Outputs:
League context.

---

## 4. Player Intelligence

Mission:
Build Fantasy GM's opinion of every player.

Consumes:
- Basketball Intelligence
- Market Intelligence
- League Intelligence

Produces:
- Fantasy GM Projection
- Confidence
- Risk
- Valuation

Player Intelligence never recommends actions.

---

## 5. Decision Intelligence

Mission:
Help the manager make the best available decision.

Consumes:
- Player Intelligence
- League Intelligence
- Decision Context

Produces:
- Recommendations
- Alternatives
- Explanations

Decision Types:
- Draft
- Trade
- Waiver
- Add / Drop
- Start / Sit
- Streaming
- Playoff Planning
- Keeper / Dynasty (future)

Decision Intelligence never changes projections.

---

## 6. Evaluation Intelligence

Mission:
Measure whether Fantasy GM is improving.

Owns:
- Backtesting
- Calibration
- Benchmark comparisons
- Regret analysis
- Recommendation success
- Model comparisons

Produces:
Actionable feedback for improving the system.

Evaluation never rewrites history.

---

# Capability Relationships

Basketball + Market + League
            │
            ▼
    Player Intelligence
            │
            ▼
   Decision Intelligence
            │
            ▼
 Evaluation Intelligence

---

# Capability Boundaries

Basketball Intelligence
- knows basketball
- knows nothing about fantasy advice

Market Intelligence
- knows market opinion
- forms no recommendations

League Intelligence
- knows user context
- predicts nothing

Player Intelligence
- forms player opinions
- chooses no actions

Decision Intelligence
- chooses actions
- does not retrain models

Evaluation Intelligence
- judges past performance
- never influences historical records

---

# Expansion Principle

New features should extend an existing capability whenever possible.

Examples:

Trade Analyzer -> Decision Intelligence

Waiver Assistant -> Decision Intelligence

Draft Assistant -> Decision Intelligence

If a feature requires an entirely new capability, its justification should be documented in an ADR.

---

# Mission Statement

Fantasy GM exists to help fantasy managers consistently make better decisions by combining historical data, market intelligence, transparent analysis, and continuous self-evaluation.

Success is measured by better decisions over time—not merely more accurate projections.
