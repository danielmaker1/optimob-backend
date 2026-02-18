"""
V6 plan population use case. Orchestrates domain. No FastAPI.

Primera línea: Block 4 (paradas shuttle viables + carpool).
Sombra: generate_shuttle_candidates opcional para métricas de comparación.
"""

from datetime import date
from typing import Optional

from backend.v6.application.config import (
    DEFAULT_OFFICE_LAT,
    DEFAULT_OFFICE_LNG,
    DEFAULT_STRUCTURAL_CONSTRAINTS,
)
from backend.v6.application.shuttle_candidates import get_shuttle_candidates_block4
from backend.v6.domain.assignment import solve_assignment
from backend.v6.domain.constraints import StructuralConstraints
from backend.v6.domain.evaluation import evaluate_carpool, evaluate_shuttle
from backend.v6.domain.models import DailyPlan, Employee
from backend.v6.domain.option import generate_carpool_candidates, generate_shuttle_candidates


def plan_population(
    employees: list[Employee],
    plan_date: str | None = None,
    office_lat: Optional[float] = None,
    office_lng: Optional[float] = None,
    constraints: Optional[StructuralConstraints] = None,
    include_shadow_metrics: bool = False,
) -> DailyPlan:
    """
    Flow: Block 4 shuttle_candidates + carpool_set -> residual -> carpool_candidates
          -> evaluate -> solve_assignment -> DailyPlan.
    """
    if plan_date is None:
        plan_date = date.today().isoformat()
    if office_lat is None:
        office_lat = DEFAULT_OFFICE_LAT
    if office_lng is None:
        office_lng = DEFAULT_OFFICE_LNG
    if constraints is None:
        constraints = DEFAULT_STRUCTURAL_CONSTRAINTS

    all_ids = [e.employee_id for e in employees]
    employees_by_id = {e.employee_id: e for e in employees}

    # Primera línea: Block 4
    shuttle_candidates, carpool_set = get_shuttle_candidates_block4(
        employees, office_lat, office_lng, constraints
    )
    residual = [e for e in employees if e.employee_id in carpool_set]

    shuttle_scored = [(opt, evaluate_shuttle(opt, employees_by_id)) for opt in shuttle_candidates]

    carpool_candidates = generate_carpool_candidates(residual)
    carpool_scored = [(opt, evaluate_carpool(opt)) for opt in carpool_candidates]

    assignment = solve_assignment(shuttle_scored, carpool_scored, all_ids)

    shuttle_routes = [
        {
            "option_id": s.option_id,
            "employee_ids": s.employee_ids,
            "centroid_lat": s.centroid_lat,
            "centroid_lng": s.centroid_lng,
            "estimated_size": s.estimated_size,
        }
        for s in assignment.selected_shuttles
    ]
    carpool_routes = [
        {
            "option_id": c.option_id,
            "driver_id": c.driver_id,
            "passenger_ids": c.passenger_ids,
            "estimated_size": c.estimated_size,
        }
        for c in assignment.selected_carpools
    ]

    shadow_metrics: Optional[dict] = None
    if include_shadow_metrics and employees:
        shadow_opts = generate_shuttle_candidates(employees)
        n_shadow = len(shadow_opts)
        assigned_shadow = sum(len(o.employee_ids) for o in shadow_opts)
        shadow_metrics = {
            "n_clusters": n_shadow,
            "coverage_pct": (assigned_shadow / len(employees) * 100.0) if employees else 0.0,
        }

    return DailyPlan(
        date=plan_date,
        shuttle_routes=shuttle_routes,
        carpool_routes=carpool_routes,
        unassigned=assignment.unassigned_employee_ids,
        shuttle_shadow_metrics=shadow_metrics,
    )
