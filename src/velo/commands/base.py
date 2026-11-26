"""Commandes de base : init, refresh, station list et station search."""
import re
from pathlib import Path

from rich.console import Console
from rich.table import Table

from velo.config import save_config
from velo.gbfs import recuperer_gbfs
from velo.models import (
    AppConfig,
    Station,
    StationInfo,
    VeloError,
    est_plein,
    est_vide,
    pas_service,
)

console = Console()

def statut_station(station: Station, config: AppConfig) -> str:
    """Retourne en couleur l'état d'une station"""
    if pas_service(station):
        return "[red]Hors service[/red]"
    if est_vide(station, config.alerts.low_bikes):
        return "[yellow]Peu de vélos[/yellow]"
    if est_plein(station, config.alerts.low_docks):
        return "[yellow]Peu de places[/yellow]"
    return "[green]OK[/green]"

def afficher_stations(paires: list, config: AppConfig, titre: str) -> None:
    """Affiche la liste des stations dans un tableau"""
    table = Table(title=titre)
    table.add_column("ID", style="cyan")
    table.add_column("Nom")
    table.add_column("Vélos", justify="right")
    table.add_column("Places", justify="right")
    table.add_column("Statut")

    for info, station in paires:
        table.add_row(
            info.station_id,
            info.name,
            str(station.num_bikes_available),
            str(station.num_docks_available),
            statut_station(station, config),
        )
    console.print(table)

def init(config: AppConfig, config_path: Path | None = None, force: bool = False) -> None:
    """Crée le fichier config.yaml par défaut"""
    chemin = save_config(config, config_path=config_path, force=force)
    console.print(f"[green]Configuration créée :[/green] {chemin}")

def refresh(config: AppConfig) -> None:
    """Télécharge les données de gbfs"""
    gbfs = recuperer_gbfs(config.network.gbfs_url)
    config.data.folder.mkdir(parents=True, exist_ok=True)
    cache_path = config.data.folder / "gbfs_cache.json" #enregistre le cache pour ne pas tout re télécharger tout le temps
    cache_path.write_text(gbfs.model_dump_json(indent=2), encoding="utf-8")
    console.print(f"[green]Données rafraîchies :[/green] {gbfs.system_info.name} ", f"({len(gbfs.stations)} stations) -> {cache_path}")

def joindre_stations(config: AppConfig) -> list[tuple[StationInfo, Station]]:
    """Récupère les stations et associe chaque StationInfo à son Station."""
    gbfs = recuperer_gbfs(config.network.gbfs_url)
    etats = {station.station_id: station for station in gbfs.stations}
    paires = []
    for info in gbfs.stations_info:
        if info.station_id in etats:
            paires.append((info, etats[info.station_id]))
    return paires

def station_liste(config: AppConfig) -> None:
    """Récupère et affiche toutes les stations"""
    paires = joindre_stations(config)
    afficher_stations(paires, config, f"Stations ({len(paires)})")

def station_cherche(config: AppConfig, texte: str) -> None:
    """Recherche les stations avec le nom"""
    try:
        motif = re.compile(texte, re.IGNORECASE) #enlève les maj etc
    except re.error as e:
        raise VeloError(f"Expression régulière invalide '{texte}' : {e}") from e
    paires = joindre_stations(config)
    trouvees = [(info, station) for info, station in paires if motif.search(info.name)]
    if not trouvees:
        console.print(f"[yellow]Aucune station trouvée pour '{texte}'.[/yellow]")
        return
    afficher_stations(trouvees, config, f"Résultats pour '{texte}' ({len(trouvees)})")