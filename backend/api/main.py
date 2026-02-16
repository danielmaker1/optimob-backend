"""
FastAPI mínima para OptiMob backend v5

Capa API HTTP sobre la lógica existente.
No modifica ni refactoriza el backend v5.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

# Importar funciones del backend v5
from backend.v5.today import get_today
from backend.v5.validation import validate_trip
from backend.v5.carpool import (
    create_carpool_route,
    assign_mock_passengers,
    update_carpool_status,
    passenger_respond,
    confirm_pickup,
)


# Crear aplicación FastAPI
app = FastAPI(
    title="OptiMob API",
    description="API HTTP mínima sobre backend v5",
    version="1.0.0"
)

origins = [
    "http://localhost:5173",
    "https://symmetrical-carnival-xrr9r5jg9w5fp9xv-5173.app.github.dev"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://symmetrical-carnival-xrr9r5jg9w5fp9xv-5173.app.github.dev"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Modelos Pydantic para validación
class ValidateTripRequest(BaseModel):
    user_id: str
    trip_type: str
    validated_by: str


class CreateCarpoolRequest(BaseModel):
    driver_id: str
    capacity: int
    stops: list  # [{"name": str, "lat": float, "lng": float}]
    date: str    # "YYYY-MM-DD"
    time: str    # "HH:MM"


class AssignCarpoolPassengersRequest(BaseModel):
    driver_id: str
    passengers: list  # list[str] — user_id de pasajeros


class UpdateCarpoolStatusRequest(BaseModel):
    driver_id: str
    status: str  # "active" | "in_progress" | "completed"


class PassengerRespondRequest(BaseModel):
    driver_id: str
    passenger_id: str
    response: str  # "accepted" | "rejected"


class PassengerPickupRequest(BaseModel):
    driver_id: str
    passenger_id: str


# Endpoints
@app.get("/")
def root():
    """Endpoint raíz"""
    return {"message": "OptiMob API v5", "status": "ok"}


@app.get("/today")
def endpoint_get_today(user_id: str, role: str = "passenger"):
    """
    GET /today
    
    Query params:
        - user_id (str): ID del usuario
        - role (str): Rol del usuario (passenger, carpool_driver)
    
    Returns:
        JSON con el estado operativo del día
    """
    try:
        result = get_today(user_id=user_id, role=role)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/validate")
def endpoint_validate_trip(request: ValidateTripRequest):
    """
    POST /validate
    
    Body:
        - user_id (str): ID del usuario
        - trip_type (str): Tipo de viaje (ida, vuelta)
        - validated_by (str): Quién valida (passenger, driver, shuttle_driver)
    
    Returns:
        JSON con la confirmación de validación
    """
    try:
        result = validate_trip(
            user_id=request.user_id,
            trip_type=request.trip_type,
            validated_by=request.validated_by
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/carpool/create")
def endpoint_create_carpool(request: CreateCarpoolRequest):
    """
    POST /carpool/create

    Body:
        - driver_id (str): ID del conductor
        - capacity (int): Capacidad del vehículo
        - stops (list): Paradas [{"name": str, "lat": float, "lng": float}]
        - date (str): "YYYY-MM-DD"
        - time (str): "HH:MM"

    Returns:
        JSON con la ruta de carpool creada
    """
    try:
        result = create_carpool_route(
            driver_id=request.driver_id,
            capacity=request.capacity,
            stops=request.stops,
            date=request.date,
            time=request.time,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/carpool/assign")
def endpoint_carpool_assign(request: AssignCarpoolPassengersRequest):
    """
    POST /carpool/assign

    Body:
        - driver_id (str): ID del conductor
        - passengers (list[str]): user_id de pasajeros a asignar

    Returns:
        JSON con la ruta actualizada (respetando capacity)
    """
    try:
        result = assign_mock_passengers(
            driver_id=request.driver_id,
            passengers=request.passengers,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/carpool/status")
def endpoint_carpool_status(request: UpdateCarpoolStatusRequest):
    """
    POST /carpool/status

    Body:
        - driver_id (str): ID del conductor
        - status (str): Estado operativo. Permitidos: active, in_progress, completed

    Returns:
        JSON con la ruta actualizada. /today refleja este estado para carpool_driver.
    """
    try:
        result = update_carpool_status(
            driver_id=request.driver_id,
            new_status=request.status,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/carpool/passenger/respond")
def endpoint_carpool_passenger_respond(request: PassengerRespondRequest):
    """
    POST /carpool/passenger/respond — Pasajero confirma o rechaza plaza.

    Body:
        - driver_id (str): ID del conductor
        - passenger_id (str): ID del pasajero
        - response (str): "accepted" | "rejected"

    Returns:
        Ruta actualizada; estado de ruta recalculado automáticamente.
    """
    try:
        result = passenger_respond(
            driver_id=request.driver_id,
            passenger_id=request.passenger_id,
            response=request.response,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/carpool/passenger/pickup")
def endpoint_carpool_passenger_pickup(request: PassengerPickupRequest):
    """
    POST /carpool/passenger/pickup — Conductor confirma recogida.

    Body:
        - driver_id (str): ID del conductor
        - passenger_id (str): ID del pasajero

    Ruta debe estar in_progress; pasajero debe estar accepted.
    Returns:
        Ruta actualizada; estado recalculado (completed si todos los accepted recogidos).
    """
    try:
        result = confirm_pickup(
            driver_id=request.driver_id,
            passenger_id=request.passenger_id,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Bloque para ejecutar con uvicorn
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
