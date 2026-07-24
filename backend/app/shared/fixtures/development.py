from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class DevelopmentPlayerFixture:
    id: int
    full_name: str
    team: str
    primary_position: str
    eligible_positions: tuple[str, ...]
    games: Decimal
    minutes_per_game: Decimal
    fgm: Decimal
    fga: Decimal
    ftm: Decimal
    fta: Decimal
    rebounds: Decimal
    assists: Decimal
    steals: Decimal
    blocks: Decimal
    turnovers: Decimal
    is_active: bool = True


EXISTING_PLAYER_FIXTURES = [
    DevelopmentPlayerFixture(1, "Nikola Jokic", "DEN", "C", ("C",), Decimal("70.50"), Decimal("34.20"), Decimal("10.800"), Decimal("18.900"), Decimal("5.100"), Decimal("6.300"), Decimal("12.400"), Decimal("9.200"), Decimal("1.400"), Decimal("0.900"), Decimal("3.100")),
    DevelopmentPlayerFixture(2, "Shai Gilgeous-Alexander", "OKC", "PG", ("PG", "SG"), Decimal("72.00"), Decimal("34.80"), Decimal("10.500"), Decimal("21.000"), Decimal("8.200"), Decimal("9.100"), Decimal("5.600"), Decimal("6.400"), Decimal("1.800"), Decimal("1.000"), Decimal("2.400")),
    DevelopmentPlayerFixture(3, "Luka Doncic", "LAL", "PG", ("PG", "SG"), Decimal("68.50"), Decimal("35.40"), Decimal("9.800"), Decimal("20.700"), Decimal("6.700"), Decimal("8.200"), Decimal("8.500"), Decimal("9.100"), Decimal("1.400"), Decimal("0.500"), Decimal("3.700")),
    DevelopmentPlayerFixture(4, "Giannis Antetokounmpo", "MIL", "PF", ("PF", "C"), Decimal("66.00"), Decimal("32.60"), Decimal("11.200"), Decimal("19.000"), Decimal("7.000"), Decimal("10.800"), Decimal("11.100"), Decimal("6.200"), Decimal("1.200"), Decimal("1.100"), Decimal("3.000")),
    DevelopmentPlayerFixture(5, "Anthony Edwards", "MIN", "SG", ("SG", "SF"), Decimal("74.00"), Decimal("35.00"), Decimal("9.400"), Decimal("20.800"), Decimal("5.000"), Decimal("6.200"), Decimal("5.700"), Decimal("5.000"), Decimal("1.300"), Decimal("0.600"), Decimal("2.800")),
    DevelopmentPlayerFixture(6, "Jayson Tatum", "BOS", "SF", ("SF", "PF"), Decimal("70.00"), Decimal("36.10"), Decimal("9.100"), Decimal("19.800"), Decimal("5.800"), Decimal("6.900"), Decimal("8.000"), Decimal("5.300"), Decimal("1.100"), Decimal("0.700"), Decimal("2.500")),
    DevelopmentPlayerFixture(7, "Victor Wembanyama", "SAS", "C", ("PF", "C"), Decimal("69.50"), Decimal("31.80"), Decimal("8.900"), Decimal("18.500"), Decimal("4.700"), Decimal("5.800"), Decimal("10.700"), Decimal("4.100"), Decimal("1.200"), Decimal("3.400"), Decimal("3.300")),
    DevelopmentPlayerFixture(8, "Stephen Curry", "GSW", "PG", ("PG",), Decimal("65.00"), Decimal("32.40"), Decimal("8.500"), Decimal("18.400"), Decimal("4.300"), Decimal("4.800"), Decimal("4.500"), Decimal("6.100"), Decimal("1.100"), Decimal("0.400"), Decimal("2.900")),
    DevelopmentPlayerFixture(9, "Bam Adebayo", "MIA", "C", ("PF", "C"), Decimal("71.00"), Decimal("33.10"), Decimal("7.400"), Decimal("13.900"), Decimal("3.900"), Decimal("5.200"), Decimal("10.200"), Decimal("4.000"), Decimal("1.100"), Decimal("0.900"), Decimal("2.100")),
    DevelopmentPlayerFixture(10, "Paolo Banchero", "ORL", "PF", ("SF", "PF"), Decimal("73.00"), Decimal("34.00"), Decimal("8.800"), Decimal("18.700"), Decimal("5.600"), Decimal("7.200"), Decimal("7.400"), Decimal("5.400"), Decimal("1.000"), Decimal("0.700"), Decimal("2.700")),
]


TEAMS = [
    "ATL",
    "BOS",
    "BKN",
    "CHA",
    "CHI",
    "CLE",
    "DAL",
    "DEN",
    "DET",
    "GSW",
    "HOU",
    "IND",
    "LAC",
    "LAL",
    "MEM",
    "MIA",
    "MIL",
    "MIN",
    "NYK",
    "OKC",
    "ORL",
    "PHI",
    "PHX",
    "POR",
    "SAC",
    "SAS",
    "TOR",
    "UTA",
    "WAS",
    "FA",
]


def generated_player_fixtures() -> list[DevelopmentPlayerFixture]:
    fixtures: list[DevelopmentPlayerFixture] = []
    next_id = 10001
    for position in ["PG", "SG", "SF", "PF", "C"]:
        for index in range(1, 27):
            fixtures.append(
                _fixture(
                    next_id,
                    f"Development {position} {index:03d}",
                    position,
                    (position,),
                    index,
                )
            )
            next_id += 1

    for label, primary_position, positions in [
        ("Guard Combo", "PG", ("PG", "SG")),
        ("Wing Combo", "SG", ("SG", "SF")),
        ("Forward Combo", "SF", ("SF", "PF")),
        ("Big Combo", "PF", ("PF", "C")),
    ]:
        for index in range(1, 11):
            fixtures.append(
                _fixture(
                    next_id,
                    f"Development {label} {index:03d}",
                    primary_position,
                    positions,
                    index + 24,
                )
            )
            next_id += 1
    return fixtures


def _fixture(
    fixture_id: int,
    full_name: str,
    primary_position: str,
    eligible_positions: tuple[str, ...],
    index: int,
) -> DevelopmentPlayerFixture:
    tier = (fixture_id - 10001) // 10
    variance = index % 7
    tie_adjustment = Decimal("0.000") if index % 17 in {0, 1} else Decimal(index % 5) / Decimal("100")
    return DevelopmentPlayerFixture(
        id=fixture_id,
        full_name=full_name,
        team=TEAMS[(fixture_id + index) % len(TEAMS)],
        primary_position=primary_position,
        eligible_positions=eligible_positions,
        games=Decimal(58 + ((fixture_id + index) % 25)).quantize(Decimal("0.00")),
        minutes_per_game=(Decimal("14.00") + Decimal((fixture_id + index) % 23) + tie_adjustment).quantize(Decimal("0.00")),
        fgm=(Decimal("2.000") + Decimal(tier) / Decimal("5") + Decimal(variance) / Decimal("10")).quantize(Decimal("0.000")),
        fga=(Decimal("6.000") + Decimal(tier) / Decimal("4") + Decimal(variance) / Decimal("10")).quantize(Decimal("0.000")),
        ftm=(Decimal("1.000") + Decimal(index % 6) / Decimal("5")).quantize(Decimal("0.000")),
        fta=(Decimal("2.000") + Decimal(index % 6) / Decimal("4")).quantize(Decimal("0.000")),
        rebounds=(Decimal("2.500") + Decimal((index + tier) % 9) / Decimal("2")).quantize(Decimal("0.000")),
        assists=(Decimal("1.500") + Decimal((index + len(eligible_positions)) % 8) / Decimal("2")).quantize(Decimal("0.000")),
        steals=(Decimal("0.400") + Decimal(index % 5) / Decimal("10")).quantize(Decimal("0.000")),
        blocks=(Decimal("0.200") + Decimal((index + tier) % 5) / Decimal("10")).quantize(Decimal("0.000")),
        turnovers=(Decimal("0.800") + Decimal(index % 7) / Decimal("10")).quantize(Decimal("0.000")),
    )


DEVELOPMENT_PLAYER_FIXTURES = [
    *EXISTING_PLAYER_FIXTURES,
    *generated_player_fixtures(),
]
