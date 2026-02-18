"""
Obtención de candidatos shuttle para el plan.

Primera línea: Block 4 (run_shuttle_stop_opening) → paradas viables y carpool.
Sombra: generate_shuttle_candidates (option.py) — solo para métricas de comparación.
"""

from backend.v6.core.network_design_engine.shuttle_stop_engine import run_shuttle_stop_opening
from backend.v6.domain.constraints import StructuralConstraints
from backend.v6.domain.models import Employee, ShuttleOption


def block4_clusters_to_shuttle_options(
    final_clusters: list[list[str]],
    employees_by_id: dict[str, Employee],
) -> list[ShuttleOption]:
    """Convierte la salida de Block 4 (listas de employee_id) en list[ShuttleOption]."""
    options: list[ShuttleOption] = []
    for i, cluster_ids in enumerate(final_clusters):
        if not cluster_ids:
            continue
        lats = [employees_by_id[eid].home_lat for eid in cluster_ids]
        lngs = [employees_by_id[eid].home_lng for eid in cluster_ids]
        centroid_lat = sum(lats) / len(lats)
        centroid_lng = sum(lngs) / len(lngs)
        options.append(
            ShuttleOption(
                option_id=f"shuttle_{i}",
                employee_ids=cluster_ids,
                centroid_lat=centroid_lat,
                centroid_lng=centroid_lng,
                estimated_size=len(cluster_ids),
            )
        )
    return options


def get_shuttle_candidates_block4(
    employees: list[Employee],
    office_lat: float,
    office_lng: float,
    constraints: StructuralConstraints,
) -> tuple[list[ShuttleOption], set[str]]:
    """
    Primera línea: Block 4. Devuelve (shuttle_options, carpool_employee_ids).
    shuttle_options son las paradas viables; carpool_employee_ids es el residual (carpool).
    """
    final_clusters, carpool_set = run_shuttle_stop_opening(
        employees, office_lat, office_lng, constraints
    )
    employees_by_id = {e.employee_id: e for e in employees}
    options = block4_clusters_to_shuttle_options(final_clusters, employees_by_id)
    return options, carpool_set
