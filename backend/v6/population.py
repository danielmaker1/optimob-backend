"""
V6 – Population modeling. Transformation only.
"""

from backend.v6.models import Employee


def load_population(raw_employees: list[dict]) -> list[Employee]:
    """
    Transform raw employee dicts into list of Employee.
    No clustering. Only transformation.
    """
    result: list[Employee] = []
    for raw in raw_employees:
        result.append(
            Employee(
                id=str(raw.get("id", "")),
                home_lat=float(raw.get("home_lat", 0.0)),
                home_lng=float(raw.get("home_lng", 0.0)),
                time_window_start=str(raw.get("time_window_start", "")),
                time_window_end=str(raw.get("time_window_end", "")),
                can_drive=bool(raw.get("can_drive", False)),
            )
        )
    return result
