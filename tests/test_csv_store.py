"""Tests unitaires pour le module csv_store."""

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from velo.csv_store import (
    Stationinfo,
    append_snapshot,
    list_history_files,
    read_csv_file,
    read_history,
)

TZ = timezone(timedelta(hours=1))


def _make_record(ts: datetime, station_id: str = "42", bikes: int = 5) -> Stationinfo:
    """Crée un Stationinfo de test."""
    return Stationinfo(
        timestamp=ts,
        station_id=station_id,
        bikes=bikes,
        docks=15,
        is_installed=True,
        is_renting=True,
        is_returning=True,
        last_reported=ts - timedelta(seconds=10),
    )


def test_append_and_read_snapshot(tmp_path: Path) -> None:
    """Vérifie l'écriture puis la relecture d'un relevé complet."""
    ts = datetime(2026, 11, 18, 8, 14, 0, tzinfo=TZ)
    records = [
        _make_record(ts, station_id="42", bikes=3),
        _make_record(ts, station_id="43", bikes=0),
    ]

    csv_path = append_snapshot(tmp_path, ts, records)

    assert csv_path == tmp_path / "2026-11-18.csv"
    assert csv_path.exists()

    loaded = read_history(tmp_path)
    assert len(loaded) == 2
    assert loaded[0].station_id == "42"
    assert loaded[0].bikes == 3
    assert loaded[1].station_id == "43"
    assert loaded[1].bikes == 0


def test_midnight_rollover_creates_two_files(tmp_path: Path) -> None:
    """Vérifie qu'un passage de minuit crée bien deux fichiers journaliers."""
    ts_before = datetime(2026, 11, 18, 23, 59, 0, tzinfo=TZ)
    ts_after = datetime(2026, 11, 19, 0, 1, 0, tzinfo=TZ)

    append_snapshot(tmp_path, ts_before, [_make_record(ts_before)])
    append_snapshot(tmp_path, ts_after, [_make_record(ts_after)])

    files = list_history_files(tmp_path)
    assert [f.name for f in files] == ["2026-11-18.csv", "2026-11-19.csv"]

    all_records = read_history(tmp_path)
    assert len(all_records) == 2


def test_corrupted_lines_are_ignored(tmp_path: Path) -> None:
    """Vérifie que les lignes invalides sont ignorées sans planter."""
    csv_file = tmp_path / "2026-11-18.csv"
    csv_file.write_text(
        "timestamp,station_id,bikes,docks,is_installed,is_renting,is_returning,last_reported\n"
        "2026-11-18T08:14:00+01:00,42,3,17,true,true,true,2026-11-18T08:13:41+01:00\n"
        "DATE_INVALIDE,43,5,10,true,true,true,2026-11-18T08:13:41+01:00\n"
        "2026-11-18T08:14:00+01:00,44,-2,10,true,true,true,2026-11-18T08:13:41+01:00\n"
        "2026-11-18T08:14:00+01:00,45,8,12,peut-etre,true,true,2026-11-18T08:13:41+01:00\n",
        encoding="utf-8",
    )

    records = read_csv_file(csv_file)
    assert len(records) == 1
    assert records[0].station_id == "42"


def test_filter_by_date_range(tmp_path: Path) -> None:
    """Vérifie le filtrage entre date_from et date_to."""
    for day in (18, 19, 20):
        ts = datetime(2026, 11, day, 10, 0, 0, tzinfo=TZ)
        append_snapshot(tmp_path, ts, [_make_record(ts, station_id=str(day))])

    filtered = read_history(
        tmp_path,
        date_from=date(2026, 11, 19),
        date_to=date(2026, 11, 19),
    )
    assert len(filtered) == 1
    assert filtered[0].station_id == "19"