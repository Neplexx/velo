"""Tests unitaires pour le module csv."""

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from velo.csv import (
    ReleveStation,
    ajouter_releves_stations,
    lire_historique_stations,
    lire_releves_depuis_csv,
    lister_fichiers_historique_csv,
)

FUSEAU_HORAIRE = timezone(timedelta(hours=1))


def _creer_releve_test(
    horodatage: datetime,
    id_station: str = "42",
    velos_disponibles: int = 5,
) -> ReleveStation:
    """Crée un ReleveStation de test."""
    return ReleveStation(
        horodatage=horodatage,
        id_station=id_station,
        velos_disponibles=velos_disponibles,
        bornes_disponibles=15,
        est_installee=True,
        est_en_location=True,
        accepte_retours=True,
        derniere_mise_a_jour=horodatage - timedelta(seconds=10),
    )


def test_ecriture_et_lecture_releve(tmp_path: Path) -> None:
    """Vérifie l'écriture puis la relecture d'un relevé complet."""
    horodatage = datetime(2026, 11, 18, 8, 14, 0, tzinfo=FUSEAU_HORAIRE)
    releves = [
        _creer_releve_test(horodatage, id_station="42", velos_disponibles=3),
        _creer_releve_test(horodatage, id_station="43", velos_disponibles=0),
    ]

    chemin_csv = ajouter_releves_stations(tmp_path, horodatage, releves)
    assert chemin_csv == tmp_path / "2026-11-18.csv"
    assert chemin_csv.exists()

    releves_charges = lire_historique_stations(tmp_path)
    assert len(releves_charges) == 2
    assert releves_charges[0].id_station == "42"
    assert releves_charges[0].velos_disponibles == 3
    assert releves_charges[1].id_station == "43"
    assert releves_charges[1].velos_disponibles == 0


def test_passage_minuit_cree_deux_fichiers(tmp_path: Path) -> None:
    """Vérifie qu'un passage de minuit crée bien deux fichiers journaliers."""
    horodatage_avant = datetime(2026, 11, 18, 23, 59, 0, tzinfo=FUSEAU_HORAIRE)
    horodatage_apres = datetime(2026, 11, 19, 0, 1, 0, tzinfo=FUSEAU_HORAIRE)

    ajouter_releves_stations(tmp_path, horodatage_avant, [_creer_releve_test(horodatage_avant)])
    ajouter_releves_stations(tmp_path, horodatage_apres, [_creer_releve_test(horodatage_apres)])

    fichiers = lister_fichiers_historique_csv(tmp_path)
    assert [fichier.name for fichier in fichiers] == ["2026-11-18.csv", "2026-11-19.csv"]

    tous_les_releves = lire_historique_stations(tmp_path)
    assert len(tous_les_releves) == 2


def test_lignes_corrompues_sont_ignorees(tmp_path: Path) -> None:
    """Vérifie que les lignes invalides sont ignorées sans planter."""
    fichier_csv = tmp_path / "2026-11-18.csv"
    fichier_csv.write_text(
        "timestamp,station_id,bikes,docks,is_installed,is_renting,is_returning,last_reported\n"
        "2026-11-18T08:14:00+01:00,42,3,17,true,true,true,2026-11-18T08:13:41+01:00\n"
        "DATE_INVALIDE,43,5,10,true,true,true,2026-11-18T08:13:41+01:00\n"
        "2026-11-18T08:14:00+01:00,44,-2,10,true,true,true,2026-11-18T08:13:41+01:00\n"
        "2026-11-18T08:14:00+01:00,45,8,12,peut-etre,true,true,2026-11-18T08:13:41+01:00\n",
        encoding="utf-8",
    )

    releves = lire_releves_depuis_csv(fichier_csv)
    assert len(releves) == 1
    assert releves[0].id_station == "42"


def test_filtrage_par_plage_de_dates(tmp_path: Path) -> None:
    """Vérifie le filtrage entre date_debut et date_fin."""
    for jour in (18, 19, 20):
        horodatage = datetime(2026, 11, jour, 10, 0, 0, tzinfo=FUSEAU_HORAIRE)
        ajouter_releves_stations(
            tmp_path,
            horodatage,
            [_creer_releve_test(horodatage, id_station=str(jour))],
        )

    releves_filtres = lire_historique_stations(
        tmp_path,
        date_debut=date(2026, 11, 19),
        date_fin=date(2026, 11, 19),
    )
    assert len(releves_filtres) == 1
    assert releves_filtres[0].id_station == "19"