# Fantasy GM — Data Source Feasibility: ESPN and NBA.com

**Phase:** -1  
**Status:** Research finding; architecture decisions proposed but not yet accepted  
**Date:** July 23, 2026

---

## 1. Research Question

Can ESPN and NBA.com provide the foundational data needed for Fantasy GM, and how should the system protect itself from their limitations?

---

## 2. Executive Conclusion

Fantasy GM should use the two sources for different purposes:

- **NBA.com / `nba_api`: basketball-performance source**
- **ESPN fantasy endpoints / `espn_api`: league-state and market-context source**

Neither source should become Fantasy GM's internal domain model.

Both sources expose interfaces that can change without contractual notice. Therefore, each must be isolated behind an adapter, cached locally, validated at ingestion, and mapped into canonical Fantasy GM records.

---

# 3. NBA.com / `nba_api`

## Intended Role

Primary candidate for:

- Player and team identifiers
- Historical player statistics
- Game logs
- Box scores
- Advanced statistics
- Player and team reference data
- Live scoreboard data
- Potential play-by-play and tracking-derived features

## Confirmed Capabilities

The `nba_api` project exposes NBA.com statistics and live data through Python endpoint classes. It supports JSON, dictionaries, and optional pandas DataFrame output.

The project includes:

- Official-stats endpoints
- Live-data endpoints
- Static player and team datasets
- Endpoint documentation
- Proxy, custom-header, and timeout options
- Integration and unit testing infrastructure

## Strengths

1. Broad statistical coverage
2. Python-native access
3. Mature open-source project
4. Extensive endpoint mapping
5. Static player and team lookup data
6. Historical and game-level inputs suitable for feature engineering
7. MIT-licensed client library

## Risks

### A. NBA.com does not publish a stable API contract

The `nba_api` maintainers explicitly note that NBA.com does not provide information about new, changed, or removed endpoints.

### B. Endpoints can disappear or change behavior

A November 2025 release removed two endpoints because NBA.com stopped supporting them. Other endpoints were restored after being mistakenly considered retired, and parameter behavior changed as NBA.com became stricter.

### C. Multiple requests may time out

A February 2026 issue reports code that worked days earlier timing out on the second sequential request. This is not definitive proof of a formal rate limit, but it demonstrates operational instability.

### D. Returned schemas may change

The project added integration validation specifically to catch response-structure changes.

### E. NBA.com terms still govern the underlying data

The client library is MIT-licensed, but that does not make the upstream NBA.com data unrestricted.

## Feasibility Rating

| Dimension | Rating |
|---|---:|
| Statistical breadth | High |
| Historical utility | High |
| Python integration | High |
| Documentation | Medium-High |
| Stability | Medium-Low |
| Contractual reliability | Low |
| Cost | Free |
| Dependency risk | Medium-High |

## Preliminary Recommendation

**Adopt as the initial basketball-statistics source, with safeguards.**

Required safeguards:

- Adapter interface
- Local raw-response cache
- Request throttling
- Retry with exponential backoff
- Explicit timeouts
- Schema validation
- Endpoint health checks
- Source timestamp
- Ingestion version
- Fallback or replaceability plan
- Tests based on recorded fixtures rather than live API calls alone

---

# 4. ESPN Fantasy Data

## Intended Role

Primary candidate for:

- League settings
- Custom scoring rules
- Teams and rosters
- Draft results
- Matchups and standings
- Transactions and recent activity
- Player ownership and availability
- ESPN fantasy projections
- ESPN rankings or market signals, where exposed
- Fantasy eligibility and position data
- Schedule and roster-state context inside the user's league

## Confirmed Capabilities

The `espn_api` package supports public and private ESPN fantasy football and basketball leagues.

For private leagues it requires:

- League ID
- Season
- `SWID` cookie
- `espn_s2` cookie

Community documentation maps ESPN league views such as:

- Team
- Roster
- Matchup
- Matchup score
- Settings
- Draft detail
- Scoreboard
- Standings
- Status
- Player information

## Strengths

1. Directly reflects the user's actual league
2. Supports custom league settings
3. Supports roster, matchup, draft, and standings context
4. Community wrapper reduces initial reverse-engineering work
5. Essential for measuring value relative to ESPN's market
6. Can expose information unavailable from general NBA statistics

## Risks

### A. The fantasy API is undocumented

The community projects themselves describe the endpoints as undocumented.

### B. Private-league authentication uses browser cookies

`SWID` and `espn_s2` are sensitive session credentials and must never be committed to Git.

### C. Authentication can break

Community issues document access-denied and cookie-format problems.

### D. ESPN can change endpoints, fields, or views

There is no public compatibility guarantee for these fantasy interfaces.

### E. Historical market data may be incomplete

Current league data may be accessible while historical ADP, rankings, projections, or ownership snapshots are difficult to reconstruct after the fact.

### F. Wrapper support can lag ESPN changes

A wrapper may be maintained and still temporarily fail when ESPN modifies its responses.

## Feasibility Rating

| Dimension | Rating |
|---|---:|
| League-specific value | Very High |
| Draft and roster context | High |
| Market-signal potential | High |
| Historical market coverage | Unknown / likely limited |
| Documentation | Medium-Low |
| Stability | Low-Medium |
| Authentication simplicity | Medium-Low |
| Cost | Free |
| Dependency risk | High |

## Preliminary Recommendation

**Adopt as the initial league-state adapter, but do not make it a core domain dependency.**

Required safeguards:

- `EspnLeagueAdapter`
- Environment variables for credentials
- `.env` excluded by `.gitignore`
- No cookies in logs, fixtures, screenshots, or documentation
- Raw response snapshots with secrets stripped
- Schema validation
- Cache last successful league sync
- Graceful degraded mode when ESPN is unavailable
- Separate ESPN player IDs from canonical player IDs
- Explicit season and league identifiers on every record
- Integration tests that can be skipped when credentials are unavailable

---

# 5. Proposed Responsibility Boundary

## NBA.com owns

- Basketball performance
- Historical statistics
- Games
- Box scores
- Team and player reference information
- Advanced statistical inputs

## ESPN owns

- User's fantasy league
- League configuration
- Draft state
- Fantasy rosters
- Matchups
- Transactions
- Ownership and availability
- ESPN market signals

## Fantasy GM owns

- Canonical player identity
- Scoring calculations
- Feature engineering
- Projections
- Confidence
- Risk
- Replacement level
- Market comparison
- Recommendation logic
- Explanations
- Evaluation history

---

# 6. Canonical Data Principle

Fantasy GM should never pass raw ESPN or NBA objects throughout the application.

Instead:

```text
NBA response ──> NbaStatsAdapter ──┐
                                   ├──> Canonical Fantasy GM records
ESPN response ─> EspnLeagueAdapter ─┘
```

Example identity record:

```text
CanonicalPlayer
- fantasy_gm_player_id
- full_name
- normalized_name
- nba_player_id
- espn_player_id
- current_team_id
- active_status
- identity_confidence
- source_mappings
```

Source-specific fields remain traceable, but the rest of the system depends on the canonical record.

---

# 7. Historical Data Concern

The largest unresolved issue is not current NBA statistics.

It is **historical fantasy-market data**.

Fantasy GM eventually needs time-stamped versions of:

- ESPN rankings
- ESPN projections
- ADP
- Ownership percentage
- Roster percentage
- Injury designations
- News and role expectations

Without historical snapshots, the system cannot honestly backtest whether it identified an inefficiency using only information available at the time.

## Implication

Once Fantasy GM begins operating, it should capture market snapshots regularly rather than assuming they can be reconstructed later.

This creates a likely future requirement:

> The ingestion system must preserve what ESPN and other sources believed at each point in time.

---

# 8. Proposed Decisions

## Proposed ADR-002

**External data sources must be accessed through replaceable adapters.**

Rationale:

- Both primary sources are operationally unstable.
- ESPN is undocumented.
- NBA.com changes endpoints without formal notice.
- The system should survive replacing either source.

## Proposed ADR-003

**Fantasy GM owns a canonical player identity independent of ESPN and NBA.com.**

Rationale:

- ESPN and NBA IDs differ.
- Names change and collide.
- Team changes complicate matching.
- Future sources will introduce more identifiers.

## Proposed ADR-004

**Historical source snapshots are first-class data, not disposable API responses.**

Rationale:

- Decision backtesting requires information as it existed at prediction time.
- Revised current data cannot recreate historical beliefs.
- Market-value evaluation depends on timestamped baselines.

These decisions should be reviewed after the remaining data sources are investigated.

---

# 9. Open Questions

1. Which exact `nba_api` endpoints provide all fields needed for Version 1?
2. How far back can each required NBA endpoint be queried consistently?
3. Can ESPN expose historical draft-day rankings and projections?
4. Does ESPN expose reliable ownership and availability snapshots?
5. How frequently should Fantasy GM capture ESPN market data?
6. How long do ESPN authentication cookies remain valid?
7. Can public league access cover development and automated testing?
8. Which source should define fantasy position eligibility?
9. How should duplicate names and renamed players be resolved?
10. What data may be redistributed in a public GitHub repository?
11. Should raw responses be stored locally but excluded from Git?
12. What fallback source should be considered if NBA.com becomes unusable?

---

# 10. Immediate Next Research

The next data-source investigation should target the hardest missing categories:

1. Historical ESPN rankings, projections, and ADP
2. Injuries and availability
3. NBA schedules
4. Transactions and roster changes
5. News, coach quotes, and role context
6. Player identity reconciliation

The highest-priority question is:

> Can Fantasy GM obtain historical market expectations, or must it build that dataset prospectively?

---

# 11. Sources

- `nba_api` repository and documentation  
  https://github.com/swar/nba_api
- `nba_api` releases  
  https://github.com/swar/nba_api/releases
- `nba_api` issue #633  
  https://github.com/swar/nba_api/issues/633
- `espn-api` repository  
  https://github.com/cwendt94/espn-api
- `espn-api` wiki  
  https://github.com/cwendt94/espn-api/wiki
- Public ESPN endpoint mapping  
  https://github.com/pseudo-r/Public-ESPN-API

---

# 12. What Fantasy GM Learned

> Data sources are replaceable evidence providers. Fantasy GM—not ESPN, NBA.com, or a wrapper library—must own player identity, scoring, historical truth, and decision logic.
