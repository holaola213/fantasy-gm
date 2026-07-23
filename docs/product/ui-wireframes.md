---
title: UI Wireframes
version: 1.0
status: Draft
owner: Admin
last_updated: 2026-07-23
---

# UI Wireframes

## Purpose

This document defines the high-level layout of each major screen in Fantasy GM Version 1.

These are functional wireframes—not visual designs.

---

# Design Principles

- Recommendation first
- Dense, information-rich layout
- Desktop-first
- Designed for one expert user
- Use standard fantasy terminology where possible
- Minimize clicks during a live draft

---

# Screen 1 — Draft Dashboard (Primary Screen)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Fantasy GM                  League: ESPN Points       Round 4 • Pick 38      │
│ Sync: ✓                     Timer: 0:47                                   │
├──────────────────────────────────────────────────────────────────────────────┤
│ RECOMMENDATION                                                       88%     │
│ Jaren Jackson Jr. (PF/C)                                                High │
│                                                                              │
│ Projected FP: 3412     Tier: 3     ADP: 42.6     Risk: Moderate              │
│ VOR: +186              Roster Fit: 84      Next-Pick Availability: 21%       │
│                                                                              │
│ Why                                                                         │
│ • Highest projected value remaining                                         │
│ • Tier drop after this pick                                                 │
│ • Fits current roster                                                       │
│                                                                              │
│ [Player Details] [Compare]                                                  │
├──────────────────────────────┬───────────────────────────────────────────────┤
│ Alternatives                 │ Your Team                                    │
│ 1. Bam Adebayo               │ PG Curry                                     │
│ 2. Darius Garland            │ SG Booker                                    │
│ 3. Dejounte Murray           │ SF ...                                       │
│                              │ PF ...                                       │
│                              │ C  ...                                       │
├──────────────────────────────┴───────────────────────────────────────────────┤
│ Available Players (search, sort, filter)                                   │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

# Screen 2 — Player Details

Displays:

- Basic information
- Season projection
- Fantasy projections
- Risk assessment
- ADP history (future)
- Comparable players
- Draft recommendation notes

Opens as a side panel without leaving the dashboard.

---

# Screen 3 — Player Comparison

Compare two or more players.

Columns include:

- Projected Fantasy Points
- VOR
- Tier
- ADP
- Risk
- Position Eligibility
- Roster Fit
- Recommendation Confidence

---

# Screen 4 — Draft Summary

Displays:

- Final roster
- Position balance
- Biggest values
- Biggest reaches
- Team strengths
- Team weaknesses
- Recommendation accuracy log

---

# Screen 5 — Settings

Displays:

- ESPN connection
- League settings
- Projection source configuration
- Custom scoring verification
- Refresh options

---

# Notes

The dashboard is the primary screen of Version 1.

Every other screen should support faster, better draft decisions rather than distract from them.
