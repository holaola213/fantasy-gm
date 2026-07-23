# Fantasy GM — Domain Model Foundation

**Phase:** -1  
**Status:** Draft for review  
**Purpose:** Define the stable language and conceptual boundaries of Fantasy GM before database, API, or implementation design.

---

## 1. Design Principle

Fantasy GM should model the real fantasy-basketball decision environment before it models tables, classes, or endpoints.

The system must distinguish:

- identity from observation
- source data from internal truth
- historical fact from forecast
- forecast from decision
- decision from outcome
- NBA context from fantasy-league context
- stable concepts from temporary source-specific fields

The goal is to avoid embedding assumptions into the foundation that later become expensive to remove.

---

## 2. Core Domain Areas

Fantasy GM is not one undifferentiated model. It contains several related domains.

### A. Basketball Domain

Represents the real NBA world.

Core concepts:

- Player
- NBA Team
- Season
- Game
- Player Game Performance
- Team Game Performance
- Schedule
- Roster Membership
- Injury / Availability State

### B. Fantasy League Domain

Represents the user's fantasy competition.

Core concepts:

- Fantasy League
- League Season
- Scoring System
- Roster Rules
- Fantasy Team
- Fantasy Roster Slot
- Draft
- Draft Pick
- Matchup
- Transaction
- Waiver State
- Player Eligibility
- Fantasy Player Availability

### C. Market Domain

Represents what external sources and fantasy managers believe at a specific time.

Core concepts:

- Market Snapshot
- Ranking
- Projection
- ADP
- Roster Percentage
- Ownership Percentage
- Availability Percentage
- Injury Label
- News Signal
- Source Observation

### D. Intelligence Domain

Represents Fantasy GM's own analytical outputs.

Core concepts:

- Feature Set
- Model Version
- Fantasy GM Projection
- Confidence Assessment
- Risk Assessment
- Player Valuation
- Replacement-Level Estimate
- Decision Context
- Recommendation
- Explanation
- Alternative
- Evaluation Result

### E. System Provenance Domain

Represents where data came from and how it was produced.

Core concepts:

- Data Source
- Source Record
- Ingestion Run
- Snapshot Run
- Transformation Version
- Model Version
- Recommendation Version
- Data Quality Result

---

# 3. Core Entities

## 3.1 Player

A real human basketball player.

### Stable identity attributes

- `player_id`
- full legal or commonly accepted name
- normalized name
- birth date
- active status

### External mappings

- NBA player ID
- ESPN player ID
- additional future source IDs

### Time-varying facts that do not belong directly on Player

- current team
- current fantasy position
- injury status
- ranking
- ownership
- projection
- roster status

Those belong to time-bounded observations or relationships.

### Important rule

A Player remains the same entity when:

- traded
- waived
- injured
- renamed
- assigned a new fantasy position
- represented differently by a source

---

## 3.2 NBA Team

A professional basketball franchise in a given league context.

Attributes:

- `nba_team_id`
- franchise name
- abbreviation
- city
- active status

Time-varying properties such as coach, roster, pace, and ratings should be observations or season-specific records.

---

## 3.3 Season

A basketball season.

Examples:

- 2025–26 NBA season
- 2026–27 NBA season

Attributes:

- `season_id`
- league
- start date
- end date
- season label
- season type definitions

A Season is not the same as a Fantasy League Season.

---

## 3.4 Game

A scheduled NBA contest between two NBA teams.

Attributes:

- `game_id`
- season
- home team
- away team
- scheduled start
- actual start
- status
- result

A Game exists before it is played. Its observed performances are separate entities.

---

## 3.5 Player Game Performance

A player's observed statistical performance in one NBA game.

Attributes may include:

- minutes
- field goals made and attempted
- free throws made and attempted
- rebounds
- assists
- steals
- blocks
- turnovers
- source metadata

Derived fantasy points should not be permanently treated as universal because they depend on league scoring rules.

---

## 3.6 Team Game Performance

An NBA team's observed performance in one game.

Useful for:

- pace
- offensive environment
- defensive environment
- opponent context
- possession estimates
- team-level feature engineering

---

## 3.7 Roster Membership

A time-bounded relationship between a Player and an NBA Team.

Attributes:

- player
- team
- effective start
- effective end
- roster status
- source

This avoids storing only a player's current team and losing historical truth.

---

## 3.8 Injury / Availability State

A time-bounded observation of a player's physical or participation status.

Examples:

- healthy
- probable
- questionable
- doubtful
- out
- suspended
- personal absence
- minutes restriction

Important distinction:

- source-reported label
- Fantasy GM normalized status
- expected availability probability

These must not be conflated.

---

# 4. Fantasy League Entities

## 4.1 Fantasy League

The persistent fantasy competition.

Attributes:

- `fantasy_league_id`
- platform
- external league ID
- league name
- manager count

The league persists across seasons.

---

## 4.2 Fantasy League Season

A specific season of a Fantasy League.

Attributes:

- fantasy league
- NBA season
- scoring system
- roster rules
- waiver rules
- playoff rules
- transaction rules
- start and end dates

This is the correct home for rules that may change from year to year.

---

## 4.3 Scoring System

The formula used to convert basketball statistics into fantasy points.

For the user's current league:

- FGM: +1
- FGA: -1
- FTM: +1
- FTA: -1
- REB: +1
- AST: +1
- STL: +2
- BLK: +2
- TO: -1

A Scoring System must be versioned and attached to a Fantasy League Season.

---

## 4.4 Fantasy Team

A manager-controlled team inside a Fantasy League Season.

Attributes:

- fantasy team ID
- league season
- manager identity
- team name
- external team ID

The same manager may control different teams over time.

---

## 4.5 Fantasy Roster Membership

A time-bounded relationship between a Player and a Fantasy Team.

Attributes:

- player
- fantasy team
- acquired at
- released at
- acquisition type
- active roster or reserve state

This is distinct from NBA Roster Membership.

---

## 4.6 Fantasy Roster Slot

Represents the slot assignment or constraint context for a rostered player.

Examples:

- PG
- SG
- SF
- PF
- C
- G
- F
- UTIL
- IR
- bench

A player's eligibility is separate from the slot they currently occupy.

---

## 4.7 Player Eligibility

A platform- and time-specific statement of which fantasy positions a Player may occupy.

Attributes:

- player
- platform
- league season
- eligible positions
- observed at
- source

This must be historical because platforms can add or remove eligibility.

---

## 4.8 Draft

A fantasy draft event for a Fantasy League Season.

Attributes:

- draft ID
- league season
- type
- date
- order
- settings

---

## 4.9 Draft Pick

One player selection in a Draft.

Attributes:

- draft
- pick number
- round
- fantasy team
- player
- timestamp
- source ranking at selection, when available

Draft Pick is historical fact. Draft Recommendation is not.

---

## 4.10 Matchup

A fantasy competition between Fantasy Teams over a scoring period.

Attributes:

- matchup ID
- scoring period
- participating teams
- start and end
- result
- current score

---

## 4.11 Transaction

A historical fantasy action.

Examples:

- add
- drop
- trade
- waiver claim
- IR move
- lineup move

Attributes:

- transaction ID
- league season
- timestamp
- type
- actors
- players
- status
- cost or waiver consequence

A Trade may later become a specialized aggregate containing several transaction components.

---

## 4.12 Waiver State

The current or historical waiver context of a player or team.

Possible elements:

- waiver priority
- FAAB remaining
- claim status
- player lock status
- clear date
- acquisition limit state

Waiver State is required because the value of an add depends on opportunity cost.

---

# 5. Market Entities

## 5.1 Snapshot Run

A collection event at a specific time.

Attributes:

- `snapshot_run_id`
- captured at
- source
- league context
- status
- completeness
- ingestion version

A Snapshot Run is not itself a player's market state. It groups observations.

---

## 5.2 Source Observation

A raw or normalized statement made by an external source at a point in time.

Examples:

- ESPN rank = 42
- ESPN projection = 31.8
- rostered percentage = 81%
- injury label = questionable
- eligible positions = PG, SG

Attributes:

- subject
- metric
- value
- source
- observed at
- valid for
- snapshot run
- raw record reference
- quality status

This is the most general market-data building block.

---

## 5.3 Market Snapshot

A consolidated time-stamped view of market signals for one Player.

Potential contents:

- rankings
- ADP
- ownership
- roster percentage
- availability
- platform projection
- public injury label
- recent trend
- source coverage

A Market Snapshot is derived from Source Observations and should retain provenance.

---

## 5.4 Ranking

A source's ordered assessment of players.

Required context:

- source
- timestamp
- ranking scope
- league or scoring format
- position scope
- rank value
- methodology, if known

A rank without format and timestamp is not meaningful.

---

## 5.5 External Projection

A source's forecast for a Player.

Required context:

- source
- target period
- scoring system or statistic target
- forecast value
- published at
- source methodology, if known

This is separate from Fantasy GM Projection.

---

## 5.6 ADP

Average draft position from a specific source and draft population.

Required context:

- platform
- scoring format
- date range
- draft type
- sample size, if known

ADP is a market behavior signal, not a player-performance forecast.

---

## 5.7 News Signal

A structured interpretation of news rather than a permanently stored article.

Attributes may include:

- player
- source
- published time
- event type
- direction
- expected duration
- confidence
- source reference

Examples:

- expected starter
- minutes restriction
- coach change
- trade
- suspension
- return timeline

Full copyrighted article text should not be part of the canonical model.

---

# 6. Intelligence Entities

## 6.1 Feature Set

The exact analytical inputs used by a model or rules engine.

Attributes:

- feature set version
- target date
- player
- values
- source timestamps
- completeness
- leakage check result

Feature Sets must preserve point-in-time correctness.

---

## 6.2 Model Version

An immutable definition of an analytical model.

Attributes:

- model family
- version
- training period
- feature set version
- hyperparameters
- code revision
- created at
- status

A model version should never silently change after producing outputs.

---

## 6.3 Fantasy GM Projection

Fantasy GM's forecast for a Player over a defined target period.

Required context:

- player
- target period
- scoring system
- model version
- created at
- projected value
- distribution or interval
- input snapshot cutoff

A projection is invalid without a target period and scoring context.

---

## 6.4 Confidence Assessment

An assessment of how trustworthy a projection or recommendation is.

Possible components:

- data completeness
- role stability
- injury uncertainty
- minutes uncertainty
- source agreement
- model historical reliability
- schedule certainty
- sample size

Confidence is not the same as upside or predicted performance.

---

## 6.5 Risk Assessment

A structured estimate of downside or volatility.

Possible risk categories:

- injury
- role
- minutes
- rotation
- transaction
- suspension
- schedule
- sample-size
- model disagreement

Confidence and risk are related but should remain separate.

---

## 6.6 Player Valuation

A context-specific estimate of a player's fantasy value.

Required context:

- player
- league season
- decision date
- horizon
- replacement level
- roster constraints
- projection
- risk
- scarcity
- market price

There is no universal Player Value.

---

## 6.7 Decision Context

The complete state surrounding a decision.

Examples:

- draft pick number
- available players
- user's roster
- opponents' rosters
- waiver priority
- transaction limits
- playoff schedule
- matchup horizon
- trade offer
- alternatives

A recommendation cannot be evaluated fairly without its Decision Context.

---

## 6.8 Recommendation

Fantasy GM's suggested action.

Examples:

- draft Player A
- add Player B
- hold Player C
- drop Player D
- accept trade
- reject trade
- start Player E
- preserve waiver priority

Required context:

- recommendation type
- decision context
- created at
- valid until
- model and rules versions
- selected action
- alternatives
- confidence
- expected benefit

A Recommendation is not simply a rank.

---

## 6.9 Explanation

The evidence and reasoning presented with a Recommendation.

Possible components:

- projection difference
- market discrepancy
- schedule advantage
- role change
- injury uncertainty
- roster fit
- scarcity
- opportunity cost
- confidence drivers

Explanations should be generated from recorded evidence, not invented after the fact.

---

## 6.10 Alternative

A feasible action not selected by the Recommendation.

Examples:

- draft the next-best guard
- hold waiver priority
- stream another player
- reject trade and counter

Alternatives are necessary for evaluating whether the selected action was actually best among available choices.

---

## 6.11 Evaluation Result

The retrospective assessment of a Projection or Recommendation.

Potential fields:

- evaluation horizon
- realized outcome
- baseline outcome
- counterfactual outcome, if estimable
- regret
- calibration result
- decision success criteria
- caveats

Projection accuracy and decision quality must be evaluated separately.

---

# 7. Concepts That Must Not Be Collapsed

## Player vs Player Snapshot

- Player = stable human identity
- Player Snapshot = state observed at a time

## NBA Team vs Fantasy Team

- NBA Team = real basketball franchise
- Fantasy Team = manager-controlled roster

## NBA Roster Membership vs Fantasy Roster Membership

They represent completely different relationships.

## Fact vs Forecast

- Game performance = fact
- Projection = forecast

## Projection vs Valuation

- Projection estimates performance
- Valuation incorporates context, scarcity, risk, and replacement level

## Valuation vs Recommendation

- Valuation compares worth
- Recommendation chooses an action in a specific decision context

## Confidence vs Risk

- Confidence describes trust in the estimate
- Risk describes downside, volatility, or failure modes

## Source Observation vs Canonical Fact

- Source Observation records what a source said
- Canonical Fact is Fantasy GM's reconciled representation

## Snapshot Time vs Valid Time

A source may be captured today but describe a status valid for tomorrow or a ranking published yesterday.

Both must be represented.

---

# 8. Concepts Deliberately Deferred

These may be useful later but should not enter the foundation until justified.

- Manager psychology
- Trade negotiation behavior
- Social sentiment
- Betting markets
- Salary-cap dynasty contracts
- Keeper costs
- Category-league punt strategies
- College or international prospect models
- Computer vision
- Natural-language article storage
- Real-time play-by-play recommendations
- Multi-sport abstractions

The initial architecture should not prevent them, but it should not be distorted by them.

---

# 9. Aggregate Boundaries

Potential aggregates help define where consistency matters.

## Player Aggregate

- Player
- external ID mappings
- identity aliases

Does not own projections, rankings, or injury history.

## NBA Game Aggregate

- Game
- team game performances
- player game performances

## Fantasy League Season Aggregate

- league rules
- fantasy teams
- schedule periods
- draft settings
- waiver settings

## Transaction Aggregate

- transaction
- involved teams
- player movements
- cost
- status

## Snapshot Run Aggregate

- capture metadata
- source observations
- validation results

## Recommendation Aggregate

- decision context reference
- selected action
- alternatives
- explanation
- confidence
- model versions

These are preliminary and should be revisited during architecture design.

---

# 10. Key Invariants

The following rules should eventually be enforced by design.

1. Every source-derived record has provenance.
2. Every time-varying record has an observation or validity timestamp.
3. Every projection has a target period.
4. Every fantasy-point projection identifies its scoring system.
5. Every model output identifies the exact model version.
6. Every recommendation identifies the decision context.
7. Every evaluation uses only information available at the original decision time.
8. A Player is never identified solely by name.
9. Source-specific objects do not cross adapter boundaries.
10. Historical records are append-only unless corrected with an audit trail.
11. Current state is derived from history, not substituted for it.
12. Missing data is represented explicitly, not silently converted to zero.
13. Confidence is never inferred only from projection magnitude.
14. Recommendations expire when their underlying context materially changes.
15. Fantasy GM calculations must be reproducible from stored inputs and versions.

---

# 11. Preliminary Relationship Map

```text
NBA Season
├── NBA Team
│   └── Roster Membership ── Player
├── Game
│   ├── Team Game Performance
│   └── Player Game Performance ── Player
└── Schedule

Fantasy League
└── Fantasy League Season
    ├── Scoring System
    ├── Roster Rules
    ├── Fantasy Team
    │   └── Fantasy Roster Membership ── Player
    ├── Draft
    │   └── Draft Pick ── Player
    ├── Matchup
    ├── Transaction
    └── Waiver State

Data Source
└── Snapshot Run
    └── Source Observation
        └── Market Snapshot ── Player

Player + Historical Facts + Market Snapshot + League Context
└── Feature Set
    └── Model Version
        └── Fantasy GM Projection
            ├── Confidence Assessment
            ├── Risk Assessment
            └── Player Valuation
                └── Decision Context
                    └── Recommendation
                        ├── Explanation
                        ├── Alternatives
                        └── Evaluation Result
```

---

# 12. Decisions Emerging From the Domain Model

These are not yet accepted ADRs.

## Candidate Decision A

Fantasy GM must use temporal modeling for all changing state.

Reason:

Current-only fields destroy historical truth and make honest backtesting impossible.

## Candidate Decision B

Projection, valuation, and recommendation are separate domain concepts.

Reason:

Combining them would recreate the exact projection-centric architecture rejected by ADR-001.

## Candidate Decision C

Every recommendation must preserve its available alternatives and decision context.

Reason:

Decision quality cannot be evaluated from the selected action alone.

## Candidate Decision D

Source observations remain immutable and traceable even after normalization.

Reason:

Future corrections and source disagreements require an audit trail.

## Candidate Decision E

League rules belong to Fantasy League Season, not Fantasy League.

Reason:

Rules can change between seasons.

---

# 13. Outstanding Questions Before Finalization

1. Should `Confidence Assessment` be its own entity or a component of each analytical output?
2. Should `Risk Assessment` be independent or embedded within Player Valuation?
3. Should `Market Snapshot` be materialized, or derived dynamically from Source Observations?
4. Should a Trade be a specialized domain entity rather than only a Transaction type?
5. Should manager identity be modeled in Version 1?
6. How should lineup decisions be represented: as Recommendations, Transactions, or a separate Lineup Decision?
7. Is `Replacement-Level Estimate` an entity, value object, or derived calculation?
8. Should scoring periods be explicit entities?
9. How should multi-day projections and rest-of-season projections share a common abstraction?
10. Which records require bitemporal history: observed time and valid time?
11. How should corrections to source data be recorded without mutating history?
12. What minimum context must exist before a Recommendation can legally be generated?

---

# 14. Recommended Next Review

Before database design, resolve the outstanding questions in this order:

1. Temporal model
2. Projection vs valuation vs recommendation boundaries
3. Decision context and alternatives
4. Confidence and risk
5. Market snapshot materialization
6. Trade and lineup specialization
7. Aggregate boundaries
8. Minimum valid recommendation contract

Only after those are settled should the project create:

- class diagrams
- database tables
- API contracts
- service boundaries
- production code

---

# 15. Foundation Standard

The domain model is ready for implementation only when:

- important terms have one agreed meaning
- time-varying data has an explicit temporal design
- source-specific concepts are isolated
- facts, forecasts, valuations, and decisions are separate
- recommendation evaluation is possible
- all foundational invariants are documented
- unresolved questions are either answered or deliberately deferred

> Build for Version 10, ship Version 1.
