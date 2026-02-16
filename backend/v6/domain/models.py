"""
V6 domain models. Dataclasses only. No FastAPI, no Pydantic.
"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=False)
class Employee:
    employee_id: str
    home_lat: float
    home_lng: float
    work_lat: float
    work_lng: float
    arrival_window_start: str
    arrival_window_end: str
    willing_driver: bool


@dataclass
class ShuttleOption:
    option_id: str
    employee_ids: list[str]
    centroid_lat: float
    centroid_lng: float
    estimated_size: int


@dataclass
class CarpoolOption:
    option_id: str
    driver_id: str
    passenger_ids: list[str]
    estimated_size: int


@dataclass
class AssignmentResult:
    selected_shuttles: list[ShuttleOption]
    selected_carpools: list[CarpoolOption]
    unassigned_employee_ids: list[str]


@dataclass
class DailyPlan:
    date: str
    shuttle_routes: list[dict[str, Any]]
    carpool_routes: list[dict[str, Any]]
    unassigned: list[str]
