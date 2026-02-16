"""
V5 – Carpooling (MVP)
Permite que un conductor cree una ruta de carpooling
almacenada en memoria como recurso del sistema.
Temporal: reemplazar por persistencia real en producción.
"""

from typing import Any, Dict, List

from backend.v5.carpool_store import IN_MEMORY_CARPOOL_ROUTES

# CARPOOL OPERATIONAL STATE TRANSITION (MVP)
# Allowed statuses for carpool_route; /today reflects this for carpool_driver.
ALLOWED_CARPOOL_STATUSES = {"active", "in_progress", "completed"}


def create_carpool_route(
    driver_id: str,
    capacity: int,
    stops: List[Dict[str, Any]],
    date: str,
    time: str,
) -> dict:
    """
    Crea una ruta de carpooling y la guarda en el store en memoria (MVP).
    El conductor queda registrado como dueño de la ruta.
    El rol carpool_driver en /today dependerá de que la fecha de la ruta sea la del día consultado.

    Args:
        driver_id: ID del usuario conductor.
        capacity: Capacidad máxima del vehículo.
        stops: Lista de paradas [{"name": str, "lat": float, "lng": float}].
        date: Fecha de la ruta (formato "YYYY-MM-DD").
        time: Hora de la ruta (formato "HH:MM").

    Returns:
        La ruta creada con route_id, driver_id, capacity, stops, date, time, status.
    """
    # Generar identificador simple para la ruta (MVP: un conductor, una ruta activa).
    route_id = f"carpool_{driver_id}"

    route = {
        "route_id": route_id,
        "driver_id": driver_id,
        "capacity": capacity,
        "stops": stops,
        "status": "active",
        "date": date,   # Rol carpool_driver solo si route["date"] == día consultado (MVP)
        "time": time,
        "passengers": [],  # Pasajeros asignados (recurso colectivo MVP)
    }

    # Almacenar en memoria (temporal; sustituir por DB en producción).
    IN_MEMORY_CARPOOL_ROUTES[route_id] = route

    return route


def assign_mock_passengers(driver_id: str, passengers: List[str]) -> dict:
    """
    Asigna pasajeros a la ruta del conductor (MVP: asignación simulada en memoria).
    Respeta la capacidad de la ruta. Cada pasajero se añade con status "pending".

    Args:
        driver_id: ID del conductor (dueño de la ruta).
        passengers: Lista de user_id de pasajeros a asignar.

    Returns:
        La ruta actualizada con los pasajeros añadidos (respetando capacity).

    Raises:
        ValueError: Si no existe ruta para el driver_id.
    """
    route_id = f"carpool_{driver_id}"
    if route_id not in IN_MEMORY_CARPOOL_ROUTES:
        raise ValueError(f"No carpool route found for driver {driver_id}")

    route = IN_MEMORY_CARPOOL_ROUTES[route_id]
    capacity = route["capacity"]
    current = route.setdefault("passengers", [])

    # MVP: asignación simulada; respetar capacity (plazas para pasajeros).
    slots_left = max(0, capacity - len(current))
    for user_id in passengers[:slots_left]:
        current.append({"user_id": user_id, "status": "pending"})

    return route


def update_carpool_status(driver_id: str, new_status: str) -> dict:
    """
    CARPOOL OPERATIONAL STATE TRANSITION (MVP).
    Actualiza el estado operativo de la ruta (active | in_progress | completed).
    /today reflejará este estado en result["status"], result["trips"][0]["status"]
    y result["carpool_route"]["status"] para carpool_driver.
    No modifica passengers, capacity, date ni time.
    """
    if new_status not in ALLOWED_CARPOOL_STATUSES:
        raise ValueError(
            f"Invalid status {new_status!r}; allowed: {sorted(ALLOWED_CARPOOL_STATUSES)}"
        )

    route_id = f"carpool_{driver_id}"
    if route_id not in IN_MEMORY_CARPOOL_ROUTES:
        raise ValueError("Carpool route not found")

    route = IN_MEMORY_CARPOOL_ROUTES[route_id]
    route["status"] = new_status
    return route
