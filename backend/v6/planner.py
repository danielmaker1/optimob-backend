"""
V6 – Decision Engine planner. Scaffold only. No implementation.
"""

from backend.v6.models import CarpoolGroup, Employee, ShuttleRoute


def generate_shuttle_routes(population: list[Employee]) -> list[ShuttleRoute]:
    """Scaffold. Returns empty list."""
    return []


def detect_residual_population(
    population: list[Employee],
    shuttle_routes: list[ShuttleRoute],
) -> list[Employee]:
    """Scaffold. Returns empty list."""
    return []


def generate_carpool_groups(
    residual_population: list[Employee],
) -> list[CarpoolGroup]:
    """Scaffold. Returns empty list."""
    return []


def rank_options_for_employee(
    employee: Employee,
    shuttle_routes: list[ShuttleRoute],
    carpool_groups: list[CarpoolGroup],
) -> list[dict]:
    """Scaffold. Returns empty list."""
    return []
