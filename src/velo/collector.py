"""Boucle de collecte périodique de l'état des stations (velo collect)."""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from velo.csv import ReleveStation, ajouter_releves_stations

journal = logging.getLogger(__name__)

INTERVALLE_MINIMUM_SECONDES = 60

# Type d'une fonction qui interroge gbfs.py et renvoie :
# (derniere_mise_a_jour_de_l_api, liste_des_stations)
FonctionRecuperationReleve = Callable[[], tuple[datetime, Sequence[ReleveStation]]]


@dataclass(frozen=True)
class BilanCollecte:
    """Bilan final d'une session de collecte."""

    releves_enregistres: int
    debut: datetime
    fin: datetime


def convertir_duree(texte_duree: str) -> timedelta:
    """Convertit une durée texte (ex: '3h', '30m', '1h30m', '90s') en timedelta."""
    correspondance = re.fullmatch(
        r"(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?",
        texte_duree.strip().lower(),
    )
    if not correspondance or not any(correspondance.groups()):
        raise ValueError(
            f"Durée invalide : {texte_duree!r} (exemples attendus : '30m', '3h', '1h30m')."
        )

    heures = int(correspondance.group(1) or 0)
    minutes = int(correspondance.group(2) or 0)
    secondes = int(correspondance.group(3) or 0)
    duree_totale = timedelta(hours=heures, minutes=minutes, seconds=secondes)

    if duree_totale.total_seconds() <= 0:
        raise ValueError("La durée doit être strictement positive.")
    return duree_totale


def convertir_date_limite(texte_date: str) -> datetime:
    """Convertit 'AAAA-MM-JJ HH:MM' en datetime local."""
    try:
        date_heure = datetime.strptime(texte_date.strip(), "%Y-%m-%d %H:%M")
    except ValueError as erreur:
        raise ValueError(
            f"Date invalide : {texte_date!r} (format attendu : 'AAAA-MM-JJ HH:MM')."
        ) from erreur
    return date_heure.astimezone()


def lancer_collecte(
    dossier_historique: Path,
    recuperer_releve: FonctionRecuperationReleve,
    *,
    intervalle_secondes: int = 120,
    duree: timedelta | None = None,
    jusqua: datetime | None = None,
    une_seule_fois: bool = False,
    fonction_pause: Callable[[float], None] = time.sleep,
    fonction_heure_actuelle: Callable[[], datetime] = lambda: datetime.now().astimezone(),
) -> BilanCollecte:
    """Exécute la boucle de collecte et renvoie le bilan final.

    Gère :
    - la validation de l'intervalle (>= 60 s) ;
    - la déduplication sur la date de dernière mise à jour ;
    - les erreurs réseau (journalisées, avec nouvel essai au cycle suivant) ;
    - l'arrêt propre sur --once, --duration, --until ou Ctrl+C.
    """
    if intervalle_secondes < INTERVALLE_MINIMUM_SECONDES:
        raise ValueError(
            f"L'intervalle doit être d'au moins {INTERVALLE_MINIMUM_SECONDES} secondes."
        )

    debut = fonction_heure_actuelle()
    echeance: datetime | None = None
    if duree is not None:
        echeance = debut + duree
    elif jusqua is not None:
        echeance = jusqua

    releves_enregistres = 0
    derniere_date_vue: datetime | None = None

    try:
        while True:
            debut_cycle = fonction_heure_actuelle()

            try:
                derniere_mise_a_jour, releves = recuperer_releve()
            except Exception as erreur:  # noqa: BLE001
                journal.error("Erreur lors de la collecte : %s (nouvel essai)", erreur)
            else:
                if (
                    derniere_date_vue is not None
                    and derniere_mise_a_jour == derniere_date_vue
                ):
                    journal.info(
                        "Relevé ignoré (last_updated inchangé : %s)",
                        derniere_mise_a_jour.isoformat(),
                    )
                else:
                    ajouter_releves_stations(
                        dossier_historique,
                        derniere_mise_a_jour,
                        releves,
                    )
                    derniere_date_vue = derniere_mise_a_jour
                    releves_enregistres += 1
                    journal.info(
                        "Relevé #%d enregistré (%d stations)",
                        releves_enregistres,
                        len(releves),
                    )

            if une_seule_fois:
                break

            maintenant = fonction_heure_actuelle()
            if echeance is not None and maintenant >= echeance:
                break

            temps_ecoule = (maintenant - debut_cycle).total_seconds()
            secondes_attente = max(0.0, intervalle_secondes - temps_ecoule)

            if echeance is not None:
                temps_restant = (echeance - maintenant).total_seconds()
                if temps_restant <= 0:
                    break
                secondes_attente = min(secondes_attente, temps_restant)

            if secondes_attente > 0:
                fonction_pause(secondes_attente)

    except KeyboardInterrupt:
        journal.info("Collecte interrompue par l'utilisateur (Ctrl+C).")

    fin = fonction_heure_actuelle()
    return BilanCollecte(
        releves_enregistres=releves_enregistres,
        debut=debut,
        fin=fin,
    )