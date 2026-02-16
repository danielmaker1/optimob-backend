"""
V6 API request/response schemas. Pydantic only in api layer.
"""

from pydantic import BaseModel


class EmployeeSchema(BaseModel):
    employee_id: str
    home_lat: float
    home_lng: float
    work_lat: float
    work_lng: float
    arrival_window_start: str
    arrival_window_end: str
    willing_driver: bool


class PlanRequest(BaseModel):
    employees: list[EmployeeSchema]
    date: str | None = None


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
