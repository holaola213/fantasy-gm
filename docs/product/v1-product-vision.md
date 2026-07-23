---
title: V1 Product Vision
version: 1.0
status: Approved
owner: Admin
last_updated: 2026-07-23
---

# Fantasy GM V1 Product Vision

## Purpose

Fantasy GM Version 1 exists to help a single fantasy basketball manager make better draft decisions for one ESPN league.

It is not intended to be a complete fantasy basketball platform. It is the first product implementation of the broader Fantasy GM architecture and serves as the foundation for future regular-season decision support.

The immediate goal is to provide trustworthy, explainable draft recommendations that are useful during preseason preparation and a live fantasy draft.

---

# Target User

- One user: Admin
- One ESPN fantasy basketball league
- One NBA fantasy season
- One desktop-first workflow

Future versions may support additional users, leagues, and platforms, but Version 1 intentionally optimizes for a single real-world league.

---

# Current Product Focus

Fantasy GM should follow the fantasy basketball calendar.

For Version 1, the current focus is:

> Draft Intelligence

After the season begins, the product focus will shift toward:

- Waiver and free-agent analysis
- Matchup analysis
- Streaming decisions
- Trade evaluation

Those regular-season capabilities are not part of the current V1 implementation scope.

---

# Core Product Promise

> When preparing for or participating in a fantasy basketball draft, Fantasy GM identifies the best available players, explains why they are recommended, and communicates the confidence and tradeoffs behind each recommendation.

Every recommendation should answer four questions:

1. What should I do?
2. Why should I do it?
3. How confident is Fantasy GM?
4. What is the cost of waiting or choosing another player?

---

# Product Identity

Fantasy GM is a decision-support system.

It is not:

- A generic fantasy basketball website
- A chatbot that invents opinions
- A simple player ranking list
- A fully automated draft bot
- A public multi-user platform

It should help Admin decide, not make decisions on Admin's behalf.

---

# Guiding Principles

## Explainability First

Every recommendation must include understandable reasoning.

The product should never ask the user to trust a black box.

---

## One Primary Recommendation

Fantasy GM should present one clear recommended action.

Alternatives may be shown for context, but they should support the primary recommendation rather than compete with it.

---

## Confidence Matters

Every recommendation should communicate confidence.

Confidence reflects the strength and consistency of the supporting evidence. It does not replace the recommendation itself.

---

## Draft Context Matters

The best player in a general ranking is not always the best player for the current pick.

Recommendations should consider:

- League scoring settings
- Current roster construction
- Position eligibility
- Draft tier
- Expected availability at the next pick
- Projection quality
- Role and injury uncertainty

---

## Quality Over Quantity

Fantasy GM should reduce decision-making effort.

It should show the most important information first and allow deeper analysis when needed.

---

## Data Before Intelligence

Recommendations should be based on data that is available, attributable, and timestamped.

Whenever possible, Fantasy GM should preserve:

- Source data
- Projection inputs
- Recommendation output
- Confidence
- Explanation
- Draft state
- Timestamp

This historical record will support future evaluation and improvement.

---

## Architecture Supports the Future; Product Ships the Present

The architecture may support long-term capabilities such as waivers, trades, matchup analysis, and opportunity detection.

Version 1 should implement only what is necessary to deliver excellent draft intelligence for one league and one user.

---

# V1 Experience

The expected Version 1 workflow is:

1. Admin opens Fantasy GM.
2. Fantasy GM loads the connected ESPN league and scoring settings.
3. Fantasy GM displays the current draft state.
4. Fantasy GM recommends the best available player.
5. Admin reviews the explanation, confidence, and alternatives.
6. Admin makes the pick in ESPN.
7. Fantasy GM records the decision and recalculates after the draft board changes.
8. Fantasy GM produces a post-draft summary.

---

# Included Product Capabilities

Version 1 includes:

- One ESPN league connection
- League scoring and roster settings
- Draft board
- Available-player tracking
- Best-available recommendation
- Alternative recommendations
- Player analysis
- Projection and value display
- Draft tier display
- Risk summary
- Confidence display
- Recommendation explanation
- Draft history
- Post-draft summary

The detailed implementation boundary is defined in `v1-feature-scope.md`.

---

# Explicitly Deferred

The following are intentionally deferred:

- Waiver recommendations
- Free-agent monitoring
- Matchup analysis
- Streaming recommendations
- Trade analysis
- Lineup optimization
- Push notifications
- Discord integration
- Background monitoring
- Multiple leagues
- Multiple users
- Yahoo support
- Sleeper support
- Mobile application
- Dynasty support
- Machine learning models
- LLM-generated decisions
- Automated ESPN draft picks

These items belong in the future roadmap.

---

# Success Criteria

Fantasy GM Version 1 is successful if:

- It becomes Admin's primary draft-preparation and live-draft companion.
- It consistently produces a clear recommended pick.
- Every recommendation is understandable.
- Confidence and uncertainty are communicated honestly.
- League-specific scoring meaningfully affects rankings.
- Draft context meaningfully affects recommendations.
- Historical recommendations and selections are recorded.
- The application remains usable under live draft time pressure.
- Future regular-season features can be added without redesigning the core architecture.

Success is measured by trust and usefulness, not feature count.

---

# Scope Decision Rule

Before adding any feature to Version 1, ask:

> Does this directly improve Admin's ability to make a better draft decision in the current ESPN league?

If the answer is no, the feature should be deferred.

---

# Relationship to Other Product Documents

- `v1-user-journey.md` defines how Admin experiences the product.
- `v1-feature-scope.md` defines what is included and excluded.
- `ui-wireframes.md` will define the initial screen structure and information hierarchy.
- `future-roadmap.md` will capture intentionally deferred capabilities.
