"""
V6 domain constraints. Dataclasses only. No FastAPI, no external deps beyond dataclasses/typing.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class StructuralConstraints:
    assign_radius_m: float
    max_cluster_size: int
    bus_capacity: int
    min_shuttle_occupancy: float
    detour_cap: float
    backfill_max_delta_min: float
    # Block 4 cobertura (opcionales)
    min_ok_far_m: Optional[float] = None  # distancia (m) a oficina para usar min_ok_far en zona lejana
    min_ok_far: Optional[int] = None  # min miembros por cluster en zona lejana (ej. 6)
    pair_radius_m: Optional[float] = None  # radio (m) para reabsorber residual en paradas; mayor = más cobertura
    assign_by_stop_radius_after: Optional[bool] = None  # True = segundo paso: asignar residual por distancia a centro de parada


@dataclass(frozen=True)
class TriggerPolicy:
    min_occupancy_threshold: float
    cost_increase_threshold: float
    coverage_threshold: float
    consecutive_days_required: int


@dataclass(frozen=True)
class AllocationPolicy:
    prioritize_no_alternative: bool
    use_reservation_order: bool


# Carpool 6B: parámetros de matching (V4 CFG_MATCH)
@dataclass(frozen=True)
class CarpoolMatchConfig:
    dbscan_eps_m: float = 500.0
    dbscan_min_samples: int = 3
    mp_cluster_eps_m: float = 300.0
    max_walk_m: float = 800.0
    k_mp_pax: int = 5
    max_detour_min: float = 25.0
    max_detour_ratio: float = 1.6
    alpha_walk: float = 1.0
    beta_detour: float = 60.0
    gamma_eta_off: float = 2.0
    delta_occupancy_bonus: float = 50.0
    max_drivers_per_mp: int = 40
    min_passengers_per_driver: int = 1
    do_2opt: bool = True
