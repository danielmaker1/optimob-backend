"""
V6 API router. Calls application only. No business logic.
"""

from fastapi import APIRouter, HTTPException

from backend.v6.api.schemas import DailyPlanSchema, PlanRequest
from backend.v6.application.use_cases.plan_population import plan_population
from backend.v6.infrastructure.population_loader import load_employees

router = APIRouter()


@router.post("/plan", response_model=DailyPlanSchema)
def post_plan(request: PlanRequest) -> DailyPlanSchema:
    """
    POST /v6/plan
    Accepts list of employees. Returns DailyPlan.
    """
    try:
        raw = [e.model_dump() for e in request.employees]
        employees = load_employees(raw)
        plan = plan_population(employees, plan_date=request.date)
        return DailyPlanSchema(
            date=plan.date,
            shuttle_routes=plan.shuttle_routes,
            carpool_routes=plan.carpool_routes,
            unassigned=plan.unassigned,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
