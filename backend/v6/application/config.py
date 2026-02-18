"""
Configuración por defecto para el caso de uso plan_population (oficina y constraints).
Un solo lugar para evitar duplicar valores entre API, evaluadores y motor.
"""

from backend.v6.domain.constraints import StructuralConstraints

# Oficina por defecto (Madrid)
DEFAULT_OFFICE_LAT = 40.4168
DEFAULT_OFFICE_LNG = -3.7038

# Preset cobertura Optimob (Block 4 en primera línea)
DEFAULT_STRUCTURAL_CONSTRAINTS = StructuralConstraints(
    assign_radius_m=1200.0,
    max_cluster_size=50,
    bus_capacity=50,
    min_shuttle_occupancy=0.7,
    detour_cap=2.2,
    backfill_max_delta_min=1.35,
    min_ok_far_m=3000.0,
    min_ok_far=6,
    pair_radius_m=450.0,
    assign_by_stop_radius_after=True,
)
