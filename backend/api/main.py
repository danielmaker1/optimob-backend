"""
FastAPI mínima para OptiMob backend v5

Capa API HTTP sobre la lógica existente.
No modifica ni refactoriza el backend v5.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional

# Importar funciones del backend v5
from backend.v5.today import get_today
from backend.v5.validation import validate_trip


# Crear aplicación FastAPI
app = FastAPI(
    title="OptiMob API",
    description="API HTTP mínima sobre backend v5",
    version="1.0.0"
)


# Modelos Pydantic para validación
class ValidateTripRequest(BaseModel):
    user_id: str
    trip_type: str
    validated_by: str


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


# Bloque para ejecutar con uvicorn
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
