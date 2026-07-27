# Bootstrap Projection Generator

The Basketball Reference SPS bootstrap generator exists only to exercise Fantasy
GM with real basketball-shaped data. It is not permanent Basketball Reference
support, not a player registry redesign, and not Fantasy GM's long-term
projection model.

Fantasy GM's long-term vision is to generate its own projections. External
datasets are bootstrap inputs and possible future comparison sources.

## Architecture

The bootstrap flow keeps the existing projection-provider and import
architecture intact:

```text
Basketball Reference SPS CSV + Basketball Reference player metadata CSV
-> bootstrap parsers
-> source_player_id join
-> fixed assumption generator
-> ProjectionPlayer
-> ProjectionImportService preview
-> ProjectionImportService atomic import
-> immutable ProjectionSet
```

The recommendation engine is not changed. It reads persisted projection sets as
usual.

## Input

The expected local raw input is:

```text
data/raw/basketball_reference/basketball_reference_sps_2027.csv
data/raw/basketball_reference/basketball_reference_player_metadata_2027.csv
```

This checkout also supports the flat bootstrap path:

```text
data/raw/basketball_reference_sps_2027.csv
data/raw/basketball_reference_player_metadata_2027.csv
```

Raw files are read-only bootstrap inputs and are ignored by Git.

The SPS file provides per-36 statistical projections and the Basketball
Reference player ID. It does not include team or position metadata. The
metadata file supplies the development-only team, primary position, and
eligibility positions needed by valuation and draft workflows:

```text
source_player_id,player_name,team,primary_position,positions
jokicni01,Nikola Jokic,DEN,C,C
gilgesh01,Shai Gilgeous-Alexander,OKC,PG,"PG,SG"
```

`source_player_id` is the authoritative join key. Rows without valid metadata
are excluded from the draft-oriented bootstrap import rather than receiving a
guessed position.

## Conversion Formula

Basketball Reference SPS values are per-36-minute statistics. The generator
converts them to per-game projections with:

```text
per_game_stat = per36_stat * projected_minutes_per_game / 36
```

Converted fields:

- `FG` -> `fgm`
- `FGA` -> `fga`
- `FT` -> `ftm`
- `FTA` -> `fta`
- `TRB` -> `rebounds`
- `AST` -> `assists`
- `STL` -> `steals`
- `BLK` -> `blocks`
- `TOV` -> `turnovers`
- `PTS` -> `points`

`PTS` is persisted as optional raw projection data. Fantasy point calculations
still come only from league scoring rules.

## Assumptions

Default assumptions:

- projected games: `68`
- projected minutes per game: `26`

Optional per-player overrides are supported in code through
`BootstrapAssumptions`, but no player-specific overrides are currently
hardcoded.

The generator does not estimate minutes, games, injuries, or role changes.

## CLI

The frontend also exposes an `Import Bootstrap Data` action when no projection
sets exist and the local raw CSV is available. The action calls the backend,
which uses this generator and the existing `ProjectionImportService`; it does
not duplicate import logic or silently import data on page load.

The API action is local-development only and is controlled by:

```text
ENABLE_BOOTSTRAP_IMPORT=true
```

The Docker Compose development stack enables it by default. Outside that
configuration, the bootstrap status/import endpoints return HTTP 403 when the
flag is disabled. The client cannot provide a filesystem path to the API action;
it reads only the canonical bootstrap path or the documented compatibility
fallback.

Preview:

```powershell
docker compose run --rm backend python -m app.projections.bootstrap.generator --preview
```

Import:

```powershell
docker compose run --rm backend python -m app.projections.bootstrap.generator
```

Import and activate:

```powershell
docker compose run --rm backend python -m app.projections.bootstrap.generator --activate
```

Useful options:

- `--path`
- `--metadata-path`
- `--source`
- `--source-name`
- `--season`
- `--as-of-date`
- `--preview`
- `--activate`

## Diagnostics

The CLI prints:

- rows read
- metadata rows read
- metadata availability
- players matched by `source_player_id`
- players missing metadata
- duplicate metadata source IDs
- invalid metadata teams
- invalid metadata positions
- ambiguous metadata rows
- accepted players
- rejected players
- invalid numeric values
- duplicate Basketball Reference IDs
- players using default assumptions

If parsing rejects any rows, the CLI exits before preview/import and prints the
row-level diagnostics.

## Local Regeneration

Projection snapshots are immutable. If an earlier local bootstrap import was
created without eligibility, import a new active bootstrap projection set with a
new `--as-of-date` after adding the metadata CSV:

```powershell
docker compose run --rm backend python -m app.projections.bootstrap.generator `
  --as-of-date YYYY-MM-DD `
  --activate
```

If an existing local draft has zero picks and points at the old bootstrap set,
delete it through the existing draft lifecycle and create a new draft so the
new draft snapshots the active eligible projection set. Do not mutate the old
projection set in place.

## Known Limitations

- Basketball Reference SPS does not provide team or position metadata; the
  companion metadata CSV is required for draft-ready bootstrap imports.
- The generator does not predict games or minutes.
- The generator does not implement a long-term projection model.
- The generator does not add provider aggregation, confidence scoring, injury
  adjustments, or recommendation changes.
