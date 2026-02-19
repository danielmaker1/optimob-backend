"""
V6 API request/response schemas. Pydantic only in api layer.
"""

from pydantic import BaseModel


class EmployeeSchema(BaseModel):
    employee_id: str
    home_lat: float
    home_lng: float
    work_lat: float = 0.0
    work_lng: float = 0.0
    arrival_window_start: str = ""
    arrival_window_end: str = ""
    willing_driver: bool = False


class EmployeeOverrideSchema(BaseModel):
    """Override por empleado (ej. desde app): prioridad sobre datos empresa. Solo los enviados se aplican."""
    employee_id: str
    home_lat: float | None = None
    home_lng: float | None = None
    willing_driver: bool | None = None
    arrival_window_start: str | None = None  # ej. "09:00" -> hora_obj_min para carpool
    hora_obj_min: float | None = None  # minutos desde medianoche; si se envía, tiene prioridad sobre arrival_window_start


class PlanRequest(BaseModel):
    employees: list[EmployeeSchema]
    date: str | None = None
    include_shadow_metrics: bool = False  # incluir métricas del clustering legacy (generate) en la respuesta
    # Opcional: overrides desde app; se aplican sobre employees (prioridad empleado).
    employee_overrides: list[EmployeeOverrideSchema] | None = None


class ShuttleRouteSchema(BaseModel):
    option_id: str
    employee_ids: list[str]
    centroid_lat: float
    centroid_lng: float
    estimated_size: int


class CarpoolRouteSchema(BaseModel):
    option_id: str
    driver_id: str
    passenger_ids: list[str]
    estimated_size: int


class DailyPlanSchema(BaseModel):
    date: str
    shuttle_routes: list[ShuttleRouteSchema]
    carpool_routes: list[CarpoolRouteSchema]
    unassigned: list[str]
    shuttle_shadow_metrics: dict | None = None  # modo sombra: n_clusters, coverage_pct del clustering legacy
