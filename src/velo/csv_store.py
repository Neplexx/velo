"""Lecture et écriture des fichiers CSV d'historique."""

from __future__ import annotations

import csv
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

logger = logging.getLogger(__name__)

CSV_COLUMNS: tuple[str, ...] = (
    "timestamp",
    "station_id",
    "bikes",
    "docks",
    "is_installed",
    "is_renting",
    "is_returning",
    "last_reported",
)


@dataclass(frozen=True)
class Stationinfo:
    """Représente une ligne d'historique (une station à un instant donné)."""

    timestamp: datetime
    station_id: str
    bikes: int
    docks: int
    is_installed: bool
    is_renting: bool
    is_returning: bool
    last_reported: datetime


def _to_local_iso(dt: datetime) -> str:
    """Convertit un datetime en chaîne ISO 8601 avec fuseau horaire local."""
    if dt.tzinfo is None:
        dt = dt.astimezone()
    return dt.isoformat(timespec="seconds")


def _format_bool(value: bool) -> str:
    """Formate un booléen en 'true' ou 'false' (format CSV attendu)."""
    return "true" if value else "false"


def _parse_bool(value: str) -> bool:
    """Convertit 'true'/'false' en booléen, ou lève ValueError."""
    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise ValueError(f"Booléen invalide : {value!r}")


def get_history_file(history_dir: Path, dt: datetime) -> Path:
    """Retourne le chemin AAAA-MM-JJ.csv correspondant à la date locale du relevé."""
    local_dt = dt.astimezone()
    return history_dir / f"{local_dt.date().isoformat()}.csv"


def append_snapshot(
    history_dir: Path,
    timestamp: datetime,
    records: Sequence[Stationinfo],
) -> Path:
    """Ajoute un relevé (ensemble de stations) dans le fichier CSV du jour.

    Crée le dossier et l'en-tête CSV si le fichier n'existe pas encore.
    """
    history_dir.mkdir(parents=True, exist_ok=True)
    file_path = get_history_file(history_dir, timestamp)
    file_exists = file_path.exists() and file_path.stat().st_size > 0

    with file_path.open("a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(CSV_COLUMNS)

        for rec in records:
            writer.writerow(
                [
                    _to_local_iso(rec.timestamp),
                    rec.station_id,
                    rec.bikes,
                    rec.docks,
                    _format_bool(rec.is_installed),
                    _format_bool(rec.is_renting),
                    _format_bool(rec.is_returning),
                    _to_local_iso(rec.last_reported),
                ]
            )

    logger.debug("Enregistré %d lignes dans %s", len(records), file_path)
    return file_path


def _parse_row(row: dict[str, str | None]) -> Stationinfo:
    """Convertit une ligne CSV (dict) en Stationinfo ou lève ValueError."""
    if any(row.get(col) is None for col in CSV_COLUMNS):
        raise ValueError("Colonnes manquantes")
    timestamp = datetime.fromisoformat(row["timestamp"].strip())  
    last_reported = datetime.fromisoformat(row["last_reported"].strip())  
    station_id = row["station_id"].strip() 
    if not station_id:
        raise ValueError("station_id vide")

    bikes = int(row["bikes"].strip())  
    docks = int(row["docks"].strip())  
    if bikes < 0 or docks < 0:
        raise ValueError("bikes ou docks négatif")

    return Stationinfo(
        timestamp=timestamp,
        station_id=station_id,
        bikes=bikes,
        docks=docks,
        is_installed=_parse_bool(row["is_installed"]),  
        is_renting=_parse_bool(row["is_renting"]), 
        is_returning=_parse_bool(row["is_returning"]), 
        last_reported=last_reported,
    )



def read_csv_file(file_path: Path) -> list[Stationinfo]:
    """Lit un fichier CSV d'historique en ignorant proprement les lignes corrompues."""
    records: list[Stationinfo] = []

    if not file_path.exists():
        return records

    with file_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for line_num, row in enumerate(reader, start=2):
            try:
                records.append(_parse_row(row))
            except (ValueError, KeyError, TypeError) as exc:
                logger.warning(
                    "Ligne corrompue ignorée dans %s (ligne %d) : %s",
                    file_path.name,
                    line_num,
                    exc,
                )

    return records


def list_history_files(
    history_dir: Path,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[Path]:
    """Liste les fichiers AAAA-MM-JJ.csv triés chronologiquement, filtrés par dates."""
    if not history_dir.exists():
        return []

    matching_files: list[tuple[date, Path]] = []
    for path in history_dir.glob("*.csv"):
        try:
            file_date = date.fromisoformat(path.stem)
        except ValueError:
            logger.debug("Fichier ignoré (nom non conforme) : %s", path.name)
            continue

        if date_from is not None and file_date < date_from:
            continue
        if date_to is not None and file_date > date_to:
            continue

        matching_files.append((file_date, path))

    matching_files.sort(key=lambda item: item[0])
    return [path for _, path in matching_files]


def read_history(
    history_dir: Path,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[Stationinfo]:
    """Lit tout l'historique (ou une plage de dates) trié par timestamp."""
    all_records: list[Stationinfo] = []
    for file_path in list_history_files(history_dir, date_from=date_from, date_to=date_to):
        all_records.extend(read_csv_file(file_path))

    all_records.sort(key=lambda rec: rec.timestamp)
    return all_records