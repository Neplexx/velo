"""Données depuis le Json pour en faire le structure du projet"""

from pathlib import Path
from typing import Literal

from platformdirs import user_data_dir
from pydantic import BaseModel, Field


#modèle d'une station et ses fonctions d'états
class Station(BaseModel):
    """état d'une station (infos qui varient)"""
    station_id: str
    num_bikes_available: int = Field(default=0, ge=0) #nbr de vélo dispo
    num_docks_available: int = Field(default=0, ge=0) #nbr de place dispo
    is_installed: bool = True
    is_renting: bool = True
    is_returning: bool = True
    last_reported: int | None = None

class StationInfo(BaseModel):
    """Infos d'une station (infos statiques)"""
    station_id: str
    name: str
    lat: float
    lon: float
    capacity: int = Field(default=0, ge=0)
    address: str | None = None
    post_code: str | None = None

def pas_service(station: Station) -> bool:
    """True si la station est hors service"""
    install = station.is_installed
    rendre_et_prendre = station.is_renting and station.is_returning
    return bool(not install or not rendre_et_prendre)

def est_vide(station: Station, nbr_velo: int = 2) -> bool:
    """True si la station est vide ou presque vide (velo <= 2)"""
    hors_service = pas_service(station)
    est_presque_vide = station.num_bikes_available <= nbr_velo
    return bool(not hors_service and est_presque_vide)

def est_plein(station: Station, nbr_place: int = 2) -> bool:
    """True si la station est pleine ou presque pleine (place <=2)"""
    hors_service = pas_service(station)
    est_presque_pleine = station.num_docks_available <= nbr_place
    return bool(not hors_service and est_presque_pleine)


#fichier config.yaml

class Network(BaseModel):
    name: str = "vlille"
    gbfs_url: str = "https://media.ilevia.fr/opendata/gbfs.json"

class Data(BaseModel):
    folder: Path = Field(default_factory=lambda: Path(user_data_dir("velo")))

class Refresh(BaseModel):
    max_age_days: int = Field(default=7, ge=1)

class Collect(BaseModel):
    interval_seconds: int = Field(default=60, ge=60)

class Alerts(BaseModel):
    low_bikes: int = Field(default=2, ge=0)
    low_docks: int = Field(default=2, ge=0)

class Dashboard(BaseModel):
    refresh_seconds: int = Field(default=60, ge=60)

class Logging(BaseModel):
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

class AppConfig(BaseModel):
    """config du fichier"""
    network: Network = Field(default_factory=Network)
    data: Data = Field(default_factory=Data)
    refresh: Refresh = Field(default_factory=Refresh)
    collect: Collect = Field(default_factory=Collect)
    alerts: Alerts = Field(default_factory=Alerts)
    dashboard: Dashboard = Field(default_factory=Dashboard)
    logging: Logging = Field(default_factory=Logging)

#Infos GBFS

class SystemInfo(BaseModel):
    """données du réseaux"""
    system_id: str
    name: str
    timezone: str
    language: str | None = None

class GBFS(BaseModel):
    """Instantané complet d'un rafraîchissement GBFS"""
    last_updated: int
    system_info: SystemInfo
    stations_info: list[StationInfo]
    stations: list[Station]

#Récupération de l'erreur 

class VeloError(Exception):
    """Erreur gérée par message et code"""

    def __init__(self, message: str, exit_code: int = 1) -> None:
        super().__init__(message)
        self.message = message
        self.exit_code = exit_code