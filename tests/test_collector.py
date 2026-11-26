"""Tests unitaires pour le module collector."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from velo.collector import convertir_date_limite, convertir_duree, lancer_collecte
from velo.csv import ReleveStation, lire_historique_stations

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


def test_convertir_duree_valide() -> None:
    """Vérifie le parsing de durées valides."""
    assert convertir_duree("3h") == timedelta(hours=3)
    assert convertir_duree("30m") == timedelta(minutes=30)
    assert convertir_duree("1h30m") == timedelta(hours=1, minutes=30)
    assert convertir_duree("90s") == timedelta(seconds=90)


def test_convertir_duree_invalide() -> None:
    """Vérifie que les durées invalides ou nulles lèvent ValueError."""
    with pytest.raises(ValueError):
        convertir_duree("0s")
    with pytest.raises(ValueError):
        convertir_duree("abc")
    with pytest.raises(ValueError):
        convertir_duree("")


def test_convertir_date_limite_valide_et_invalide() -> None:
    """Vérifie le parsing de la date limite --until."""
    date_heure = convertir_date_limite("2026-11-26 18:30")
    assert date_heure.year == 2026
    assert date_heure.month == 11
    assert date_heure.day == 26
    assert date_heure.hour == 18
    assert date_heure.minute == 30
    assert date_heure.tzinfo is not None

    with pytest.raises(ValueError):
        convertir_date_limite("26/11/2026 18:30")


def test_intervalle_inferieur_au_minimum_echoue(tmp_path: Path) -> None:
    """Vérifie qu'un intervalle inférieur à 60 secondes est refusé."""
    horodatage = datetime(2026, 11, 26, 10, 0, 0, tzinfo=FUSEAU_HORAIRE)

    def fausse_recuperation() -> tuple[datetime, list[ReleveStation]]:
        return horodatage, [_creer_releve_test(horodatage)]

    with pytest.raises(ValueError):
        lancer_collecte(
            tmp_path,
            fausse_recuperation,
            intervalle_secondes=30,
            une_seule_fois=True,
        )


def test_collecte_une_seule_fois(tmp_path: Path) -> None:
    """Vérifie que --once enregistre exactement un relevé puis s'arrête."""
    horodatage = datetime(2026, 11, 26, 10, 0, 0, tzinfo=FUSEAU_HORAIRE)

    def fausse_recuperation() -> tuple[datetime, list[ReleveStation]]:
        return horodatage, [
            _creer_releve_test(horodatage, id_station="42"),
            _creer_releve_test(horodatage, id_station="43"),
        ]

    bilan = lancer_collecte(
        tmp_path,
        fausse_recuperation,
        une_seule_fois=True,
        fonction_heure_actuelle=lambda: horodatage,
    )

    assert bilan.releves_enregistres == 1
    assert len(lire_historique_stations(tmp_path)) == 2


def test_deduplication_meme_derniere_mise_a_jour(tmp_path: Path) -> None:
    """Vérifie qu'un relevé avec la même date de mise à jour n'est pas enregistré deux fois."""
    heure_actuelle = [datetime(2026, 11, 26, 10, 0, 0, tzinfo=FUSEAU_HORAIRE)]
    horodatage_identique = datetime(2026, 11, 26, 10, 0, 0, tzinfo=FUSEAU_HORAIRE)
    horodatage_nouveau = datetime(2026, 11, 26, 10, 2, 0, tzinfo=FUSEAU_HORAIRE)
    reponses = [
        (horodatage_identique, [_creer_releve_test(horodatage_identique)]),
        (horodatage_identique, [_creer_releve_test(horodatage_identique)]),  # doublon à ignorer
        (horodatage_nouveau, [_creer_releve_test(horodatage_nouveau)]),
    ]
    index_appel = [0]

    def fausse_recuperation() -> tuple[datetime, list[ReleveStation]]:
        index = index_appel[0]
        index_appel[0] += 1
        return reponses[index]

    def fausse_pause(secondes: float) -> None:
        heure_actuelle[0] += timedelta(seconds=secondes)

    bilan = lancer_collecte(
        tmp_path,
        fausse_recuperation,
        intervalle_secondes=60,
        duree=timedelta(seconds=120),
        fonction_pause=fausse_pause,
        fonction_heure_actuelle=lambda: heure_actuelle[0],
    )

    assert bilan.releves_enregistres == 2
    assert len(lire_historique_stations(tmp_path)) == 2


def test_erreur_reseau_reessaie_sans_planter(tmp_path: Path) -> None:
    """Vérifie qu'une erreur réseau est ignorée et que la collecte continue."""
    heure_actuelle = [datetime(2026, 11, 26, 10, 0, 0, tzinfo=FUSEAU_HORAIRE)]
    horodatage_valide = datetime(2026, 11, 26, 10, 1, 0, tzinfo=FUSEAU_HORAIRE)
    nombre_appels = [0]

    def fausse_recuperation() -> tuple[datetime, list[ReleveStation]]:
        nombre_appels[0] += 1
        if nombre_appels[0] == 1:
            raise ConnectionError("Réseau indisponible")
        return horodatage_valide, [_creer_releve_test(horodatage_valide)]

    def fausse_pause(secondes: float) -> None:
        heure_actuelle[0] += timedelta(seconds=secondes)

    bilan = lancer_collecte(
        tmp_path,
        fausse_recuperation,
        intervalle_secondes=60,
        duree=timedelta(seconds=60),
        fonction_pause=fausse_pause,
        fonction_heure_actuelle=lambda: heure_actuelle[0],
    )

    assert nombre_appels[0] == 2
    assert bilan.releves_enregistres == 1
    assert len(lire_historique_stations(tmp_path)) == 1


def test_ctrl_c_renvoie_bilan(tmp_path: Path) -> None:
    """Vérifie qu'un Ctrl+C renvoie proprement le bilan des relevés déjà enregistrés."""
    horodatage = datetime(2026, 11, 26, 10, 0, 0, tzinfo=FUSEAU_HORAIRE)

    def fausse_recuperation() -> tuple[datetime, list[ReleveStation]]:
        return horodatage, [_creer_releve_test(horodatage)]

    def fausse_pause(_secondes: float) -> None:
        raise KeyboardInterrupt

    bilan = lancer_collecte(
        tmp_path,
        fausse_recuperation,
        intervalle_secondes=60,
        fonction_pause=fausse_pause,
        fonction_heure_actuelle=lambda: horodatage,
    )

    assert bilan.releves_enregistres == 1
    assert bilan.debut == horodatage
    assert bilan.fin == horodatage