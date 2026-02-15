# ==========================================
# TEMPORARY CARPOOL ROUTE STORE (MVP)
# ------------------------------------------
# Stores carpool routes in memory.
# This is a temporary implementation for MVP.
# Replace with persistent DB in production.
# ==========================================

IN_MEMORY_CARPOOL_ROUTES = {}

# Formato esperado por route_id:
# {
#     "route_id": str,
#     "driver_id": str,
#     "capacity": int,
#     "stops": list,  # [{"name": str, "lat": float, "lng": float}]
#     "status": "active"
# }
