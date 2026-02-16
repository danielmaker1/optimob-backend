"""
V6 population loader. Raw dict -> domain Employee. No domain logic.
"""

from backend.v6.domain.models import Employee


def load_employees(raw_employees: list[dict]) -> list[Employee]:
    """Transform raw list of dicts into list[Employee]. No validation beyond types."""
    result: list[Employee] = []
    for raw in raw_employees:
        result.append(
            Employee(
                employee_id=str(raw.get("employee_id", "")),
                home_lat=float(raw.get("home_lat", 0.0)),
                home_lng=float(raw.get("home_lng", 0.0)),
                work_lat=float(raw.get("work_lat", 0.0)),
                work_lng=float(raw.get("work_lng", 0.0)),
                arrival_window_start=str(raw.get("arrival_window_start", "")),
                arrival_window_end=str(raw.get("arrival_window_end", "")),
                willing_driver=bool(raw.get("willing_driver", False)),
            )
        )
    return result
