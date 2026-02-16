"""
V6 domain objective. Pure functions only. No FastAPI, no external deps beyond typing.
Lexicographic: 1. Cost per seat, 2. Coverage, 3. Travel time (placeholder).
"""

from .constraints import TriggerPolicy


def compute_cost_per_seat(total_operating_cost: float, total_assigned: int) -> float:
    if total_assigned <= 0:
        return 0.0
    return total_operating_cost / total_assigned


def compute_coverage(total_employees: int, assigned: int) -> float:
    if total_employees <= 0:
        return 0.0
    return assigned / total_employees


def should_trigger_redesign(
    current_cost: float,
    baseline_cost: float,
    occupancy: float,
    coverage: float,
    policy: TriggerPolicy,
    consecutive_days_below: int,
) -> bool:
    if consecutive_days_below < policy.consecutive_days_required:
        return False
    if occupancy < policy.min_occupancy_threshold:
        return True
    if coverage < policy.coverage_threshold:
        return True
    if baseline_cost <= 0:
        return False
    if current_cost > baseline_cost * (1.0 + policy.cost_increase_threshold):
        return True
    return False
