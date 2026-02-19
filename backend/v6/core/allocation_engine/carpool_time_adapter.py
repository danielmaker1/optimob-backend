"""
Adapter de tiempos y distancias para carpool (6A/6B).
Implementación por defecto: Haversine + velocidad constante (sin OSM).
"""

import math
from typing import Protocol


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R_KM = 6371.0
    lat1_r = math.radians(lat1)
    lat2_r = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.asin(min(1.0, math.sqrt(a)))
    return R_KM * c


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    return haversine_km(lat1, lon1, lat2, lon2) * 1000.0


class CarpoolTimeAdapter(Protocol):
    """Protocolo para tiempo (min) y distancia a pie (m)."""

    def tt_min(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Tiempo de viaje en minutos entre dos puntos (conduciendo o aprox)."""
        ...

    def walk_dist_m(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Distancia a pie en metros (línea recta)."""
        ...


class HaversineCarpoolAdapter:
    """Adapter Haversine: tt_min = distancia_km / speed_kmh * 60; walk = Haversine m."""

    def __init__(self, speed_kmh: float = 30.0):
        self.speed_kmh = max(1.0, speed_kmh)

    def tt_min(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        km = haversine_km(lat1, lon1, lat2, lon2)
        return (km / self.speed_kmh) * 60.0

    def walk_dist_m(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        return haversine_m(lat1, lon1, lat2, lon2)
