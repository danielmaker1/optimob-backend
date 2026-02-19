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
    # Opcional: minuto del día (desde medianoche) para ventana de llegada; usado en carpool (prioridad app/empleado).
    hora_obj_min: Optional[float] = None
    # Opcional: minuto del día (desde medianoche) para ventana de llegada; usado en carpool (prioridad app/empleado).
    hora_obj_min: Optional[float] = None


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


# --- Carpool 6A/6B (V4 Block 6) ---


@dataclass(frozen=True)
class CarpoolPerson:
    """Una persona en el censo carpool: conductor o pasajero."""
    person_id: str
    lat: float
    lng: float
    office_lat: float
    office_lon: float
    is_driver: bool
    seats_driver: int  # 0 si pasajero
    hora_obj_min: Optional[float] = None  # minutos desde medianoche, opcional
    cap_efectiva: int = 0  # max(0, seats_driver - 1) para conductores


@dataclass(frozen=True)
class MeetingPoint:
    """Punto de encuentro carpool (salida de DBSCAN + cluster suave)."""
    id_mp: str
    lat: float
    lng: float


@dataclass(frozen=True)
class CarpoolMatch:
    """Un match (conductor, pasajero, MP) con métricas."""
    driver_id: str
    pax_id: str
    id_mp: str
    mp_lat: float
    mp_lng: float
    walk_m: float
    detour_min: float
    detour_ratio: float
    eta_oficina_min: float
    cost: float


@dataclass
class DriverRoute:
    """Ruta de un conductor: orden de MPs, duración, detour, pax."""
    driver_id: str
    order_mp_ids: List[str]
    total_dur_min: float
    detour_min: float
    detour_ratio: float
    n_pax: int
    pax_by_mp: Optional[dict] = None  # id_mp -> list of pax_id (opcional)


@dataclass
class CarpoolMatchResult:
    """Salida del motor 6B con métricas para observabilidad (MVP frugal)."""
    matches: List[CarpoolMatch]
    driver_routes: List[DriverRoute]
    unmatched_pax_ids: List[str]
    n_mp: int
    n_candidates: int
    n_matches: int
    n_unmatched: int
    duration_ms: float
    unmatched_reasons: Optional[dict] = None  # pax_id -> "no_candidate" | "trimmed_by_detour"


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
