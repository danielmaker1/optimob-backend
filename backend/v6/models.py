"""
V6 – Decision Engine Layer – Data models.
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class Employee:
    id: str
    home_lat: float
    home_lng: float
    time_window_start: str
    time_window_end: str
    can_drive: bool


@dataclass
class ShuttleRoute:
    id: str
    stops: list[dict[str, Any]]
    capacity: int
    assigned_employee_ids: list[str]


@dataclass
class CarpoolGroup:
    driver_id: str
    passenger_ids: list[str]
    capacity: int
