"""Smoke test: plan_population con Block 4 en primera línea."""
from backend.v6.domain.models import Employee
from backend.v6.application.use_cases.plan_population import plan_population

employees = [
    Employee("e1", 40.42, -3.70, False),
    Employee("e2", 40.43, -3.71, False),
    Employee("e3", 40.44, -3.72, True),
]
plan = plan_population(employees, include_shadow_metrics=True)
print("OK:", plan.date, "shuttles:", len(plan.shuttle_routes), "carpools:", len(plan.carpool_routes), "shadow:", plan.shuttle_shadow_metrics)
