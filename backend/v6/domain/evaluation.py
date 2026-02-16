"""
V6 evaluation. Pure scoring. No I/O.
"""

import math
from backend.v6.domain.models import CarpoolOption, ShuttleOption

_EARTH_RADIUS_KM = 6371.0


def _cluster_radius_km(option: ShuttleOption, employees_by_id: dict) -> float:
    """Approximate radius of cluster in km (max distance from centroid to member)."""
    if not option.employee_ids:
        return 0.0
    rad = 0.0
    for eid in option.employee_ids:
        e = employees_by_id.get(eid)
        if e is None:
            continue
        lat1, lon1 = math.radians(option.centroid_lat), math.radians(option.centroid_lng)
        lat2, lon2 = math.radians(e.home_lat), math.radians(e.home_lng)
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        c = 2 * math.asin(math.sqrt(min(1.0, a)))
        d_km = _EARTH_RADIUS_KM * c
        if d_km > rad:
            rad = d_km
    return rad


def evaluate_shuttle(option: ShuttleOption, employees_by_id: dict | None = None) -> float:
    """
    Score: higher is better.
    - Size: more employees = better (linear).
    - Compactness: smaller radius = better (inverse).
    Simple formula: size / (1 + radius_km).
    """
    size = option.estimated_size
    if size == 0:
        return 0.0
    employees_by_id = employees_by_id or {}
    radius_km = _cluster_radius_km(option, employees_by_id)
    return size / (1.0 + radius_km)


def evaluate_carpool(option: CarpoolOption) -> float:
    """
    Score: higher is better.
    - Occupancy ratio: (1 + passengers) / capacity_like (we treat 4 as typical capacity).
    - Driver existence: must have driver_id.
    """
    if not option.driver_id:
        return 0.0
    capacity = 4
    n = 1 + len(option.passenger_ids)
    occupancy = n / capacity if capacity else 0.0
    return occupancy
