# Fantasy GM — Phase -1 Research Charter

**Status:** Active  
**Started:** July 23, 2026  
**Purpose:** Establish the evidence, constraints, and evaluation framework required before designing or implementing Fantasy GM.

---

## 1. Research Objective

Fantasy GM is a fantasy basketball decision-support system designed primarily for an ESPN total-points league.

The project will not optimize solely for projection accuracy. Its broader goal is to improve decisions relative to the available fantasy market by identifying players whose expected value, risk, opportunity, or roster fit differs materially from ESPN rankings, ADP, projections, or league consensus.

### Primary question

> How can Fantasy GM make better draft, waiver, trade, lineup, and streaming decisions than a manager relying only on ESPN information?

---

## 2. Known League Context

The initial implementation is designed around:

- ESPN Fantasy Basketball
- 12-team total-points league
- Custom scoring:
  - FGM: +1
  - FGA: -1
  - FTM: +1
  - FTA: -1
  - REB: +1
  - AST: +1
  - STL: +2
  - BLK: +2
  - TO: -1
- Maximum of four centers
- One acquisition per day
- Eight-team playoffs
- One-week playoff matchups
- No playoff byes

These rules are product requirements, not implementation details. They affect player value, scarcity, replacement level, schedule value, roster construction, and transaction strategy.

---

## 3. Phase -1 Deliverables

Phase -1 ends when the project has evidence-backed answers—or explicitly documented uncertainty—for the following areas:

1. Existing fantasy basketball and NBA prediction projects
2. Data sources and access risks
3. Fantasy-value definitions
4. Projection architecture
5. Confidence and uncertainty
6. Evaluation methodology
7. Market baselines
8. Decision-quality metrics
9. Explainability requirements
10. Initial system scope

No production implementation should begin until the foundational decisions are documented.

---

## 4. Research Tracks

### Track A — Existing Projects

For each relevant project, record:

- Project goal
- Fantasy format
- Data sources
- Architecture
- Prediction target
- Features
- Models or rules
- Evaluation method
- Strengths
- Weaknesses
- Ideas to adopt
- Ideas to avoid
- Maintenance status

### Track B — Data Sources

Evaluate each source for:

- Available fields
- Historical depth
- Update frequency
- Player identifiers
- Reliability
- Authentication requirements
- Rate limits
- Cost
- Terms and access risk
- Ease of backfilling
- Ease of reproducibility
- Dependency risk

Initial candidates:

- NBA.com statistics through `nba_api`
- ESPN fantasy-league data through unofficial endpoints or wrappers
- ESPN rankings, projections, ownership, and ADP where accessible
- NBA schedules
- Injury and transaction sources
- News and role-context sources
- Optional commercial providers

### Track C — Projection Design

Research whether season and in-season projections should be decomposed into components such as:

- Minutes
- Games played
- Per-minute production
- Usage and role
- Team environment
- Availability
- Schedule volume

A decomposed model is preferred as a hypothesis because it is more explainable and makes errors easier to diagnose. It is not yet an approved architecture decision.

### Track D — Confidence

Determine how uncertainty should be represented.

Candidate components:

- Sample size
- Role stability
- Coaching continuity
- Team continuity
- Injury history and recovery
- Rookie status
- Rotation competition
- Projection-source disagreement
- Model residual uncertainty
- News ambiguity
- Data freshness

Research must distinguish:

- Projection
- Risk
- Confidence
- Upside/downside range

These concepts must not be collapsed into one score without justification.

### Track E — Evaluation

Fantasy GM must use time-respecting evaluation.

Random train/test splits can leak future information into past predictions. Candidate evaluation methods include rolling-origin or walk-forward validation.

Evaluation should eventually cover:

- Projection error
- Ranking quality
- Calibration
- Market outperformance
- Draft value
- Waiver value
- Transaction regret
- Roster constraint handling
- Decision quality by confidence band

### Track F — Market Baselines

Fantasy GM needs explicit baselines.

Candidate baselines:

- ESPN projected fantasy points
- ESPN rankings
- ESPN ADP
- Previous-season fantasy points
- Recent rolling averages
- Consensus projections
- Replacement-level ranking
- Simple age and minutes heuristics

A sophisticated model is only valuable if it beats simple alternatives.

---

## 5. Initial Landscape Findings

### Finding 1 — Many public projects begin with direct prediction

Several public projects attempt to predict fantasy points, PPG, game outcomes, or category value directly with models such as Random Forest, XGBoost, neural networks, boosting, and linear regression.

**Implication:** Fantasy GM should study these projects, but should not assume direct fantasy-point prediction is the best first architecture.

### Finding 2 — Existing projects often combine data acquisition, modeling, and UI tightly

Public repositories commonly package scraping, notebooks, model training, and a web interface together.

**Implication:** Fantasy GM should separate ingestion, canonical data models, features, rules, projections, evaluation, and presentation.

### Finding 3 — Stronger models do not automatically beat simpler systems

One NBA prediction project reported that its Elo-based approach outperformed its tested machine-learning models.

**Implication:** Every advanced method must be compared against simple, interpretable baselines.

### Finding 4 — Time-aware validation is mandatory

Forecasting references and scikit-learn documentation warn that ordinary cross-validation can train on future observations and evaluate on earlier observations. Rolling-origin or time-series splits preserve temporal order.

**Implication:** Walk-forward evaluation is a likely project requirement.

### Finding 5 — ESPN access is possible but unofficial

Community projects expose ESPN fantasy-basketball league data, including public and private leagues, but these integrations depend on undocumented APIs.

**Implication:** ESPN should be treated as a replaceable adapter with monitoring, caching, and fallback plans—not as the canonical internal model.

### Finding 6 — NBA.com data is accessible through a maintained Python client

The `nba_api` package provides access to NBA.com statistics and documents player, team, game, and endpoint access.

**Implication:** It is a strong initial candidate for historical and current NBA statistics, subject to reliability and usage testing.

### Finding 7 — Points leagues require a different research path than category leagues

Published fantasy-basketball work on G-score and H-scoring addresses uncertainty and dynamic strategy primarily in category formats.

**Implication:** The strategic ideas may transfer, but Fantasy GM cannot import category-league valuation methods directly into the user's custom points league.

---

## 6. Working Hypotheses

These are not decisions.

1. Player value should be decomposed into talent, opportunity, availability, schedule, scarcity, and market price.
2. Minutes and games played may matter more than marginal improvements in per-minute prediction.
3. ESPN should represent the market baseline, not ground truth.
4. Confidence should be separate from expected value.
5. Recommendations should retain machine-readable reason codes.
6. Source data should map into one canonical player identity.
7. Evaluation should simulate decisions using only information available at that historical moment.
8. The first useful system may be rules plus blended projections rather than machine learning.
9. League rules should be configuration, not embedded assumptions.
10. The project should measure whether recommendations beat ESPN, not merely whether projections have low RMSE.

---

## 7. Open Questions

### Product

- What is the smallest useful Draft GM?
- Is the first output a ranking table, draft assistant, player card, or report?
- Which decisions must Version 1 support?
- How much manual information entry is acceptable?

### Data

- Can historical ESPN ADP and projections be acquired reliably?
- Which source provides dependable historical injuries and roles?
- How should player IDs be reconciled across NBA and ESPN?
- Which data can legally and reliably be stored in the repository?
- How should revisions and late stat corrections be handled?

### Modeling

- Should season projections use minutes × per-minute production × games played?
- How should rookies and players with limited NBA samples be handled?
- How should coaching and roster changes enter projections?
- How should correlation between availability and per-game production be handled?
- Should projections be probabilistic from the beginning?

### Evaluation

- What is the primary decision-quality metric?
- How can draft recommendations be backtested against historical ADP?
- How should replacement level account for the four-center limit?
- How should schedule value be measured under a one-add-per-day rule?
- What qualifies as a successful recommendation?

### Confidence

- Is confidence a calibrated probability, a reliability score, or both?
- How should source disagreement affect confidence?
- How should qualitative news be scored without creating false precision?
- What evidence is required before a manual confidence weight becomes data-driven?

---

## 8. Research Standards

Every research document should distinguish:

- **Fact:** supported by a cited source or observed data
- **Finding:** interpretation supported by facts
- **Hypothesis:** plausible idea requiring testing
- **Decision:** approved project direction
- **Open question:** unresolved
- **Rejected idea:** evaluated and declined, with reasoning

Every source should be assessed for:

- Authority
- Recency
- Reproducibility
- Applicability to the user's league
- Limitations
- Dependency risk

---

## 9. Phase -1 Exit Criteria

Phase -1 is complete when:

- The main data sources have been tested or rejected.
- The market baseline is defined.
- The target decisions for Version 1 are defined.
- The initial projection decomposition is chosen.
- Confidence terminology is defined.
- Historical evaluation methodology is chosen.
- Player identity requirements are known.
- Major architecture decisions are ready for ADRs.
- The scope of Phase 0 can be written without guessing.

---

## 10. Immediate Research Sequence

1. **Existing-project landscape**
   - Review representative projects in depth.
   - Create a comparison matrix.
2. **Data-source feasibility**
   - ESPN
   - NBA.com / `nba_api`
   - schedules
   - injuries
   - news
   - historical market data
3. **Evaluation framework**
   - define baselines
   - define walk-forward simulation
   - define decision metrics
4. **Projection decomposition**
   - minutes
   - rates
   - availability
   - schedule
5. **Confidence framework**
6. **Phase -1 synthesis and ADR candidates**

---

## 11. Initial Source Register

- scikit-learn, `TimeSeriesSplit`
  - https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html
- Forecasting: Principles and Practice, time-series cross-validation
  - https://otexts.com/fpp3/tscv.html
- `nba_api`
  - https://github.com/swar/nba_api
- `espn-api`
  - https://github.com/cwendt94/espn-api
- Public ESPN API mapping
  - https://github.com/pseudo-r/Public-ESPN-API
- Improving Algorithms for Fantasy Basketball
  - https://arxiv.org/abs/2307.02188
- Dynamic Quantification of Player Value for Fantasy Basketball
  - https://arxiv.org/abs/2409.09884
- Representative public projects:
  - https://github.com/KengoA/fantasy-basketball
  - https://github.com/iocak28/Fantasy_Basketball_ML
  - https://github.com/wfordh/ottobasket_values
  - https://github.com/luke-lite/NBA-Prediction-Modeling

---

## 12. What Fantasy GM Learned

> Before choosing a model, Fantasy GM must define the decision it is trying to improve, the market baseline it must beat, and a historical evaluation that prevents future information from leaking into past decisions.
