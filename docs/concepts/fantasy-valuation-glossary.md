# Fantasy Valuation Glossary

Fantasy GM separates projection data from valuation and recommendation logic. The
current Basketball Reference bootstrap projection set is a development input for
validating the import pipeline and UI. It is not a final Fantasy GM projection
model.

## Bootstrap Assumptions

The Basketball Reference SPS bootstrap currently gives every imported player the
same season assumptions:

- Projected games: 68
- Projected minutes: 26 minutes per game

Those fixed assumptions can make rankings look unrealistic. Players with strong
per-minute defensive or rebounding rates can rise sharply, while high-volume
shooters can be penalized if missed shot and turnover scoring outweighs their
positive categories.

## Fantasy PPG

Projected fantasy points per game using the league's scoring rules.

Fantasy GM targets one fixed ESPN points league. It multiplies each projected
stat by the configured league weight for that stat, then sums the contributions.

PTS is a mandatory fixed scoring rule at `+1` and is applied whenever the
projection contains projected points.

TEAM_WINS is also a mandatory fixed scoring rule at `+1`, but Fantasy GM does
not currently project team wins. Diagnostics report TEAM_WINS as unsupported
with a zero contribution.

## Projected Total

Fantasy PPG multiplied by projected games played.

## Projected Games

Estimated games played used to convert per-game value into season value.

## Projected Minutes

Estimated minutes per game used to convert per-36 production into per-game
projections.

## Replacement Level

The projected value of the best player expected to remain freely available at a
position. Replacement levels are calculated from the league's roster slots, team
count, projected player pool, and player eligibility.

## VOR

Value Over Replacement. Estimated season value above the replacement-level option
at the player's eligible position. Negative VOR means below replacement; it does
not necessarily mean the player has negative fantasy points.

## Positional Scarcity

How quickly useful value drops at a position. Greater scarcity means waiting may
carry more risk.

## VOR Drop

The projected decline in value from the current top option to the next relevant
options at that position.

## Availability Outlook

An estimate of whether the player may still be available at your next pick.

## Roster Fit

How well a player's eligible positions fit the open slots on your current roster.

## Inspecting A Player Calculation

The Valuations page includes an `Explain` action for each player row. It opens a
diagnostics view with:

- raw projected stats;
- projected games and minutes;
- league scoring weights;
- per-stat scoring contributions;
- Fantasy PPG;
- projected total;
- eligible positions;
- replacement baseline by eligible position;
- VOR.

Explanatory terms such as Fantasy PPG, Projected Total, and VOR can be hovered
or keyboard-focused directly. The UI no longer uses separate question-mark help
icons for these terms.

The diagnostics view does not change scoring, replacement-level, VOR, ranking,
recommendation, or draft behavior.
