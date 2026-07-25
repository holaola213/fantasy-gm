from __future__ import annotations

import argparse
import asyncio
from datetime import date

from app.projections.import_service import (
    ProjectionImportMetadata,
    ProjectionImportService,
)
from app.projections.providers import (
    ProjectionProviderService,
    ProjectionProviderValidationError,
)
from app.shared.database.session import AsyncSessionLocal


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import a local projection CSV.")
    parser.add_argument("--path", required=True, help="Path to the local CSV file.")
    parser.add_argument("--source", required=True, help="Projection source key.")
    parser.add_argument(
        "--source-name",
        required=True,
        help="Projection source display name.",
    )
    parser.add_argument("--season", required=True, type=int)
    parser.add_argument("--as-of-date", required=True, type=date.fromisoformat)
    parser.add_argument("--source-description")
    parser.add_argument("--notes")
    parser.add_argument(
        "--activate",
        action="store_true",
        help="Mark the imported projection set active for its source, season, and type.",
    )
    return parser.parse_args()


async def import_csv() -> None:
    args = parse_args()
    provider_service = ProjectionProviderService()
    players = provider_service.load_csv_players(args.path)

    async with AsyncSessionLocal() as session:
        result = await ProjectionImportService(session).import_players(
            players=players,
            metadata=ProjectionImportMetadata(
                source_key=args.source,
                source_name=args.source_name,
                source_description=args.source_description,
                season=args.season,
                as_of_date=args.as_of_date,
                activate=args.activate,
                notes=args.notes,
            ),
        )

    print(
        "Imported projection set "
        f"{result.projection_set_id} from {result.source_key} "
        f"for {result.season} with {result.player_count} players "
        f"(active={result.is_active})."
    )


if __name__ == "__main__":
    try:
        asyncio.run(import_csv())
    except ProjectionProviderValidationError as exc:
        print(f"Projection import failed: {exc}")
        raise SystemExit(1) from None
