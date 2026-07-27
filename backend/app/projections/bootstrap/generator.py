from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from app.projections.bootstrap.assumptions import BootstrapAssumptions
from app.projections.bootstrap.basketball_reference import (
    BasketballReferenceMetadataParseResult,
    BasketballReferencePlayerMetadata,
    BasketballReferenceSpsParseResult,
    BasketballReferenceSpsPlayer,
    parse_basketball_reference_metadata_csv,
    parse_basketball_reference_sps_csv,
)
from app.projections.import_service import (
    ProjectionImportMetadata,
    ProjectionImportService,
)
from app.projections.providers.models import ProjectionPlayer
from app.shared.database.session import AsyncSessionLocal


DOCUMENTED_DEFAULT_PATH = Path(
    "data/raw/basketball_reference/basketball_reference_sps_2027.csv"
)
FALLBACK_DEFAULT_PATH = Path("data/raw/basketball_reference_sps_2027.csv")
DOCUMENTED_DEFAULT_METADATA_PATH = Path(
    "data/raw/basketball_reference/basketball_reference_player_metadata_2027.csv"
)
FALLBACK_DEFAULT_METADATA_PATH = Path("data/raw/basketball_reference_player_metadata_2027.csv")
DEFAULT_SOURCE_KEY = "basketball-reference-sps-bootstrap"
DEFAULT_SOURCE_NAME = "Basketball Reference SPS Bootstrap"
DEFAULT_SEASON = 2027
DEFAULT_AS_OF_DATE = date(2026, 7, 26)
STAT_QUANT = Decimal("0.001")
USAGE_QUANT = Decimal("0.01")
HELP_EPILOG = f"""
Examples:
  Preview using the default path:
    python -m app.projections.bootstrap.generator --preview

  Preview a specific file:
    python -m app.projections.bootstrap.generator \\
      --path {DOCUMENTED_DEFAULT_PATH} \\
      --metadata-path {DOCUMENTED_DEFAULT_METADATA_PATH} \\
      --preview

  Import without activating:
    python -m app.projections.bootstrap.generator \\
      --season 2027 \\
      --as-of-date YYYY-MM-DD

  Import and activate:
    python -m app.projections.bootstrap.generator \\
      --season 2027 \\
      --as-of-date YYYY-MM-DD \\
      --activate
"""


@dataclass(frozen=True)
class BootstrapProjectionDiagnostics:
    rows_read: int
    metadata_rows_read: int
    metadata_available: bool
    players_matched_by_source_player_id: int
    players_missing_metadata: int
    duplicate_metadata_source_ids: int
    invalid_teams: int
    invalid_positions: int
    ambiguous_rows: int
    accepted_players: int
    rejected_players: int
    invalid_numeric_values: int
    duplicate_ids: int
    players_using_default_assumptions: int


@dataclass(frozen=True)
class BootstrapProjectionPayload:
    players: list[ProjectionPlayer]
    diagnostics: BootstrapProjectionDiagnostics
    parse_result: BasketballReferenceSpsParseResult
    metadata_result: BasketballReferenceMetadataParseResult


def generate_bootstrap_projection_payload(
    path: str | Path,
    metadata_path: str | Path | None = None,
    assumptions: BootstrapAssumptions | None = None,
) -> BootstrapProjectionPayload:
    selected_assumptions = assumptions or BootstrapAssumptions()
    parse_result = parse_basketball_reference_sps_csv(path)
    metadata_result = parse_basketball_reference_metadata_csv(
        metadata_path or default_basketball_reference_metadata_path()
    )
    metadata_by_source_id = {
        metadata.source_player_id: metadata
        for metadata in metadata_result.accepted_metadata
    }
    players = [
        generate_projection_player(
            player,
            selected_assumptions,
            metadata_by_source_id.get(player.source_player_id),
        )
        for player in parse_result.accepted_players
        if player.source_player_id in metadata_by_source_id
    ]
    missing_metadata_count = sum(
        1
        for player in parse_result.accepted_players
        if player.source_player_id not in metadata_by_source_id
    )
    default_assumption_count = sum(
        1
        for player in players
        if selected_assumptions.uses_default_assumptions(player.source_player_id)
    )
    return BootstrapProjectionPayload(
        players=players,
        diagnostics=BootstrapProjectionDiagnostics(
            rows_read=parse_result.rows_read,
            metadata_rows_read=metadata_result.rows_read,
            metadata_available=metadata_result.metadata_available,
            players_matched_by_source_player_id=len(players),
            players_missing_metadata=missing_metadata_count,
            duplicate_metadata_source_ids=metadata_result.duplicate_ids,
            invalid_teams=metadata_result.invalid_teams,
            invalid_positions=metadata_result.invalid_positions,
            ambiguous_rows=0,
            accepted_players=len(players),
            rejected_players=(
                parse_result.rejected_players
                + metadata_result.rejected_rows
                + missing_metadata_count
            ),
            invalid_numeric_values=parse_result.invalid_numeric_values,
            duplicate_ids=parse_result.duplicate_ids,
            players_using_default_assumptions=default_assumption_count,
        ),
        parse_result=parse_result,
        metadata_result=metadata_result,
    )


def generate_projection_player(
    player: BasketballReferenceSpsPlayer,
    assumptions: BootstrapAssumptions,
    metadata: BasketballReferencePlayerMetadata | None = None,
) -> ProjectionPlayer:
    minutes = assumptions.minutes_per_game_for(player.source_player_id).quantize(
        USAGE_QUANT, rounding=ROUND_HALF_UP
    )
    games = assumptions.projected_games_for(player.source_player_id).quantize(
        USAGE_QUANT, rounding=ROUND_HALF_UP
    )
    return ProjectionPlayer(
        source_player_id=player.source_player_id,
        full_name=player.full_name,
        team=metadata.team if metadata else None,
        primary_position=metadata.primary_position if metadata else None,
        positions=metadata.positions if metadata else (),
        games=games,
        minutes_per_game=minutes,
        fgm=_per_game(player.fg_per36, minutes),
        fga=_per_game(player.fga_per36, minutes),
        ftm=_per_game(player.ft_per36, minutes),
        fta=_per_game(player.fta_per36, minutes),
        rebounds=_per_game(player.rebounds_per36, minutes),
        assists=_per_game(player.assists_per36, minutes),
        steals=_per_game(player.steals_per36, minutes),
        blocks=_per_game(player.blocks_per36, minutes),
        turnovers=_per_game(player.turnovers_per36, minutes),
        points=_per_game(player.points_per36, minutes),
        is_active=True,
    )


def default_basketball_reference_sps_path() -> Path:
    if DOCUMENTED_DEFAULT_PATH.exists():
        return DOCUMENTED_DEFAULT_PATH
    return FALLBACK_DEFAULT_PATH


def default_basketball_reference_metadata_path() -> Path:
    if DOCUMENTED_DEFAULT_METADATA_PATH.exists():
        return DOCUMENTED_DEFAULT_METADATA_PATH
    return FALLBACK_DEFAULT_METADATA_PATH


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate bootstrap projections from Basketball Reference SPS. "
            f"Canonical default input path: {DOCUMENTED_DEFAULT_PATH}"
        ),
        epilog=HELP_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--path",
        default=str(default_basketball_reference_sps_path()),
        help=(
            f"Basketball Reference SPS CSV path. Canonical default: "
            f"{DOCUMENTED_DEFAULT_PATH}. The raw file is treated as read-only. "
            f"Temporary compatibility fallback: {FALLBACK_DEFAULT_PATH}."
        ),
    )
    parser.add_argument(
        "--metadata-path",
        default=str(default_basketball_reference_metadata_path()),
        help=(
            "Basketball Reference player metadata CSV path. Canonical default: "
            f"{DOCUMENTED_DEFAULT_METADATA_PATH}. The raw metadata file is "
            "treated as read-only. Temporary compatibility fallback: "
            f"{FALLBACK_DEFAULT_METADATA_PATH}."
        ),
    )
    parser.add_argument("--source", default=DEFAULT_SOURCE_KEY)
    parser.add_argument("--source-name", default=DEFAULT_SOURCE_NAME)
    parser.add_argument("--season", type=int, default=DEFAULT_SEASON)
    parser.add_argument("--as-of-date", type=date.fromisoformat, default=DEFAULT_AS_OF_DATE)
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--activate", action="store_true")
    return parser.parse_args()


async def run_cli() -> int:
    args = parse_args()
    payload = generate_bootstrap_projection_payload(args.path, args.metadata_path)
    _print_diagnostics(payload)
    if payload.parse_result.rejected_issues or payload.metadata_result.rejected_issues:
        print("Basketball Reference bootstrap generation failed:")
        for issue in payload.parse_result.rejected_issues:
            print(f"- {issue.code}: {issue}")
        for issue in payload.metadata_result.rejected_issues:
            print(f"- {issue.code}: {issue}")
        return 1

    metadata = ProjectionImportMetadata(
        source_key=args.source,
        source_name=args.source_name,
        source_description=(
            "Temporary Basketball Reference SPS bootstrap source for validating "
            "Fantasy GM's projection import pipeline."
        ),
        season=args.season,
        as_of_date=args.as_of_date,
        activate=args.activate,
        notes=(
            "Bootstrap import generated from Basketball Reference SPS per-36 "
            "statistics using fixed games and minutes assumptions."
        ),
    )

    async with AsyncSessionLocal() as session:
        preview = await ProjectionImportService(session).preview_players(
            players=payload.players,
            metadata=metadata,
            rows_read=payload.diagnostics.rows_read,
        )
        print(
            "Projection import preview: "
            f"rows={preview.rows_read}, players={preview.valid_player_rows}, "
            f"new_players={preview.newly_proposed_players}, "
            f"identities={preview.identities_to_create}, "
            f"projection_rows={preview.projection_rows_to_create}"
        )

    if args.preview:
        return 0

    async with AsyncSessionLocal() as session:
        result = await ProjectionImportService(session).import_players(
            players=payload.players,
            metadata=metadata,
            rows_read=payload.diagnostics.rows_read,
        )
    print(
        "Imported bootstrap projection set "
        f"{result.projection_set_id} from {result.source_key} "
        f"with {result.projection_rows_created} projection rows "
        f"(active={result.is_active})."
    )
    return 0


def _per_game(per36_value: Decimal, minutes_per_game: Decimal) -> Decimal:
    return ((per36_value * minutes_per_game) / Decimal("36")).quantize(
        STAT_QUANT, rounding=ROUND_HALF_UP
    )


def _print_diagnostics(payload: BootstrapProjectionPayload) -> None:
    diagnostics = payload.diagnostics
    print("Basketball Reference bootstrap diagnostics:")
    print(f"Rows read: {diagnostics.rows_read}")
    print(f"Metadata rows read: {diagnostics.metadata_rows_read}")
    print(f"Metadata available: {diagnostics.metadata_available}")
    print(
        "Players matched by source_player_id: "
        f"{diagnostics.players_matched_by_source_player_id}"
    )
    print(f"Players missing metadata: {diagnostics.players_missing_metadata}")
    print(f"Duplicate metadata source IDs: {diagnostics.duplicate_metadata_source_ids}")
    print(f"Invalid metadata teams: {diagnostics.invalid_teams}")
    print(f"Invalid metadata positions: {diagnostics.invalid_positions}")
    print(f"Ambiguous metadata rows: {diagnostics.ambiguous_rows}")
    print(f"Accepted players: {diagnostics.accepted_players}")
    print(f"Rejected players: {diagnostics.rejected_players}")
    print(f"Invalid numeric values: {diagnostics.invalid_numeric_values}")
    print(f"Duplicate Basketball Reference IDs: {diagnostics.duplicate_ids}")
    print(
        "Players using default assumptions: "
        f"{diagnostics.players_using_default_assumptions}"
    )


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run_cli()))
