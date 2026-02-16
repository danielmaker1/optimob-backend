"""
V6 domain constraints. Dataclasses only. No FastAPI, no external deps beyond dataclasses/typing.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class StructuralConstraints:
    assign_radius_m: float
    max_cluster_size: int
    bus_capacity: int
    min_shuttle_occupancy: float
    detour_cap: float
    backfill_max_delta_min: float


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
