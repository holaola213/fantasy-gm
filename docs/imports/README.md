# Projection Imports

Projection imports turn a provider CSV into a persisted immutable projection
snapshot that Fantasy GM can use for valuations, recommendations, and draft
assistant context.

Always preview first:

```powershell
docker compose run --rm backend python -m app.projections.import_csv `
  --path docs/imports/example_projection.csv `
  --source example `
  --source-name "Example Provider" `
  --season 2026 `
  --as-of-date 2026-10-08 `
  --preview
```

Import after the preview is ready:

```powershell
docker compose run --rm backend python -m app.projections.import_csv `
  --path docs/imports/example_projection.csv `
  --source example `
  --source-name "Example Provider" `
  --season 2026 `
  --as-of-date 2026-10-08
```

Add `--activate` to make the imported set active for the same source, season,
and projection type:

```powershell
docker compose run --rm backend python -m app.projections.import_csv `
  --path docs/imports/example_projection.csv `
  --source example `
  --source-name "Example Provider" `
  --season 2026 `
  --as-of-date 2026-10-08 `
  --activate
```

Preview performs CSV parsing, normalization, validation, source lookup, player
identity lookup, exact-name fallback analysis, new-player detection, eligibility
comparison, and projected count calculation. Preview is read-only. It does not
create sources, players, identities, eligibility rows, projection sets,
projection rows, or activation changes.

Successful import recalculates the plan and persists the full snapshot in one
database transaction. Failed imports roll back all writes.

## CSV Contract

Input must be UTF-8. UTF-8 with BOM is supported. CRLF and LF line endings,
quoted CSV values, reordered columns, blank physical lines, surrounding
whitespace in headers and values, and empty optional fields are supported.

Required columns:

- `player_id`
- `full_name`
- `games`
- `minutes_per_game`
- `fgm`
- `fga`
- `ftm`
- `fta`
- `rebounds`
- `assists`
- `steals`
- `blocks`
- `turnovers`

Optional columns:

- `team`
- `primary_position`
- `positions`
- `is_active`

Headers are trimmed and compared case-insensitively. Unknown extra columns are
ignored and reported as preview/import warnings. No broad user-defined column
mapping or alias system exists in this version.

The supported position keys are `PG`, `SG`, `SF`, `PF`, and `C`. `positions`
accepts comma, `/`, or `|` separators. If `positions` is empty and
`primary_position` is present, eligibility defaults to the primary position. Both
`positions` and `primary_position` may be empty; in that case no
`PlayerEligibility` rows are created for that player. For an existing resolved
player, the latest successful import replaces current eligibility, so an empty
resolved eligibility set removes previous eligibility.

Numeric projection fields are parsed as Python `Decimal` values and persisted as
PostgreSQL `NUMERIC`. Binary floating-point parsing is not used. Percent columns
are not part of the current schema; field-goal and free-throw scoring uses made
and attempted counts.

## Identity And Eligibility

Provider identity is local to the source. `(source, player_id)` is authoritative.
`player_id` values are trimmed, stored case-sensitively, and treated as opaque
provider-local identifiers.

If an identity does not exist, the importer attempts exact full-name fallback:
zero exact matches create a new player, one exact match reuses that player, and
multiple exact matches fail with a controlled validation diagnostic.

Projection snapshots are immutable. A successful import always creates a new
`ProjectionSet` and new `PlayerProjection` rows. Historical projection rows are
not overwritten.

Current player metadata and eligibility are mutable. The latest successful
resolved import updates the player name, team, primary position, active flag,
and replaces current eligibility for that player. Obsolete eligibility positions
are removed, missing positions are inserted, unchanged positions are preserved,
and failed imports roll back eligibility changes.

Drafts persist their `projection_set_id`. A draft never silently switches to a
newly activated projection set.

## Row Counts

`rows_read` means nonblank CSV data rows after the header. The header row is not
counted. Completely blank physical lines are not counted. Rows that contain any
non-whitespace field are counted, even if validation later rejects them.

## CLI Exit Behavior

- Ready preview: exit code 0.
- Successful import: exit code 0.
- User-correctable validation or ambiguous matching failure: exit code 1 with
  structured diagnostics and no Python traceback.
- Unexpected internal or database failures are not swallowed.

## Troubleshooting

- `missing_required_column`: add the documented required header.
- `invalid_number`: use decimal numeric text such as `31.25`.
- `non_finite_number`: replace `NaN`, `Infinity`, or `-Infinity` with a finite
  decimal value.
- `unknown_position`: use only `PG`, `SG`, `SF`, `PF`, and `C`.
- `malformed_row`: remove extra fields that do not have matching headers.
- `duplicate_provider_player_id`: remove IDs that match after trimming.
- `ambiguous_exact_name_match`: import a stable provider `player_id` for that
  player or resolve duplicate local player names before importing.
