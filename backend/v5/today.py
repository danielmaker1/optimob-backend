"""
V5 – Capa operativa mínima
Este módulo responde a una única pregunta:
¿Qué pasa HOY para un usuario?
"""

from datetime import date


def get_today(user_id: str, day: date | None = None) -> dict:
    """
    Devuelve el estado operativo del día para un usuario.
    Versión hardcodeada (MVP inicial).
    """

    return {
        "date": (day or date.today()).isoformat(),
        "user_id": user_id,
        "role": "passenger",
        "status": "pending",
        "trips": [
            {
                "type": "ida",
                "status": "pending",
                "mode": "shuttle",
                "time": "08:15",
                "from": {
                    "name": "Parada Plaza Castilla",
                    "lat": 40.4669,
                    "lng": -3.6883
                },
                "to": {
                    "name": "Oficina",
                    "lat": 40.4379,
                    "lng": -3.6796
                },
                "route": None
            },
            {
                "type": "vuelta",
                "status": "pending",
                "mode": "shuttle",
                "time": "18:00",
                "from": {
                    "name": "Oficina",
                    "lat": 40.4379,
                    "lng": -3.6796
                },
                "to": {
                    "name": "Parada Plaza Castilla",
                    "lat": 40.4669,
                    "lng": -3.6883
                },
                "route": None
            }
        ]
    }


if __name__ == "__main__":
    # Prueba local mínima
    result = get_today(user_id="demo_user")
    print(result)