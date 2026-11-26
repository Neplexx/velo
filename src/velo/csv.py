"""Lecture et écriture des fichiers CSV d'historique."""

from __future__ import annotations

import csv
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

journal = logging.getLogger(__name__)

COLONNES_CSV: tuple[str, ...] = (
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
class ReleveStation:
    """Représente une ligne d'historique (une station à un instant donné)."""

    horodatage: datetime
    id_station: str
    velos_disponibles: int
    bornes_disponibles: int
    est_installee: bool
    est_en_location: bool
    accepte_retours: bool
    derniere_mise_a_jour: datetime


def _formater_date_iso_locale(date_heure: datetime) -> str:
    """Convertit un datetime en chaîne ISO 8601 avec fuseau horaire local."""
    if date_heure.tzinfo is None:
        date_heure = date_heure.astimezone()
    return date_heure.isoformat(timespec="seconds")


def _booleen_vers_texte_csv(valeur: bool) -> str:
    """Formate un booléen en 'true' ou 'false' (format CSV attendu)."""
    return "true" if valeur else "false"


def _texte_csv_vers_booleen(texte_brut: str) -> bool:
    """Convertit 'true'/'false' en booléen, ou lève ValueError."""
    texte_normalise = texte_brut.strip().lower()
    if texte_normalise == "true":
        return True
    if texte_normalise == "false":
        return False
    raise ValueError(f"Booléen invalide : {texte_brut!r}")


def obtenir_chemin_fichier_du_jour(dossier_historique: Path, date_heure: datetime) -> Path:
    """Retourne le chemin AAAA-MM-JJ.csv correspondant à la date locale du relevé."""
    date_heure_locale = date_heure.astimezone()
    return dossier_historique / f"{date_heure_locale.date().isoformat()}.csv"


def ajouter_releves_stations(
    dossier_historique: Path,
    horodatage: datetime,
    releves: Sequence[ReleveStation],
) -> Path:
    """Ajoute un relevé (ensemble de stations) dans le fichier CSV du jour.

    Crée le dossier et l'en-tête CSV si le fichier n'existe pas encore.
    """
    dossier_historique.mkdir(parents=True, exist_ok=True)
    chemin_fichier = obtenir_chemin_fichier_du_jour(dossier_historique, horodatage)
    fichier_non_vide = chemin_fichier.exists() and chemin_fichier.stat().st_size > 0

    with chemin_fichier.open("a", encoding="utf-8", newline="") as fichier_csv:
        ecrivain_csv = csv.writer(fichier_csv)
        if not fichier_non_vide:
            ecrivain_csv.writerow(COLONNES_CSV)

        for releve in releves:
            ecrivain_csv.writerow(
                [
                    _formater_date_iso_locale(releve.horodatage),
                    releve.id_station,
                    releve.velos_disponibles,
                    releve.bornes_disponibles,
                    _booleen_vers_texte_csv(releve.est_installee),
                    _booleen_vers_texte_csv(releve.est_en_location),
                    _booleen_vers_texte_csv(releve.accepte_retours),
                    _formater_date_iso_locale(releve.derniere_mise_a_jour),
                ]
            )

    journal.debug("Enregistré %d lignes dans %s", len(releves), chemin_fichier)
    return chemin_fichier


def _convertir_ligne_csv(ligne_csv: dict[str, str | None]) -> ReleveStation:
    """Convertit une ligne CSV (dict) en ReleveStation ou lève ValueError."""
    if any(ligne_csv.get(nom_colonne) is None for nom_colonne in COLONNES_CSV):
        raise ValueError("Colonnes manquantes")

    horodatage = datetime.fromisoformat(ligne_csv["timestamp"].strip())
    derniere_mise_a_jour = datetime.fromisoformat(ligne_csv["last_reported"].strip())
    id_station = ligne_csv["station_id"].strip()
    if not id_station:
        raise ValueError("station_id vide")

    velos_disponibles = int(ligne_csv["bikes"].strip())
    bornes_disponibles = int(ligne_csv["docks"].strip())
    if velos_disponibles < 0 or bornes_disponibles < 0:
        raise ValueError("bikes ou docks négatif")

    return ReleveStation(
        horodatage=horodatage,
        id_station=id_station,
        velos_disponibles=velos_disponibles,
        bornes_disponibles=bornes_disponibles,
        est_installee=_texte_csv_vers_booleen(ligne_csv["is_installed"]),
        est_en_location=_texte_csv_vers_booleen(ligne_csv["is_renting"]),
        accepte_retours=_texte_csv_vers_booleen(ligne_csv["is_returning"]),
        derniere_mise_a_jour=derniere_mise_a_jour,
    )


def lire_releves_depuis_csv(chemin_fichier: Path) -> list[ReleveStation]:
    """Lit un fichier CSV d'historique en ignorant proprement les lignes corrompues."""
    releves: list[ReleveStation] = []

    if not chemin_fichier.exists():
        return releves

    with chemin_fichier.open("r", encoding="utf-8", newline="") as fichier_csv:
        lecteur_csv = csv.DictReader(fichier_csv)
        for numero_ligne, ligne_csv in enumerate(lecteur_csv, start=2):
            try:
                releves.append(_convertir_ligne_csv(ligne_csv))
            except (ValueError, KeyError, TypeError) as erreur:
                journal.warning(
                    "Ligne corrompue ignorée dans %s (ligne %d) : %s",
                    chemin_fichier.name,
                    numero_ligne,
                    erreur,
                )

    return releves


def lister_fichiers_historique_csv(
    dossier_historique: Path,
    date_debut: date | None = None,
    date_fin: date | None = None,
) -> list[Path]:
    """Liste les fichiers AAAA-MM-JJ.csv triés chronologiquement, filtrés par dates."""
    if not dossier_historique.exists():
        return []

    fichiers_dates: list[tuple[date, Path]] = []
    for chemin_fichier in dossier_historique.glob("*.csv"):
        try:
            date_fichier = date.fromisoformat(chemin_fichier.stem)
        except ValueError:
            journal.debug("Fichier ignoré (nom non conforme) : %s", chemin_fichier.name)
            continue

        if date_debut is not None and date_fichier < date_debut:
            continue
        if date_fin is not None and date_fichier > date_fin:
            continue

        fichiers_dates.append((date_fichier, chemin_fichier))

    fichiers_dates.sort(key=lambda element: element[0])
    return [chemin_fichier for _, chemin_fichier in fichiers_dates]


def lire_historique_stations(
    dossier_historique: Path,
    date_debut: date | None = None,
    date_fin: date | None = None,
) -> list[ReleveStation]:
    """Lit tout l'historique (ou une plage de dates) trié par horodatage."""
    tous_les_releves: list[ReleveStation] = []
    for chemin_fichier in lister_fichiers_historique_csv(
        dossier_historique,
        date_debut=date_debut,
        date_fin=date_fin,
    ):
        tous_les_releves.extend(lire_releves_depuis_csv(chemin_fichier))

    tous_les_releves.sort(key=lambda releve: releve.horodatage)
    return tous_les_releves