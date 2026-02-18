"""
V6 domain models. Dataclasses only. No FastAPI, no external deps beyond dataclasses/typing.
"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class Employee:
    employee_id: str
    home_lat: float
    home_lng: float
    willing_driver: bool


@dataclass(frozen=True)
class ShuttleOption:
    option_id: str
    employee_ids: List[str]
    centroid_lat: float
    centroid_lng: float
    estimated_size: int


@dataclass(frozen=True)
class CarpoolOption:
    option_id: str
    driver_id: str
    passenger_ids: List[str]
    estimated_size: int


@dataclass
class AssignmentResult:
    selected_shuttles: List[ShuttleOption]
    selected_carpools: List[CarpoolOption]
    unassigned_employee_ids: List[str]


@dataclass
class DailyPlan:
    date: str
    shuttle_routes: List[dict]
    carpool_routes: List[dict]
    unassigned: List[str]
    # Modo sombra: métricas del clustering legacy (generate_shuttle_candidates) para comparación
    shuttle_shadow_metrics: Optional[dict] = None  # {"n_clusters": int, "coverage_pct": float}


@dataclass
class ShuttleStop:
    stop_id: str
    lat: float
    lng: float
    employee_ids: List[str]


@dataclass
class ShuttleRoute:
    route_id: str
    stop_ids: List[str]
    employee_ids: List[str]
    capacity: int


@dataclass
class NetworkDesign:
    week_id: str
    stops: List[ShuttleStop]
    routes: List[ShuttleRoute]
    baseline_cost_per_seat: float


@dataclass(frozen=True)
class Reservation:
    employee_id: str
    date: str


@dataclass
class DailyAllocation:
    date: str
    shuttle_assignments: dict[str, str]  # employee_id -> route_id
    overflow_carpool: List[str]  # employee_ids
    occupancy_by_route: dict[str, float]  # route_id -> float
    cost_per_seat: float
