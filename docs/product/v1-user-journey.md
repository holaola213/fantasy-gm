# V1 User Journey

## Purpose

This document describes the complete user experience for Fantasy GM
Version 1.

It intentionally focuses on **what the user experiences**, not how the
software is implemented.

The goal is to ensure the architecture exists to support the
product---not the other way around.

------------------------------------------------------------------------

# Primary User

-   Admin
-   One ESPN fantasy basketball league
-   One active NBA fantasy basketball draft

------------------------------------------------------------------------

# User Goal

The user wants to answer one question throughout the draft:

> **Who should I draft next?**

Fantasy GM exists to provide the best possible answer.

------------------------------------------------------------------------

# Product Philosophy

Fantasy GM is a decision support system.

It does not make draft picks.

It provides transparent recommendations that help the user make better
decisions.

Every recommendation should answer four questions:

1.  What should I do?
2.  Why?
3.  How confident are you?
4.  What happens if I don't?

------------------------------------------------------------------------

# User Journey

## Step 1 --- Open Fantasy GM

The user launches Fantasy GM.

Fantasy GM synchronizes with the connected ESPN league.

The application verifies:

-   League connection
-   Draft status
-   Current draft pick
-   Available players

If synchronization fails, Fantasy GM informs the user before generating
recommendations.

------------------------------------------------------------------------

## Step 2 --- League Overview

Fantasy GM displays:

-   League name
-   Draft status
-   Current pick number
-   Current roster
-   Remaining roster slots
-   League scoring settings

The user should immediately understand the current draft state.

------------------------------------------------------------------------

## Step 3 --- Draft Dashboard

This is the primary screen of Version 1.

Fantasy GM displays one primary recommendation.

### Recommended Pick

Display:

-   Player
-   Team
-   Position
-   Confidence
-   Expected Season Value
-   Draft Tier

### Why This Player?

Fantasy GM explains the reasoning in plain English.

### Alternative Recommendations

Fantasy GM displays two or three alternatives with a short explanation.

------------------------------------------------------------------------

## Step 4 --- Player Details

Selecting a player opens a detailed analysis including:

-   Player overview
-   Season projection
-   Risk assessment
-   Draft analysis

------------------------------------------------------------------------

## Step 5 --- Draft Decision

The user makes the draft selection inside ESPN.

Fantasy GM never submits picks automatically.

Fantasy GM records:

-   Pick number
-   Selected player
-   Recommendation
-   Confidence
-   Reasoning
-   Timestamp

------------------------------------------------------------------------

## Step 6 --- Draft Updates

After every completed pick, Fantasy GM synchronizes and recalculates
recommendations.

------------------------------------------------------------------------

## Step 7 --- Draft Complete

Fantasy GM displays a draft summary including:

-   Final roster
-   Team strengths
-   Team weaknesses
-   Biggest values
-   Biggest reaches
-   Overall draft confidence

------------------------------------------------------------------------

# User Experience Principles

-   One primary recommendation
-   Confidence is always visible
-   Explain every recommendation
-   Minimize cognitive load
-   Never hide uncertainty

------------------------------------------------------------------------

# Version 1 Boundaries

Excluded:

-   Waiver recommendations
-   Trade analysis
-   Matchup analysis
-   Streaming recommendations
-   Notifications
-   Opportunity monitoring
-   Chat assistant
-   Multiple leagues
-   Yahoo support
-   Sleeper support

------------------------------------------------------------------------

# Success Criteria

Fantasy GM becomes the primary draft companion and provides
understandable, trustworthy recommendations throughout the draft.
