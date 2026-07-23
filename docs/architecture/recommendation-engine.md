---
title: Recommendation Engine
version: 1.0
status: Draft
owner: Admin
last_updated: 2026-07-23
---

# Recommendation Engine

## Purpose

This document defines the decision process Fantasy GM uses to recommend a fantasy basketball draft pick.

It describes the reasoning model, major inputs, evaluation stages, confidence philosophy, explanation requirements, and historical data that must be preserved.

It does not define final formulas, production weights, or implementation-specific code.

---

# Core Decision Question

Fantasy GM does not ask:

> Who is the best player?

It asks:

> Who creates the most value if drafted right now?

A recommendation is therefore contextual rather than static.

The answer may change based on:

- League scoring
- Current pick
- Current roster
- Remaining player pool
- Positional scarcity
- Draft tiers
- Expected availability at the next pick
- Player risk
- Admin's draft strategy

---

# Recommendation Principles

## Context Over Consensus

General rankings, expert rankings, and ADP are inputs—not answers.

A player ranked higher by the market is not automatically the best selection for the current situation.

---

## Projection Is Not Recommendation

A season projection estimates future fantasy production.

A recommendation considers whether selecting that production now is the best available decision.

---

## Every Recommendation Must Be Decomposable

Fantasy GM must be able to explain why one player was recommended over another.

The recommendation must be reproducible from stored inputs and evaluation results.

---

## Explanations Must Reflect Actual Reasoning

Explanations may only reference factors that materially influenced the recommendation.

Fantasy GM must not generate generic or invented explanations after the decision has already been made.

---

## Uncertainty Must Be Visible

Conflicting evidence, weak source quality, unstable player roles, and incomplete data should reduce confidence.

Uncertainty should never be hidden to make a recommendation appear stronger.

---

## Personalization Is Intentional

Version 1 is optimized for Admin's league and decision style.

The engine does not need to produce a universally optimal public ranking.

It should produce recommendations that consistently help Admin make better decisions in the configured league.

---

# Decision Context

The recommendation engine evaluates players using five categories of context.

## 1. League Context

League context is relatively stable during a draft.

Examples:

- Scoring rules
- Number of teams
- Starting roster slots
- Bench slots
- Position limits
- Position eligibility rules
- Draft format
- Transaction rules relevant to roster construction

League context determines how real NBA production becomes fantasy value.

---

## 2. Draft Context

Draft context changes after every selection.

Examples:

- Current round
- Current overall pick
- Snake-draft direction
- Number of selections until Admin's next pick
- Drafted players
- Available players
- Recent positional runs
- Remaining players by tier
- Current draft pace

Draft context determines the opportunity cost of selecting or passing on a player.

---

## 3. Team Context

Team context represents Admin's current roster.

Examples:

- Drafted players
- Filled roster slots
- Remaining roster needs
- Position eligibility coverage
- Concentration of risk
- Concentration of NBA teams
- Current balance between floor and upside
- Roster flexibility

Team context should affect recommendations without causing the engine to reach aggressively for positional need.

---

## 4. Player Context

Player context describes the candidate being evaluated.

Examples:

- Projected fantasy points
- Projected games played
- Projected minutes
- Expected role
- Position eligibility
- NBA team
- Age
- Injury status
- Injury history
- Role stability
- Minutes stability
- Statistical floor
- Statistical ceiling
- Projection-source disagreement

---

## 5. Market Context

Market context estimates how the rest of the draft is likely to behave.

Examples:

- Average draft position
- Expert consensus ranking
- Platform ranking
- Draft tier
- Recent draft trends
- Positional runs
- Expected availability at Admin's next pick

Market context is used to estimate whether a player must be selected now or can reasonably be targeted later.

It should not override league-specific value by itself.

---

# Evaluation Pipeline

The recommendation process is divided into distinct stages.

```text
Raw Data
   |
Context Builder
   |
Eligibility Filter
   |
Player Evaluation
   |
Opportunity-Cost Evaluation
   |
Candidate Comparison
   |
Recommendation Selection
   |
Confidence Assessment
   |
Explanation Builder
   |
Historical Record
```

Each stage should be independently testable.

---

# Stage 1 — Context Builder

The Context Builder creates a complete snapshot of the decision environment.

The snapshot should include:

- League settings
- Current draft state
- Admin's roster
- Available player pool
- Player projections
- Risk information
- ADP and market data
- Tier definitions
- Admin strategy configuration
- Data-source timestamps

The same stored context should always reproduce the same recommendation when evaluated with the same engine version and configuration.

---

# Stage 2 — Eligibility Filter

The engine removes players who cannot reasonably be recommended.

Possible exclusion reasons:

- Already drafted
- Not eligible for the league player pool
- Inactive or unavailable
- Missing essential projection data
- Violates a hard roster or position constraint
- Explicitly excluded by Admin

Filtering should be conservative.

A player with uncertain data should usually remain eligible but receive lower confidence or higher risk rather than being silently removed.

---

# Stage 3 — Player Evaluation

Every eligible player is evaluated independently.

The initial V1 evaluation should consider the following factor groups.

## Projected Fantasy Value

Measures expected production under the league's scoring system.

Possible inputs:

- Projected total fantasy points
- Projected fantasy points per game
- Projected games played
- Replacement-level baseline
- Value over replacement

---

## Draft Value

Measures the relationship between the player's league-specific value and acquisition cost.

Possible inputs:

- Current overall pick
- ADP
- Platform rank
- Expert consensus rank
- Expected draft range
- Difference between current cost and expected cost

A player can be valuable without being the optimal pick if the engine expects that player to remain available later.

---

## Tier Position

Measures the player's place within a cluster of similarly valued players.

Possible inputs:

- Current tier
- Distance from the next player in the same tier
- Drop-off to the next tier
- Number of comparable players remaining
- Position-specific tier depth

Tier information should help identify when waiting creates a meaningful loss of options.

---

## Roster Fit

Measures how the player affects Admin's current roster construction.

Possible inputs:

- Position eligibility coverage
- Remaining starting-slot needs
- Roster flexibility
- Floor versus upside balance
- Risk concentration
- Role concentration
- Opportunity to avoid future forced reaches

Roster fit should be a contextual adjustment—not a substitute for player value.

---

## Positional Scarcity

Measures the remaining supply of useful players at each eligible position.

Possible inputs:

- Number of draftable players remaining
- Tier depth by position
- Replacement value by position
- Required roster slots
- Number of managers likely to need the position

Scarcity should matter most when the difference between available options is meaningful.

---

## Player Risk

Measures uncertainty that could reduce realized value.

Possible inputs:

- Current injury status
- Injury recurrence concerns
- Projected games uncertainty
- Role uncertainty
- Minutes uncertainty
- Rotation competition
- Team context volatility
- Projection-source disagreement

Risk should not automatically eliminate upside players.

Its effect may vary by draft stage and Admin's strategy.

---

## Upside and Floor

Measures the range of plausible outcomes.

Possible inputs:

- Conservative projection
- Baseline projection
- Optimistic projection
- Role-expansion scenario
- Injury-loss scenario

Early-round preferences may favor stability, while later rounds may favor asymmetric upside.

This behavior should remain configurable.

---

# Stage 4 — Opportunity-Cost Evaluation

The engine evaluates the cost of selecting or passing on each candidate.

This stage separates Fantasy GM from a static ranking list.

## Next-Pick Availability

Estimates the likelihood that a player remains available at Admin's next selection.

Possible inputs:

- ADP distribution
- Current pick
- Number of selections until the next pick
- Platform ranking
- Recent positional runs
- Tier depth
- Manager roster needs, when available

This should be presented as an estimate, not a certainty.

---

## Expected Value Lost by Waiting

Estimates the value difference between:

1. Drafting the candidate now, and
2. Waiting until the next pick and selecting the best likely remaining alternative.

Conceptually:

```text
Expected Value Lost by Waiting
=
Current Candidate Value
-
Expected Best Value Available at Next Pick
```

The production formula may later account for multiple future availability scenarios.

---

## Tier Drop-Off

Measures the decline from the current candidate or tier to the likely alternatives available later.

A meaningful tier drop increases the urgency to draft now.

---

## Flexibility Preserved

Measures whether selecting a player keeps future draft options open.

Examples:

- Multi-position eligibility
- Filling a scarce slot without forcing later reaches
- Avoiding overcommitment to one position
- Preserving access to several viable future roster constructions

---

# Stage 5 — Candidate Comparison

The engine compares the strongest candidates directly.

The comparison should answer:

- Which player has the highest league-specific projected value?
- Which player offers the strongest value at the current pick?
- Which player is least likely to survive until the next pick?
- Which player sits before the largest tier drop?
- Which player best supports the current roster?
- Which player introduces the most risk?
- Which choice preserves the most future flexibility?

The engine should retain the strongest rejected alternatives and the reasons they ranked below the recommendation.

---

# Stage 6 — Recommendation Selection

Fantasy GM produces:

- One primary recommendation
- A small set of alternatives
- Material reasons supporting the recommendation
- Material reasons the alternatives were not selected

The primary recommendation should maximize the estimated value of the current decision—not merely season-long projection.

---

# Standard Metrics

Fantasy GM should prefer established terminology where appropriate.

Initial standard metrics may include:

- Projected Fantasy Points
- Projected Fantasy Points per Game
- Value Over Replacement (VOR)
- Average Draft Position (ADP)
- Draft Tier
- Positional Scarcity
- Injury Risk
- Role Stability
- Minutes Stability

Definitions and formulas should be documented separately when implementation begins.

---

# Custom Metrics

Custom metrics are acceptable when they answer a useful decision question that standard metrics do not answer clearly.

## Next-Pick Availability

Definition:

> Estimated probability that a player remains undrafted until Admin's next selection.

---

## Expected Value Lost by Waiting

Definition:

> Estimated fantasy value sacrificed by passing on a player now and choosing from the likely player pool at Admin's next pick.

---

## Roster Fit Score

Definition:

> A contextual score representing how well a player supports the current roster's slot coverage, flexibility, risk balance, and future draft options.

The score must be decomposable into documented inputs.

---

## Recommendation Confidence

Definition:

> A measure of how strongly and consistently the available evidence supports the selected recommendation over the alternatives.

Confidence is not:

- A probability that the player will succeed
- A probability that the recommendation is objectively correct
- A substitute for risk
- A projection percentile

---

# Confidence Assessment

Recommendation confidence should reflect the quality and agreement of evidence.

## Confidence Increases When

- Multiple projection sources agree
- The recommended player leads across several relevant factors
- The recommendation remains stable under reasonable weight changes
- The tier drop is clear
- Next-pick availability is low
- Player role and health are stable
- Data is current and complete

---

## Confidence Decreases When

- Projection sources disagree materially
- Several candidates are nearly equivalent
- The recommendation changes under small assumption changes
- Player role or health is uncertain
- Availability estimates are weak
- Data is stale or incomplete
- Roster fit conflicts with projected value
- Market information strongly conflicts with league-specific valuation

---

## Confidence Labels

Initial labels may use:

- High
- Moderate
- Low

Numerical values may also be displayed, but the formula must be documented and should not imply false precision.

---

# Objective and Configurable Factors

## Objective Inputs

Objective inputs are derived directly from data or deterministic league state.

Examples:

- League scoring settings
- Current pick
- Drafted players
- Current roster
- Player projections
- Position eligibility
- ADP
- Injury designation
- Number of picks until the next selection

Given the same data and engine version, these inputs should produce the same result.

---

## Configurable Strategy

Configurable factors reflect Admin's preferred draft strategy.

Examples:

- Early-round preference for floor
- Late-round preference for upside
- Injury-risk tolerance
- Positional-scarcity aggressiveness
- Willingness to reach ahead of ADP
- Strength assigned to roster fit
- Value assigned to multi-position eligibility

Version 1 may initially use documented default settings rather than a full configuration UI.

The configuration must still be stored separately from objective data so it can be tuned later.

---

# Explanation Requirements

Every recommendation explanation must be generated from structured evaluation results.

## Explanation Structure

A recommendation should communicate:

1. The recommended player
2. The most important supporting factors
3. The most important risk or counterargument
4. Why the strongest alternative ranked lower
5. The cost of waiting, when material
6. Recommendation confidence

---

## Example

```text
Recommend: Player A

Primary reasons:
- Highest league-adjusted projected value among available players
- Final player remaining in the current tier
- Estimated 18% chance of remaining available at the next pick
- Adds PF/C eligibility without creating roster imbalance

Main concern:
- Moderate injury risk

Player B ranked second because:
- Similar projection
- Greater next-pick availability
- Smaller tier drop if passed over
```

---

# Historical Recording

Every recommendation event should preserve enough information to reproduce and evaluate the decision later.

Store:

- Engine version
- Strategy configuration version
- Decision timestamp
- League context snapshot
- Draft context snapshot
- Team context snapshot
- Candidate player pool
- Source projections and timestamps
- Market inputs
- Factor results for evaluated candidates
- Primary recommendation
- Alternative recommendations
- Confidence result
- Structured explanation factors
- Player actually selected
- Selection source: recommended, alternative, or other
- Subsequent draft state

Historical records should be append-only where practical.

Corrections should not erase the original decision context.

---

# Evaluation After the Draft

The engine should eventually support evaluating both process and outcomes.

## Process Evaluation

Questions:

- Was the recommendation based on current data?
- Was the player expected to remain available?
- Did the explanation match the actual factors?
- Was confidence appropriate given the evidence?
- Did Admin follow the recommendation?

---

## Outcome Evaluation

Questions:

- Did the player outperform likely alternatives?
- Did the player remain available until the next pick?
- Was the tier drop estimated correctly?
- Did roster fit improve the final team?
- Which factors were consistently over- or underweighted?

Outcome evaluation must not treat every bad result as a bad decision.

The goal is to improve decision quality, not judge recommendations solely through hindsight.

---

# V1 Boundaries

Version 1 does not require:

- Machine learning
- A universal player ranking model
- Fully dynamic user-configurable weights
- Perfect opponent draft prediction
- Automated ESPN draft selections
- LLM-generated recommendations
- Unstructured AI reasoning
- Public recommendations for other users or league formats

A deterministic, explainable, league-specific baseline is preferred over a more complex opaque model.

---

# Initial V1 Recommendation Factors

The first implementation should prioritize a small, auditable factor set.

Recommended starting factors:

1. League-adjusted projected fantasy value
2. Value over replacement
3. Draft tier and tier drop-off
4. ADP relative to current pick
5. Next-pick availability
6. Expected value lost by waiting
7. Basic roster fit
8. Position eligibility and scarcity
9. Injury, role, and minutes risk
10. Projection-source agreement

Additional factors should be added only when they improve real draft decisions and can be evaluated historically.

---

# Decision Rule for New Factors

Before adding a factor, ask:

> Does this factor provide distinct information that can materially improve a draft recommendation?

If the answer is no, it should not be added.

A new factor should also have:

- A clear definition
- A reliable data source
- A documented calculation
- A known relationship to the recommendation
- A plan for historical evaluation

---

# Architectural Direction

The backend should treat recommendation generation as a pipeline rather than a single opaque service.

Suggested conceptual components:

- Context Builder
- Eligibility Filter
- Projection Evaluator
- Market Evaluator
- Roster Fit Evaluator
- Risk Evaluator
- Opportunity-Cost Evaluator
- Candidate Comparator
- Recommendation Selector
- Confidence Assessor
- Explanation Builder
- Recommendation Recorder

These are conceptual boundaries.

They may be implemented more simply in Version 1 while preserving separation of responsibilities.

---

# Final Principle

Fantasy GM should produce a recommendation that Admin can inspect, challenge, and improve.

The system is successful when it can answer:

> Why was this the best pick at that moment?

with stored data, structured reasoning, and no invented explanation.
