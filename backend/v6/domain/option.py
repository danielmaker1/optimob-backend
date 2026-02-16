"""
V6 option generation. Pure domain. Deterministic clustering.
No external libraries. Uses math only for Haversine.
"""

import math
from backend.v6.domain.models import CarpoolOption, Employee, ShuttleOption

# Configurable constants (domain parameters)
SHUTTLE_CLUSTER_RADIUS_KM = 1.5
CARPOOL_NEIGHBOR_RADIUS_KM = 3.0
CARPOOL_MAX_PASSENGERS_PER_DRIVER = 3

_EARTH_RADIUS_KM = 6371.0


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance in km between two (lat, lon) points. Deterministic."""
    lat1_r = math.radians(lat1)
    lat2_r = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(min(1.0, a)))
    return _EARTH_RADIUS_KM * c


def generate_shuttle_candidates(employees: list[Employee]) -> list[ShuttleOption]:
    """
    Group employees by geographic proximity. Radius-based clustering.
    Threshold = SHUTTLE_CLUSTER_RADIUS_KM. Each cluster becomes one ShuttleOption.
    Deterministic: order by employee_id when forming clusters.
    """
    if not employees:
        return []
    # Sort for determinism
    sorted_employees = sorted(employees, key=lambda e: e.employee_id)
    assigned: set[str] = set()
    options: list[ShuttleOption] = []
    option_index = 0

    for emp in sorted_employees:
        if emp.employee_id in assigned:
            continue
        # Start a new cluster from this employee (home location)
        cluster_ids = [emp.employee_id]
        assigned.add(emp.employee_id)
        cluster_lats = [emp.home_lat]
        cluster_lngs = [emp.home_lng]

        # Add every other unassigned employee within radius (home-to-home)
        for other in sorted_employees:
            if other.employee_id in assigned:
                continue
            d = _haversine_km(emp.home_lat, emp.home_lng, other.home_lat, other.home_lng)
            if d <= SHUTTLE_CLUSTER_RADIUS_KM:
                cluster_ids.append(other.employee_id)
                assigned.add(other.employee_id)
                cluster_lats.append(other.home_lat)
                cluster_lngs.append(other.home_lng)

        centroid_lat = sum(cluster_lats) / len(cluster_lats)
        centroid_lng = sum(cluster_lngs) / len(cluster_lngs)
        options.append(
            ShuttleOption(
                option_id=f"shuttle_{option_index}",
                employee_ids=cluster_ids,
                centroid_lat=centroid_lat,
                centroid_lng=centroid_lng,
                estimated_size=len(cluster_ids),
            )
        )
        option_index += 1

    return options


def generate_carpool_candidates(residual_employees: list[Employee]) -> list[CarpoolOption]:
    """
    From residual employees only. Each willing_driver forms a CarpoolOption
    with up to CARPOOL_MAX_PASSENGERS_PER_DRIVER nearest passengers within CARPOOL_NEIGHBOR_RADIUS_KM.
    No passenger assigned to more than one driver.
    Deterministic: order by employee_id.
    """
    if not residual_employees:
        return []
    drivers = [e for e in residual_employees if e.willing_driver]
    non_drivers = [e for e in residual_employees if not e.willing_driver]
    if not drivers:
        return []

    sorted_drivers = sorted(drivers, key=lambda e: e.employee_id)
    assigned_passenger_ids: set[str] = set()
    options: list[CarpoolOption] = []
    option_index = 0

    for driver in sorted_drivers:
        # Nearest passengers within radius, not yet assigned
        candidates: list[tuple[float, str, Employee]] = []
        for p in non_drivers:
            if p.employee_id in assigned_passenger_ids:
                continue
            d = _haversine_km(
                driver.home_lat, driver.home_lng,
                p.home_lat, p.home_lng,
            )
            if d <= CARPOOL_NEIGHBOR_RADIUS_KM:
                candidates.append((d, p.employee_id, p))
        candidates.sort(key=lambda x: (x[0], x[1]))
        passenger_ids = [c[1] for c in candidates[:CARPOOL_MAX_PASSENGERS_PER_DRIVER]]
        for pid in passenger_ids:
            assigned_passenger_ids.add(pid)

        options.append(
            CarpoolOption(
                option_id=f"carpool_{option_index}",
                driver_id=driver.employee_id,
                passenger_ids=passenger_ids,
                estimated_size=1 + len(passenger_ids),
            )
        )
        option_index += 1

    return options
