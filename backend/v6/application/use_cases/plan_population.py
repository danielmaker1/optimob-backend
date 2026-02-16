"""
V6 plan population use case. Orchestrates domain. No FastAPI.
"""

from datetime import date

from backend.v6.domain.assignment import solve_assignment
from backend.v6.domain.evaluation import evaluate_carpool, evaluate_shuttle
from backend.v6.domain.models import DailyPlan, Employee
from backend.v6.domain.option import generate_carpool_candidates, generate_shuttle_candidates


def plan_population(employees: list[Employee], plan_date: str | None = None) -> DailyPlan:
    """
    Flow: shuttle_candidates -> residual -> carpool_candidates -> evaluate -> solve_assignment -> DailyPlan.
    """
    if plan_date is None:
        plan_date = date.today().isoformat()

    all_ids = [e.employee_id for e in employees]
    employees_by_id = {e.employee_id: e for e in employees}

    shuttle_candidates = generate_shuttle_candidates(employees)
    shuttle_scored = [(opt, evaluate_shuttle(opt, employees_by_id)) for opt in shuttle_candidates]

    assigned_by_shuttles: set[str] = set()
    for opt in shuttle_candidates:
        assigned_by_shuttles.update(opt.employee_ids)
    residual = [e for e in employees if e.employee_id not in assigned_by_shuttles]

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

    return DailyPlan(
        date=plan_date,
        shuttle_routes=shuttle_routes,
        carpool_routes=carpool_routes,
        unassigned=assignment.unassigned_employee_ids,
    )
