"""API GBFS"""

import logging

import requests
from pydantic import ValidationError

from velo.models import GBFS, Station, StationInfo, SystemInfo, VeloError

logger = logging.getLogger(__name__)

def recuperer_json(session: requests.Session, url:str, timeout: float = 10.0) -> dict:
    """Télécharge une URL et retourne son contenu JSON en dico"""
    logger.debug("Requete GBFS : %s", url)
    try:
        reponse = session.get(url, timeout=timeout)
        reponse.raise_for_status()
        donnees = reponse.json()
    except (requests.RequestException, ValueError) as e:
        raise VeloError(f"Erreur réseau ou JSON sur {url} : {e}") from e
    
    if not isinstance(donnees, dict): #vérifie que c'est bien un dico
        raise VeloError(f"Réponse JSON invalide sur {url} (dictionnaire voulu)")
    return donnees

def trouver_flux(gbfs_json:dict) -> dict[str, str]:
    """Extrait le dico (flux : url qui donne un json ) depuis le gbfs.json"""
    data = gbfs_json.get("data") #récup la clé data
    if not isinstance(data, dict) or not data:
        raise VeloError("Format gbfs.json invalide, data est absent ou vide")

    if "fr" in data:
        bloc = data["fr"]
    elif "en" in data:
        bloc = data["en"]
    else:
        bloc = next(iter(data.values()))
    if not isinstance(bloc, dict): #vérifie que bloc est bien un dico
        raise VeloError("Format gbfs.json invalide")

    urls = {}
    for flux in bloc.get("feeds", []): #parcourt la liste des fluxs (ou vide si existe pas par sécu)
        if "name" in flux and "url" in flux:
            urls[flux["name"]] = flux["url"] #enregistre les flux valide

    for requis in ("system_information", "station_information", "station_status"):
        if requis not in urls:
            raise VeloError(f"Flux GBFS manquant : {requis}")
    return urls

def recuperer_gbfs(gbfs_url:str, timeout: float=10.0) -> GBFS:
    """Récupère et valide les données GBFS"""
    with requests.Session() as session:
        racine = recuperer_json(session, gbfs_url, timeout=timeout)
        urls = trouver_flux(racine)

        sys_json = recuperer_json(session, urls["system_information"], timeout=timeout)
        info_json = recuperer_json(session, urls["station_information"], timeout=timeout)
        status_json = recuperer_json(session, urls["station_status"], timeout=timeout)
    try:
        system_info = SystemInfo.model_validate(sys_json["data"])
        stations_info = [StationInfo.model_validate(station) for station in info_json["data"]["stations"]]
        stations = [Station.model_validate(station) for station in status_json["data"]["stations"]]
        last_update = int(status_json.get("last_updated") or racine.get("last_updated") or 0)
    except(ValidationError, KeyError, TypeError, ValueError) as e:
        raise VeloError(f"Donnees gbfs invalides : {e}") from e
    logger.info("gbfs chargé : %s (%d stations)", system_info.name, len(stations))
    return GBFS(last_updated=last_update, system_info=system_info, stations_info=stations_info, stations=stations)