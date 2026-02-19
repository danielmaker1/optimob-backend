"""
V6 population loader. Raw dict -> domain Employee. Merge empresa + overrides (app).
"""

from backend.v6.domain.models import Employee


def _parse_arrival_to_minutes(value: str | None) -> float | None:
    """Convierte 'HH:MM' a minutos desde medianoche. None si vacío o inválido."""
    if not value or not isinstance(value, str):
        return None
    value = value.strip()
    if not value:
        return None
    parts = value.split(":")
    if len(parts) != 2:
        return None
    try:
        h, m = int(parts[0]), int(parts[1])
        if 0 <= h < 24 and 0 <= m < 60:
            return float(h * 60 + m)
    except ValueError:
        pass
    return None


def load_employees(raw_employees: list[dict]) -> list[Employee]:
    """Transform raw list of dicts into list[Employee]. Acepta arrival_window_start para hora_obj_min."""
    result: list[Employee] = []
    for raw in raw_employees:
        hora = _parse_arrival_to_minutes(raw.get("arrival_window_start"))
        result.append(
            Employee(
                employee_id=str(raw.get("employee_id", "")),
                home_lat=float(raw.get("home_lat", 0.0)),
                home_lng=float(raw.get("home_lng", 0.0)),
                willing_driver=bool(raw.get("willing_driver", False)),
                hora_obj_min=hora,
            )
        )
    return result


def build_census_with_overrides(
    base_employees: list[Employee],
    overrides: list[dict],
) -> list[Employee]:
    """
    Censo final con prioridad empleado: por cada empleado, si hay override para su
    employee_id se usan esos valores (solo los presentes); si no, se mantiene el base.
    overrides: lista de dicts con al menos 'employee_id' y opcionalmente
    home_lat, home_lng, willing_driver, arrival_window_start (o hora_obj_min).
    """
    by_id = {e.employee_id: e for e in base_employees}
    override_by_id: dict[str, dict] = {}
    for o in overrides:
        eid = o.get("employee_id")
        if eid is not None:
            override_by_id[str(eid)] = o

    out: list[Employee] = []
    for e in base_employees:
        o = override_by_id.get(e.employee_id)
        if not o:
            out.append(e)
            continue
        home_lat = o.get("home_lat")
        home_lng = o.get("home_lng")
        willing_driver = o.get("willing_driver")
        hora = o.get("hora_obj_min")
        if hora is None and o.get("arrival_window_start") is not None:
            hora = _parse_arrival_to_minutes(str(o["arrival_window_start"]))
        out.append(
            Employee(
                employee_id=e.employee_id,
                home_lat=float(home_lat) if home_lat is not None else e.home_lat,
                home_lng=float(home_lng) if home_lng is not None else e.home_lng,
                willing_driver=bool(willing_driver) if willing_driver is not None else e.willing_driver,
                hora_obj_min=float(hora) if hora is not None else e.hora_obj_min,
            )
        )
    return out
