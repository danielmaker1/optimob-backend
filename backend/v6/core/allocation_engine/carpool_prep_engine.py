"""
Carpool prep (6A). Residual de Block 4 → censo carpool (conductores y pasajeros).

Sin grafo OSM; el routing usa el adapter de tiempos inyectado en 6B.
"""

from typing import List

from backend.v6.domain.models import CarpoolPerson, Employee


def run_carpool_prep(
    residual_employees: List[Employee],
    office_lat: float,
    office_lng: float,
    default_seats_driver: int = 3,
) -> List[CarpoolPerson]:
    """
    Convierte el residual (empleados no shuttle) en censo carpool.

    - Conductor: willing_driver=True, seats_driver=default_seats_driver, cap_efectiva=seats_driver-1.
    - Pasajero: willing_driver=False, seats_driver=0, cap_efectiva=0.
    Solo se incluyen driver y pax (quien tiene coche pero 0 asientos se excluye).
    """
    census: List[CarpoolPerson] = []
    for e in residual_employees:
        is_driver = e.willing_driver
        if is_driver:
            seats = max(0, default_seats_driver)
            cap_eff = max(0, seats - 1)
        else:
            seats = 0
            cap_eff = 0
        # Solo añadir si es conductor con plaza o pasajero
        if is_driver and seats == 0:
            continue
        census.append(
            CarpoolPerson(
                person_id=e.employee_id,
                lat=e.home_lat,
                lng=e.home_lng,
                office_lat=office_lat,
                office_lon=office_lng,
                is_driver=is_driver,
                seats_driver=seats,
                hora_obj_min=e.hora_obj_min,
                cap_efectiva=cap_eff,
            )
        )
    return census
