"""
V5 – Capa operativa mínima
Módulo principal para responder:
¿Qué pasa HOY para un usuario?
"""

from datetime import date
from typing import Optional

# Temporary in-memory store; replace with DB in production.
from backend.v5.state_store import IN_MEMORY_VALIDATIONS
from backend.v5.carpool_store import IN_MEMORY_CARPOOL_ROUTES


def get_today(
    user_id: str,
    day: Optional[date] = None,
    role: str = "passenger"
) -> dict:
    """
    Devuelve el estado operativo del día para un usuario.

    role:
        - "passenger"
        - "carpool_driver"
    """

    today = (day or date.today()).isoformat()

    office = {
        "name": "Oficina",
        "lat": 40.4379,
        "lng": -3.6796
    }

    pickup = {
        "name": "Parada Plaza Castilla",
        "lat": 40.4669,
        "lng": -3.6883
    }

    if role == "carpool_driver":
        trips = [
            {
                "type": "ida",
                "status": "pending",
                "mode": "carpool",
                "time": "08:15",
                "from": pickup,
                "to": office,
                "vehicle": {
                    "type": "car",
                    "capacity": 4,
                    "occupied": 2
                },
                "route": None
            }
        ]
    else:
        trips = [
            {
                "type": "ida",
                "status": "pending",
                "mode": "shuttle",
                "time": "08:15",
                "from": pickup,
                "to": office,
                "route": None
            },
            {
                "type": "vuelta",
                "status": "pending",
                "mode": "shuttle",
                "time": "18:00",
                "from": office,
                "to": pickup,
                "route": None
            }
        ]

    # Temporary: apply in-memory validations so status reflects validated trips.
    for trip in trips:
        key = (user_id, trip["type"])
        if key in IN_MEMORY_VALIDATIONS:
            trip["status"] = IN_MEMORY_VALIDATIONS[key]

    result = {
        "date": today,
        "user_id": user_id,
        "role": role,
        "status": "pending",
        "trips": trips
    }

    # ==========================================
    # STATUS AGGREGATION LOGIC
    # ------------------------------------------
    # The overall day status reflects the state
    # of individual trips. If all trips are
    # confirmed, the day is considered confirmed.
    # ==========================================
    if all(trip["status"] == "confirmed" for trip in trips):
        result["status"] = "confirmed"
    else:
        result["status"] = "pending"

    # ==========================================
    # DYNAMIC ROLE DETECTION (MVP)
    # ------------------------------------------
    # If the user has created a carpool route,
    # they operate as carpool_driver for the day.
    # This is temporary logic for MVP.
    # ==========================================
    has_carpool_route = any(
        route.get("driver_id") == user_id
        for route in IN_MEMORY_CARPOOL_ROUTES.values()
    )
    if has_carpool_route:
        result["role"] = "carpool_driver"

    # ==========================================
    # CARPOOL ROUTE INTEGRATION (MVP)
    # ------------------------------------------
    # If user operates as carpool_driver,
    # attach their carpool route to today's response.
    # Progressive integration without breaking trips.
    # ==========================================
    if result["role"] == "carpool_driver":
        carpool_route = next(
            (route for route in IN_MEMORY_CARPOOL_ROUTES.values()
             if route.get("driver_id") == user_id),
            None
        )
        if carpool_route is not None:
            result["carpool_route"] = carpool_route

    return result


if __name__ == "__main__":
    print("Passenger day:")
    print(get_today(user_id="demo_user", role="passenger"))
    print()
    print("Carpool driver day:")
    print(get_today(user_id="demo_user", role="carpool_driver"))