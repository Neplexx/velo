import json
from pathlib import Path

from velo.models import VeloError

MAX_FAVORITES = 10


class FavoriteError(VeloError):
    """Erreur métier liée aux stations favorites"""


def obtenir_chemin_favori(network_dir: Path) -> Path:
    """Retourne le chemin vers le fichier favorites.json"""
    return network_dir / "favorites.json"


def charger_favori(favorites_path: Path) -> list[str]:
    """Lit la liste des IDs favoris depuis favorites.json."""
    if not favorites_path.exists():
        return []

    try:
        text = favorites_path.read_text(encoding="utf-8")
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise FavoriteError("Le fichier des favoris est corrompu.") from exc

    if not isinstance(data, list):
        raise FavoriteError("Format invalide dans le fichier des favoris.")

    return [str(station_id) for station_id in data]


def enregistrer_favori(favorites_path: Path, favorites: list[str]) -> None:
    """Écrit la liste des IDs favoris"""
    favorites_path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(favorites, ensure_ascii=False, indent=2)
    favorites_path.write_text(content, encoding="utf-8")


def ajouter_favori(
    favorites_path: Path,
    station_id: str,
    valid_station_ids: set[str],
) -> list[str]:
    """Ajoute une station aux favoris"""
    if station_id not in valid_station_ids:
        raise FavoriteError(
            f"Station '{station_id}' inconnue. "
            "Utilisez 'velo station search <nom>' pour trouver son identifiant."
        )

    favorites = charger_favori(favorites_path)

    if station_id in favorites:
        raise FavoriteError(f"La station '{station_id}' est déjà dans vos favoris.")

    if len(favorites) >= MAX_FAVORITES:
        raise FavoriteError(
            f"Limite de {MAX_FAVORITES} favoris atteinte. "
            "Retirez-en un avec 'velo favorites remove <id>'."
        )

    favorites.append(station_id)
    enregistrer_favori(favorites_path, favorites)
    return favorites


def retirer_favori(favorites_path: Path, station_id: str) -> list[str]:
    """Supprime une station des favoris."""
    favorites = charger_favori(favorites_path)

    if station_id not in favorites:
        raise FavoriteError(f"La station '{station_id}' n'est pas dans vos favoris.")

    favorites.remove(station_id)
    enregistrer_favori(favorites_path, favorites)
    return favorites