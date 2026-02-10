"""
V5 – Validación de viajes
Permite confirmar (validar) un viaje del día.
"""

from datetime import datetime
from typing import Dict


def validate_trip(
    user_id: str,
    trip_type: str,
    validated_by: str = "passenger"
) -> Dict:
    """
    Marca un viaje como validado.

    trip_type:
        - "ida"
        - "vuelta"

    validated_by:
        - "passenger"
        - "driver"
        - "shuttle_driver"
    """

    if trip_type not in ["ida", "vuelta"]:
        raise ValueError("trip_type must be 'ida' or 'vuelta'")

    if validated_by not in ["passenger", "driver", "shuttle_driver"]:
        raise ValueError("invalid validated_by")

    return {
        "user_id": user_id,
        "trip_type": trip_type,
        "validated_by": validated_by,
        "validated_at": datetime.utcnow().isoformat() + "Z",
        "status": "confirmed"
    }


if __name__ == "__main__":
    print(
        validate_trip(
            user_id="demo_user",
            trip_type="ida",
            validated_by="passenger"
        )
    )