from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from velo.models import Station, StationInfo, est_plein, est_vide, pas_service


@dataclass
class NetworkStats:
    """Résultat des calculs globaux du réseau"""

    nom_reseau: str
    derniere_actualisation: datetime
    total_stations: int
    en_service: int
    hors_service: int
    stations_vides: int
    stations_pleines: int
    velos_disponibles: int
    places_libres_pour_depot_velo: int
    taux_remplissage_pourcentage: float


@dataclass
class StationAlert:
    """Représente une station en alerte."""

    station_id: str
    name: str
    value: int 


@dataclass
class AlertsReport:
    """Les 3 catégories d'alertes triées sans doublon."""

    nom_reseau: str
    derniere_actualisation: datetime
    hors_service: list[StationAlert]
    station_peu_velo: list[StationAlert]
    station_peu_place: list[StationAlert]

    @property
    def has_alerts(self) -> bool:
        """True s'il existe au moins une alerte dans l'une des 3 listes."""
        return bool(self.hors_service or self.station_peu_velo or self.station_peu_place)


@dataclass
class FavoriteStatus:
    """État d'une station favorite et variation depuis le dernier relevé."""

    station_id: str
    name: str
    bikes: int
    docks: int
    state_label: str  # "hors service", "vide", "pleine" ou "OK"
    bikes_delta: int | None = None
    docks_delta: int | None = None


def convertir_timestamp(unix_timestamp: int, timezone_name: str = "Europe/Paris") -> datetime:
    """Convertit un timestamp Unix en objet datetime avec fuseau horaire."""
    try:
        tz = ZoneInfo(timezone_name)
        return datetime.fromtimestamp(unix_timestamp, tz=tz)
    except ZoneInfoNotFoundError:
        # Sécurité sous Windows si la base des fuseaux horaires n'est pas installée
        return datetime.fromtimestamp(unix_timestamp).astimezone()


def construire_table_noms(stations_info: list[StationInfo]) -> dict[str, str]:
    """Associe chaque station_id à son nom pour un accès rapide."""
    return {info.station_id: info.name for info in stations_info}


def calculer_stats_reseau(
    nom_reseau: str,
    last_updated: int,
    stations: list[Station],
    timezone_name: str = "Europe/Paris",
) -> NetworkStats:
    """Calcule les statistiques globales du réseau à partir de la liste des stations."""
    total = len(stations)
    hors_service = 0
    empty = 0
    full = 0
    bikes = 0
    docks = 0

    for st in stations:
        if pas_service(st):
            hors_service += 1
            continue

        bikes += st.num_bikes_available
        docks += st.num_docks_available

        # Pour 'velo status', une station vide a 0 vélo et une pleine a 0 place
        if est_vide(st, nbr_velo=0):
            empty += 1
        if est_plein(st, nbr_place=0):
            full += 1

    en_service = total - hors_service
    capacite_active = bikes + docks
    taux_remplissage = (bikes / capacite_active * 100.0) if capacite_active > 0 else 0.0

    return NetworkStats(
        nom_reseau=nom_reseau,
        derniere_actualisation=convertir_timestamp(last_updated, timezone_name),
        total_stations=total,
        en_service=en_service,
        hors_service=hors_service,
        stations_vides=empty,
        stations_pleines=full,
        velos_disponibles=bikes,
        places_libres_pour_depot_velo=docks,
        taux_remplissage_pourcentage=round(taux_remplissage, 1),
    )


def calculer_alertes(
    nom_reseau: str,
    last_updated: int,
    stations: list[Station],
    station_names: dict[str, str],
    station_peu_velo_seuil: int,
    station_peu_place_seuil: int,
    timezone_name: str = "Europe/Paris",
) -> AlertsReport:
    """Classe les stations en alerte"""
    hs_list: list[StationAlert] = []
    bikes_list: list[StationAlert] = []
    docks_list: list[StationAlert] = []

    for st in stations:
        name = station_names.get(st.station_id, f"Station {st.station_id}")

        if pas_service(st):
            hs_list.append(StationAlert(st.station_id, name, 0))
        elif est_vide(st, nbr_velo=station_peu_velo_seuil):
            bikes_list.append(StationAlert(st.station_id, name, st.num_bikes_available))
        elif est_plein(st, nbr_place=station_peu_place_seuil):
            docks_list.append(StationAlert(st.station_id, name, st.num_docks_available))

    return AlertsReport(
        nom_reseau=nom_reseau,
        derniere_actualisation=convertir_timestamp(last_updated, timezone_name),
        hors_service=hs_list,
        station_peu_velo=bikes_list,
        station_peu_place=docks_list,
    )


def calculer_etats_favoris(
    favorite_ids: list[str],
    stations_by_id: dict[str, Station],
    station_names: dict[str, str],
    previous_stations_by_id: dict[str, Station] | None = None,
) -> list[FavoriteStatus]:
    """Calcule l'état et l'évolution des stations favorites."""
    rows: list[FavoriteStatus] = []

    for station_id in favorite_ids:
        st = stations_by_id.get(station_id)
        if st is None:
            continue

        name = station_names.get(station_id, f"Station {station_id}")

        if pas_service(st):
            label = "hors service"
        elif est_vide(st, nbr_velo=0):
            label = "vide"
        elif est_plein(st, nbr_place=0):
            label = "pleine"
        else:
            label = "OK"

        bikes_delta: int | None = None
        docks_delta: int | None = None
        if previous_stations_by_id and station_id in previous_stations_by_id:
            prev = previous_stations_by_id[station_id]
            bikes_delta = st.num_bikes_available - prev.num_bikes_available
            docks_delta = st.num_docks_available - prev.num_docks_available

        rows.append(
            FavoriteStatus(
                station_id=station_id,
                name=name,
                bikes=st.num_bikes_available,
                docks=st.num_docks_available,
                state_label=label,
                bikes_delta=bikes_delta,
                docks_delta=docks_delta,
            )
        )

    return rows