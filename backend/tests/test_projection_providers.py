from __future__ import annotations

from decimal import Decimal
import subprocess
import sys

import pytest

from app.projections.providers import (
    CSVProjectionProvider,
    ProjectionPlayer,
    ProjectionProviderService,
    ProjectionProviderValidationError,
    SeedProjectionProvider,
)


CSV_HEADER = (
    "player_id,full_name,team,primary_position,positions,games,minutes_per_game,"
    "fgm,fga,ftm,fta,rebounds,assists,steals,blocks,turnovers,is_active\n"
)


def test_projection_provider_service_uses_injected_provider() -> None:
    expected = sample_player(source_player_id="local-1", full_name="Injected Player")

    class FakeProvider:
        def load_players(self) -> list[ProjectionPlayer]:
            return [expected]

    service = ProjectionProviderService(default_provider=FakeProvider())

    assert service.load_players() == [expected]


def test_csv_provider_loads_normalized_players(tmp_path) -> None:
    csv_path = tmp_path / "projections.csv"
    csv_path.write_text(
        CSV_HEADER
        + " 101 , Nikola Jokic , den , c , c , 70.5 , 34.2 , 10.8 , 18.9 , "
        "5.1 , 6.3 , 12.4 , 9.2 , 1.4 , 0.9 , 3.1 , yes\n",
        encoding="utf-8",
    )

    players = CSVProjectionProvider(csv_path).load_players()

    assert players == [
        ProjectionPlayer(
            source_player_id="101",
            full_name="Nikola Jokic",
            team="DEN",
            primary_position="C",
            positions=("C",),
            games=Decimal("70.5"),
            minutes_per_game=Decimal("34.2"),
            fgm=Decimal("10.8"),
            fga=Decimal("18.9"),
            ftm=Decimal("5.1"),
            fta=Decimal("6.3"),
            rebounds=Decimal("12.4"),
            assists=Decimal("9.2"),
            steals=Decimal("1.4"),
            blocks=Decimal("0.9"),
            turnovers=Decimal("3.1"),
            is_active=True,
        )
    ]


def test_csv_provider_loads_payload_with_row_count_and_unknown_column_warning(tmp_path) -> None:
    csv_path = tmp_path / "payload.csv"
    csv_path.write_text(
        CSV_HEADER.replace("\n", ",extra_notes\n")
        + "1,Player One,DEN,C,C,70,30,1,2,1,2,3,4,1,1,2,true,ignored\n"
        + "\n"
        + "2,Player Two,OKC,PG,PG,71,31,1,2,1,2,3,4,1,1,2,true,ignored\n",
        encoding="utf-8",
    )

    payload = CSVProjectionProvider(csv_path).load_payload()

    assert payload.rows_read == 2
    assert [player.full_name for player in payload.players] == [
        "Player One",
        "Player Two",
    ]
    assert [warning.code for warning in payload.warnings] == ["unknown_column"]


def test_csv_provider_accepts_utf8_bom_reordered_columns_and_quoted_values(tmp_path) -> None:
    csv_path = tmp_path / "excel_export.csv"
    csv_path.write_text(
        "\ufefffull_name,player_id,turnovers,blocks,steals,assists,rebounds,"
        "fta,ftm,fga,fgm,minutes_per_game,games,positions,primary_position,team\n"
        '"Last, First",bom-1,2,1,1,4,8,5,4,12,6,30.5,69.5,"PG,SG",PG,DEN\r\n',
        encoding="utf-8",
    )

    players = CSVProjectionProvider(csv_path).load_players()

    assert players[0].source_player_id == "bom-1"
    assert players[0].full_name == "Last, First"
    assert players[0].positions == ("PG", "SG")
    assert players[0].games == Decimal("69.5")


def test_csv_provider_reports_missing_required_columns(tmp_path) -> None:
    csv_path = tmp_path / "missing.csv"
    csv_path.write_text("player_id,full_name\n1,Player One\n", encoding="utf-8")

    with pytest.raises(ProjectionProviderValidationError, match="missing required"):
        CSVProjectionProvider(csv_path).load_players()


def test_csv_provider_reports_empty_files(tmp_path) -> None:
    csv_path = tmp_path / "empty.csv"
    csv_path.write_text("", encoding="utf-8")

    with pytest.raises(ProjectionProviderValidationError, match="empty"):
        CSVProjectionProvider(csv_path).load_players()


def test_csv_provider_reports_invalid_numeric_values(tmp_path) -> None:
    csv_path = tmp_path / "invalid_numeric.csv"
    csv_path.write_text(
        CSV_HEADER
        + "1,Player One,DEN,C,C,not-a-number,30,1,2,1,2,3,4,1,1,2,true\n",
        encoding="utf-8",
    )

    with pytest.raises(ProjectionProviderValidationError, match="games"):
        CSVProjectionProvider(csv_path).load_players()


def test_csv_provider_reports_non_finite_numeric_values_with_diagnostics(tmp_path) -> None:
    csv_path = tmp_path / "nan.csv"
    csv_path.write_text(
        CSV_HEADER
        + "1,Player One,DEN,C,C,NaN,30,1,2,1,2,3,4,1,1,2,true\n",
        encoding="utf-8",
    )

    with pytest.raises(ProjectionProviderValidationError) as exc_info:
        CSVProjectionProvider(csv_path).load_players()

    issue = exc_info.value.issues[0]
    assert issue.code == "non_finite_number"
    assert issue.row_number == 2
    assert issue.field == "games"
    assert issue.value == "NaN"


def test_csv_provider_detects_duplicates_after_normalization(tmp_path) -> None:
    csv_path = tmp_path / "duplicates.csv"
    csv_path.write_text(
        CSV_HEADER
        + " abc , Player One,DEN,C,C,70,30,1,2,1,2,3,4,1,1,2,true\n"
        + " abc , player one ,OKC,PG,PG,70,30,1,2,1,2,3,4,1,1,2,true\n",
        encoding="utf-8",
    )

    with pytest.raises(ProjectionProviderValidationError) as exc_info:
        CSVProjectionProvider(csv_path).load_players()

    message = str(exc_info.value)
    codes = [issue.code for issue in exc_info.value.issues]
    assert "duplicate player_id" in message
    assert "duplicate full_name" in message
    assert "duplicate_provider_player_id" in codes
    assert "duplicate_player_name" in codes


def test_csv_provider_reports_multiple_structured_issues(tmp_path) -> None:
    csv_path = tmp_path / "multiple_errors.csv"
    csv_path.write_text(
        CSV_HEADER
        + "1,,DEN,C,C,NaN,30,1,2,1,2,3,4,1,1,2,true\n"
        + "2,Player Two,DEN,C,ABC,70,bad,1,2,1,2,3,4,1,1,2,true\n",
        encoding="utf-8",
    )

    with pytest.raises(ProjectionProviderValidationError) as exc_info:
        CSVProjectionProvider(csv_path).load_players()

    codes = [issue.code for issue in exc_info.value.issues]
    assert "required_field_missing" in codes
    assert "non_finite_number" in codes
    assert "unknown_position" in codes
    assert "invalid_number" in codes


def test_csv_provider_treats_source_player_ids_as_case_sensitive(tmp_path) -> None:
    csv_path = tmp_path / "case_sensitive_ids.csv"
    csv_path.write_text(
        CSV_HEADER
        + " abc , Player One,DEN,C,C,70,30,1,2,1,2,3,4,1,1,2,true\n"
        + " ABC , Player Two,OKC,PG,PG,70,30,1,2,1,2,3,4,1,1,2,true\n",
        encoding="utf-8",
    )

    players = CSVProjectionProvider(csv_path).load_players()

    assert [player.source_player_id for player in players] == ["abc", "ABC"]


def test_documented_example_projection_csv_passes_preview_parser() -> None:
    players = CSVProjectionProvider("docs/imports/example_projection.csv").load_players()

    assert len(players) == 3
    assert players[0].source_player_id == "example-001"


def test_cli_validation_failure_has_no_traceback(tmp_path) -> None:
    csv_path = tmp_path / "invalid_cli.csv"
    csv_path.write_text(
        CSV_HEADER
        + "1,Player One,DEN,C,C,not-a-number,30,1,2,1,2,3,4,1,1,2,true\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.projections.import_csv",
            "--path",
            str(csv_path),
            "--source",
            "cli-test",
            "--source-name",
            "CLI Test",
            "--season",
            "2026",
            "--as-of-date",
            "2026-10-08",
            "--preview",
        ],
        cwd=".",
        capture_output=True,
        text=True,
        check=False,
    )

    output = result.stdout + result.stderr
    assert result.returncode == 1
    assert "Projection import failed:" in output
    assert "Traceback" not in output


def test_cli_preview_success_uses_zero_exit_code() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.projections.import_csv",
            "--path",
            "docs/imports/example_projection.csv",
            "--source",
            "cli-preview",
            "--source-name",
            "CLI Preview",
            "--season",
            "2026",
            "--as-of-date",
            "2026-10-08",
            "--preview",
        ],
        cwd=".",
        capture_output=True,
        text=True,
        check=False,
    )

    output = result.stdout + result.stderr
    assert result.returncode == 0
    assert "Ready: True" in output
    assert "Rows read: 3" in output


def test_csv_provider_reports_malformed_positions(tmp_path) -> None:
    csv_path = tmp_path / "positions.csv"
    csv_path.write_text(
        CSV_HEADER
        + "1,Player One,DEN,PG,PG|IR,70,30,1,2,1,2,3,4,1,1,2,true\n",
        encoding="utf-8",
    )

    with pytest.raises(ProjectionProviderValidationError, match="unsupported"):
        CSVProjectionProvider(csv_path).load_players()


def test_csv_provider_reports_empty_provider_rows_with_stable_code(tmp_path) -> None:
    csv_path = tmp_path / "blank_rows.csv"
    csv_path.write_text(CSV_HEADER + "\n\n", encoding="utf-8")

    with pytest.raises(ProjectionProviderValidationError) as exc_info:
        CSVProjectionProvider(csv_path).load_players()

    assert exc_info.value.issues[0].code == "empty_provider_rows"


def test_csv_provider_reports_malformed_rows_with_extra_fields(tmp_path) -> None:
    csv_path = tmp_path / "extra_fields.csv"
    csv_path.write_text(
        CSV_HEADER
        + "1,Player One,DEN,C,C,70,30,1,2,1,2,3,4,1,1,2,true,overflow\n",
        encoding="utf-8",
    )

    with pytest.raises(ProjectionProviderValidationError) as exc_info:
        CSVProjectionProvider(csv_path).load_players()

    issue = exc_info.value.issues[0]
    assert issue.code == "malformed_row"
    assert issue.row_number == 2
    assert issue.value == "overflow"


def test_seed_provider_loads_deterministic_development_players() -> None:
    players = SeedProjectionProvider().load_players()

    assert len(players) >= 10
    assert players[0].source_player_id == "1"
    assert players[0].full_name == "Nikola Jokic"
    assert players[0].positions == ("C",)
    assert players[0].games == Decimal("70.50")


def sample_player(
    *,
    source_player_id: str = "1",
    full_name: str = "Sample Player",
) -> ProjectionPlayer:
    return ProjectionPlayer(
        source_player_id=source_player_id,
        full_name=full_name,
        team="DEN",
        primary_position="C",
        positions=("C",),
        games=Decimal("70"),
        minutes_per_game=Decimal("30"),
        fgm=Decimal("1"),
        fga=Decimal("2"),
        ftm=Decimal("1"),
        fta=Decimal("2"),
        rebounds=Decimal("3"),
        assists=Decimal("4"),
        steals=Decimal("1"),
        blocks=Decimal("1"),
        turnovers=Decimal("2"),
    )
