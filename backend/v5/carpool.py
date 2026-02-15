"""
V5 – Carpooling (MVP)
Permite que un conductor cree una ruta de carpooling
almacenada en memoria como recurso del sistema.
Temporal: reemplazar por persistencia real en producción.
"""

from typing import Any, Dict, List

from backend.v5.carpool_store import IN_MEMORY_CARPOOL_ROUTES


def create_carpool_route(
    driver_id: str,
    capacity: int,
    stops: List[Dict[str, Any]],
) -> dict:
    """
    Crea una ruta de carpooling y la guarda en el store en memoria (MVP).
    El conductor queda registrado como dueño de la ruta.

    Args:
        driver_id: ID del usuario conductor.
        capacity: Capacidad máxima del vehículo.
        stops: Lista de paradas [{"name": str, "lat": float, "lng": float}].

    Returns:
        La ruta creada con route_id, driver_id, capacity, stops, status.
    """
    # Generar identificador simple para la ruta (MVP: un conductor, una ruta activa).
    route_id = f"carpool_{driver_id}"

    route = {
        "route_id": route_id,
        "driver_id": driver_id,
        "capacity": capacity,
        "stops": stops,
        "status": "active",
    }

    # Almacenar en memoria (temporal; sustituir por DB en producción).
    IN_MEMORY_CARPOOL_ROUTES[route_id] = route

    return route
