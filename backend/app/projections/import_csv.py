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
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Preview the import plan without writing database changes.",
    )
    return parser.parse_args()


async def import_csv() -> None:
    args = parse_args()
    provider_service = ProjectionProviderService()
    payload = provider_service.load_csv_payload(args.path)
    metadata = ProjectionImportMetadata(
        source_key=args.source,
        source_name=args.source_name,
        source_description=args.source_description,
        season=args.season,
        as_of_date=args.as_of_date,
        activate=args.activate,
        notes=args.notes,
    )

    async with AsyncSessionLocal() as session:
        service = ProjectionImportService(session)
        if args.preview:
            preview = await service.preview_players(
                players=payload.players,
                metadata=metadata,
                rows_read=payload.rows_read,
                warnings=payload.warnings,
            )
            print(
                "Projection import preview "
                f"for {preview.source_key} {preview.season} "
                f"{preview.projection_type} {preview.as_of_date}"
            )
            print("Ready: True")
            print(f"Rows read: {preview.rows_read}")
            print(f"Valid player rows: {preview.valid_player_rows}")
            print(f"Matched existing players: {preview.matched_existing_players}")
            print(f"New players proposed: {preview.newly_proposed_players}")
            print(f"Source identities to create: {preview.identities_to_create}")
            print(
                "Players with eligibility changes: "
                f"{preview.players_with_eligibility_changes}"
            )
            print(
                "Eligibility positions to add/remove: "
                f"{preview.eligibility_positions_to_add}/"
                f"{preview.eligibility_positions_to_remove}"
            )
            print(f"Projection rows to create: {preview.projection_rows_to_create}")
            print(f"Activation requested: {preview.activation_requested}")
            if preview.warnings:
                print("Warnings:")
                for warning in preview.warnings:
                    print(f"- {warning.code}: {warning}")
            return

        result = await service.import_players(
            players=payload.players,
            metadata=metadata,
            rows_read=payload.rows_read,
            warnings=payload.warnings,
        )

    print(
        "Imported projection set "
        f"{result.projection_set_id} from {result.source_key} "
        f"for {result.season} with {result.player_count} players "
        f"(active={result.is_active})."
    )
    print(
        "Summary: "
        f"rows_imported={result.rows_imported}, "
        f"existing_players_matched={result.existing_players_matched}, "
        f"new_players_created={result.new_players_created}, "
        f"source_identities_created={result.source_identities_created}, "
        f"players_with_eligibility_changes={result.players_with_eligibility_changes}, "
        f"eligibility_positions_added={result.eligibility_positions_added}, "
        f"eligibility_positions_removed={result.eligibility_positions_removed}, "
        f"projection_rows_created={result.projection_rows_created}"
    )


if __name__ == "__main__":
    try:
        asyncio.run(import_csv())
    except ProjectionProviderValidationError as exc:
        print("Projection import failed:")
        for issue in exc.issues:
            print(f"- {issue.code}: {issue}")
        raise SystemExit(1) from None
