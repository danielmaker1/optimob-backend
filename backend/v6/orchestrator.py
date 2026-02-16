"""
V6 – Decision Engine orchestrator.
"""

from backend.v6.models import Employee
from backend.v6.planner import (
    detect_residual_population,
    generate_carpool_groups,
    generate_shuttle_routes,
)


def build_daily_plan(population: list[Employee]) -> dict:
    """
    1. Generate shuttle routes.
    2. Detect residual population.
    3. Generate carpool groups.
    4. Return structured dict. No ranking yet.
    """
    shuttle_routes = generate_shuttle_routes(population)
    residual = detect_residual_population(population, shuttle_routes)
    carpool_groups = generate_carpool_groups(residual)
    return {
        "shuttle_routes": [
            {
                "id": r.id,
                "stops": r.stops,
                "capacity": r.capacity,
                "assigned_employee_ids": r.assigned_employee_ids,
            }
            for r in shuttle_routes
        ],
        "carpool_groups": [
            {
                "driver_id": g.driver_id,
                "passenger_ids": g.passenger_ids,
                "capacity": g.capacity,
            }
            for g in carpool_groups
        ],
        "population_size": len(population),
    }
