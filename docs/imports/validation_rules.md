# Projection Import Validation Rules

## Row Numbering

Diagnostics use physical CSV row numbers. Row 1 is the header. Completely blank
physical lines are ignored and do not produce player rows. `rows_read` counts
nonblank data rows after the header.

## Required Fields

Required headers are `player_id`, `full_name`, `games`, `minutes_per_game`,
`fgm`, `fga`, `ftm`, `fta`, `rebounds`, `assists`, `steals`, `blocks`, and
`turnovers`.

Required cell values must be nonblank after trimming whitespace.

Error code: `required_field_missing`

## Header Policy

Headers are trimmed and matched case-insensitively. Reordered columns are
accepted. Unknown extra columns are ignored and reported as warnings.

Missing required header error code: `missing_required_column`

Extra-column warning code: `unknown_column`

Rows with more fields than the header defines are rejected instead of being
silently mapped.

Malformed-row error code: `malformed_row`

## Numeric Rules

Numeric fields are parsed as finite decimal numbers. `NaN`, `Infinity`, and
`-Infinity` are rejected. Negative projection values are rejected. `games` must
be between 0 and 82. `minutes_per_game` must be between 0 and 60. `fgm` cannot
exceed `fga`; `ftm` cannot exceed `fta`.

Error codes:

- `invalid_number`
- `non_finite_number`
- `value_out_of_range`

The current schema does not accept percentage columns. Do not provide `FG%`,
`FT%`, or display percentages such as `47.5%`.

## Positions

Supported position keys are `PG`, `SG`, `SF`, `PF`, and `C`.

`primary_position` may be empty. If present, it must be supported and included in
`positions`.

`positions` may be empty. If it is empty and `primary_position` is present, the
primary position is used. If both `positions` and `primary_position` are empty,
the import creates no `PlayerEligibility` rows for that player. For an existing
resolved player, the latest successful import replaces current eligibility, so
an empty resolved eligibility set removes previous eligibility. The `positions`
column accepts comma, `/`, or `|` separators.

Error code: `unknown_position`

## Provider IDs

`player_id` is trimmed before persistence. IDs are case-sensitive after trimming,
so `player-1` and `PLAYER-1` are distinct. IDs that differ only by surrounding
whitespace collide.

Error code: `duplicate_provider_player_id`

## Exact-Name Fallback

When no provider-local identity exists, exact full-name fallback may resolve the
row to a current local player. Zero exact matches create a player. One exact
match reuses that player. Multiple exact matches fail.

Error code: `ambiguous_exact_name_match`

## Error Reference

- `required_field_missing`: a required cell value was blank.
- `missing_required_column`: a required CSV header was absent.
- `unknown_column`: an extra unsupported header was ignored.
- `invalid_number`: a numeric field could not be parsed as Decimal.
- `non_finite_number`: a numeric field was `NaN` or infinity.
- `value_out_of_range`: a numeric field violated a supported range.
- `unknown_position`: a position key was unsupported.
- `invalid_boolean`: `is_active` was not a supported true/false value.
- `duplicate_provider_player_id`: a provider-local ID duplicated after trimming.
- `duplicate_player_name`: a full name appeared more than once in one file.
- `empty_provider_rows`: the file contained no accepted player rows.
- `malformed_row`: a CSV row had more fields than the header defines.
- `ambiguous_exact_name_match`: exact-name fallback found multiple players.
