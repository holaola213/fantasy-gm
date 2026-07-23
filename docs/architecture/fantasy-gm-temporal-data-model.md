# Fantasy GM — Temporal Data Model

**Phase:** -1  
**Status:** Draft for review  
**Purpose:** Define how Fantasy GM represents time, historical truth, source observations, corrections, forecasts, and decision context.

---

## 1. Why Time Is a Foundational Concern

Fantasy GM is a time-dependent decision system.

Nearly every important fact can change:

- player team
- injury status
- fantasy eligibility
- ESPN rank
- ownership percentage
- roster membership
- waiver priority
- model projection
- recommendation
- available alternatives

A current-state-only model would destroy the historical context needed to answer:

> What did Fantasy GM know at the time, and was the recommendation reasonable using only that information?

Therefore, temporal behavior must be designed before database tables or application services.

---

# 2. The Four Times Fantasy GM Must Distinguish

Fantasy GM should not use one generic timestamp for every record.

## 2.1 Event Time

When something happened in the real world.

Examples:

- a game started
- a trade became official
- a player was added to a fantasy roster
- an injury occurred
- a lineup locked

Suggested field:

```text
event_time
```

---

## 2.2 Published Time

When a source publicly released information.

Examples:

- ESPN published a ranking
- a reporter posted an injury update
- an NBA transaction was announced
- a projection provider released new values

Suggested field:

```text
published_at
```

Published time may be unavailable for some sources.

---

## 2.3 Observed Time

When Fantasy GM actually captured or received the information.

Examples:

- Fantasy GM fetched ESPN at 9:05 AM
- the ingestion process detected a news item at 9:12 AM
- the league sync recorded a roster move at 10:00 AM

Suggested field:

```text
observed_at
```

This is essential for point-in-time evaluation.

Fantasy GM cannot claim it knew information before `observed_at`.

---

## 2.4 Valid Time

The period during which a fact or belief applies.

Examples:

- a player belonged to Boston from July 1 through February 6
- a player was Questionable from 8:30 AM until ruled Out
- a fantasy roster membership lasted from acquisition until release
- a projection applied to games on October 28
- a ranking was intended for the 2026–27 preseason

Suggested fields:

```text
valid_from
valid_to
```

`valid_to` may be open-ended.

---

# 3. Core Temporal Rule

Every time-varying record must answer two questions:

1. **When did Fantasy GM know this?**
2. **For what period was it considered true or applicable?**

This produces two separate timelines:

```text
Knowledge timeline:
observed_at

Reality or applicability timeline:
valid_from -> valid_to
```

This is a simplified bitemporal model.

---

# 4. Recommended Temporal Strategy

Fantasy GM should use a practical bitemporal design.

## System-Time Dimension

Represents when Fantasy GM stored or knew a record.

Fields:

```text
recorded_at
superseded_at
```

or, for source-facing records:

```text
observed_at
superseded_at
```

## Valid-Time Dimension

Represents when the underlying fact or belief applies.

Fields:

```text
valid_from
valid_to
```

Not every record needs all four fields, but every temporal entity must explicitly define which timestamps it uses.

---

# 5. Temporal Record Categories

Different record types need different temporal behavior.

## 5.1 Immutable Historical Events

Examples:

- completed game
- draft pick
- completed transaction
- recommendation issued
- model trained

Recommended timestamps:

- `event_time`
- `recorded_at`

These records are append-only.

Corrections create a new version or correction record rather than silently overwriting history.

---

## 5.2 Time-Bounded States

Examples:

- NBA roster membership
- fantasy roster membership
- injury state
- fantasy eligibility
- waiver state
- team coach
- active status

Recommended timestamps:

- `valid_from`
- `valid_to`
- `observed_at`
- `superseded_at`

These records represent intervals.

---

## 5.3 Point-in-Time Observations

Examples:

- ESPN rank
- roster percentage
- ownership percentage
- source projection
- market sentiment
- source injury label

Recommended timestamps:

- `published_at`, when available
- `observed_at`
- `effective_for`, when applicable
- snapshot run ID

These are generally append-only observations rather than mutable current fields.

---

## 5.4 Forecasts

Examples:

- next-game fantasy points
- weekly fantasy points
- rest-of-season value
- playoff-period value

Recommended timestamps:

- `created_at`
- `information_cutoff`
- `target_start`
- `target_end`
- `valid_until`

A forecast must never be evaluated using information after `information_cutoff`.

---

## 5.5 Recommendations

Examples:

- draft Player A
- accept a trade
- add Player B
- preserve waiver priority
- start Player C

Recommended timestamps:

- `created_at`
- `information_cutoff`
- `valid_from`
- `valid_until`
- `resolved_at`

A recommendation may expire early if its context changes materially.

---

# 6. Information Cutoff

Every analytical output must store:

```text
information_cutoff
```

Definition:

> The latest point in time from which input information was allowed to influence the output.

This is not always identical to `created_at`.

Example:

```text
Data snapshot completed: 8:00 AM
Projection generated: 8:07 AM
Recommendation created: 8:09 AM

information_cutoff = 8:00 AM
created_at = 8:09 AM
```

This field is required for honest backtesting.

---

# 7. Snapshot Runs

A Snapshot Run groups records collected together.

Suggested attributes:

```text
snapshot_run_id
source_id
started_at
completed_at
information_cutoff
status
record_count
success_count
failure_count
schema_version
ingestion_version
```

A Snapshot Run should be immutable once completed, except for operational annotations.

---

# 8. Source Observation Versioning

A source observation should never be overwritten in place.

Example:

```text
9:00 AM — ESPN injury label: Questionable
11:15 AM — ESPN injury label: Out
```

Store both.

The current state is derived by selecting the latest valid observation according to explicit rules.

Suggested observation fields:

```text
observation_id
subject_id
metric_type
value
source_id
published_at
observed_at
valid_from
valid_to
snapshot_run_id
source_record_id
quality_status
```

---

# 9. Corrections

Sources may publish incorrect information or revise historical records.

Fantasy GM should distinguish:

## New Information

A later state supersedes an earlier state.

Example:

- Questionable becomes Out

## Correction

A source indicates the earlier value was wrong.

Example:

- a box score originally credited 9 rebounds, later corrected to 10

Recommended correction fields:

```text
corrects_record_id
correction_reason
recorded_at
```

The original record remains preserved.

---

# 10. Current State Views

Fantasy GM may expose convenient current-state views, but they must be derived.

Examples:

```text
current_player_team
current_injury_state
current_fantasy_roster
current_espn_rank
current_waiver_priority
```

These should be:

- database views
- materialized views
- query-layer projections
- cached read models

They should not replace the underlying temporal records.

---

# 11. Time Zones

All persisted timestamps should use UTC.

Display conversion should happen at the application boundary.

Rules:

- Store timezone-aware UTC timestamps.
- Never persist ambiguous local timestamps.
- Preserve source timezone when needed for provenance.
- Store NBA game venue or league timezone separately when relevant.
- Use the user's timezone only for presentation and user-entered scheduling.

Recommended format:

```text
2026-07-23T21:30:00Z
```

---

# 12. Date-Only and Season Concepts

Not every temporal value is a timestamp.

Use date-only fields for:

- season start date
- season end date
- fantasy playoff date
- transaction day grouping
- schedule date where time is intentionally absent

Use season identifiers for:

- NBA season
- fantasy league season
- model training season range

Do not encode a season only as free text.

---

# 13. Temporal Semantics by Entity

## Player

Mostly non-temporal identity.

Time-varying relationships:

- name alias history
- active status history
- NBA roster membership

---

## NBA Roster Membership

```text
valid_from
valid_to
observed_at
```

---

## Fantasy Roster Membership

```text
acquired_at
released_at
observed_at
```

---

## Injury State

```text
published_at
observed_at
valid_from
valid_to
```

---

## Player Eligibility

```text
observed_at
valid_from
valid_to
```

---

## Ranking

```text
published_at
observed_at
effective_for
```

---

## External Projection

```text
published_at
observed_at
target_start
target_end
```

---

## Fantasy GM Projection

```text
created_at
information_cutoff
target_start
target_end
valid_until
```

---

## Recommendation

```text
created_at
information_cutoff
valid_from
valid_until
resolved_at
```

---

## Evaluation Result

```text
evaluation_created_at
evaluation_horizon_start
evaluation_horizon_end
```

---

# 14. Recommendation Expiration

A recommendation should be treated as invalid when its underlying decision context materially changes.

Examples:

- player ruled out
- trade accepted elsewhere
- waiver priority changes
- another manager adds the recommended player
- lineup locks
- projection is regenerated after major news
- schedule changes
- roster constraint changes

Recommended fields:

```text
valid_until
invalidated_at
invalidation_reason
```

The original recommendation remains preserved for evaluation.

---

# 15. Point-in-Time Query Requirement

Fantasy GM must eventually support queries such as:

```text
What did we know about Player X at 3:00 PM on October 24?
```

```text
What was ESPN's latest observed rank before the draft began?
```

```text
Which players were available when this waiver recommendation was issued?
```

```text
What injury information existed before lineup lock?
```

```text
Which model version and feature values created this recommendation?
```

If the data model cannot answer these questions, it is not sufficient.

---

# 16. Backtesting Rules

A valid backtest must enforce:

1. No record with `observed_at` after the decision cutoff may be used.
2. No corrected value may be substituted retroactively unless the evaluation explicitly tests corrected-data performance.
3. Current roster state may not replace historical roster state.
4. Current player eligibility may not replace historical eligibility.
5. Revised projections may not replace the version originally available.
6. Target outcomes must occur after the information cutoff.
7. Decision alternatives must reflect what was actually available at that time.
8. Model and transformation versions must be reproducible.

---

# 17. Storage Model Recommendation

Use append-only historical tables for source and analytical records.

Likely patterns:

```text
players
player_aliases
nba_roster_memberships
fantasy_roster_memberships
injury_state_history
eligibility_history
source_observations
snapshot_runs
projections
recommendations
recommendation_invalidations
evaluation_results
```

Current-state access should come from views or read models.

---

# 18. Candidate Temporal Invariants

1. `valid_to` must be later than `valid_from`.
2. `target_end` must be later than or equal to `target_start`.
3. `information_cutoff` cannot be later than `created_at`.
4. Evaluation outcomes must occur after the analytical information cutoff.
5. Overlapping roster memberships for the same player should be prohibited unless explicitly valid.
6. A completed Snapshot Run cannot accept additional observations.
7. Corrections must reference the record being corrected.
8. Historical source observations cannot be hard deleted during normal operation.
9. Recommendation invalidation cannot precede recommendation creation.
10. A current-state view must always be reproducible from historical records.

---

# 19. Decisions Proposed

## Proposed ADR — Use Practical Bitemporal Modeling

Fantasy GM will distinguish:

- when information was known to the system
- when the information was valid or applicable

This applies to all materially time-varying state.

---

## Proposed ADR — Analytical Outputs Require an Information Cutoff

Every projection, valuation, and recommendation must identify the latest input time used.

---

## Proposed ADR — Historical State Is Append-Only

Source observations, projections, and recommendations are preserved rather than overwritten.

Corrections and superseding records are explicit.

---

## Proposed ADR — Current State Is Derived

Convenient current-state representations may exist, but they must be derived from temporal history.

---

# 20. Resolved Domain Questions

This temporal review resolves several questions from the domain-model document.

## Which records need bitemporal history?

At minimum:

- injury states
- roster memberships
- fantasy eligibility
- waiver state
- source rankings
- source projections
- ownership and availability
- recommendations
- context-sensitive valuations

## How should corrections be recorded?

By appending a correction that references the original record.

## What minimum temporal context does a Recommendation require?

- `created_at`
- `information_cutoff`
- `valid_from`
- `valid_until`
- original decision context
- model and rules versions

---

# 21. Remaining Questions

1. Which entities need full valid intervals versus point observations only?
2. How long should raw source responses be retained?
3. Should all source observations use one generalized table or typed tables?
4. Should Snapshot Runs be global, per source, or per data category?
5. How should partially completed snapshot runs affect analytical eligibility?
6. When two sources disagree, which observation becomes canonical?
7. Should recommendation invalidation be event-driven or checked at read time?
8. How should retroactive NBA stat corrections affect previous evaluations?
9. Should “effective for” be a date, scoring period, game, or generic target reference?
10. Which current-state views should be materialized for performance?

---

# 22. Final Temporal Principle

> Fantasy GM must preserve both the history of the world and the history of what it believed about the world.

Without both, it cannot evaluate decision quality honestly.
