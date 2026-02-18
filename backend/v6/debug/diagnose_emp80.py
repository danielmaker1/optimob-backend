"""
Diagnóstico minucioso: Emp_80 en carpool pero dentro de círculos de paradas 1, 9 y 12.
Comprueba distancias (m) al centroide de cada parada y tamaño de cluster.
Si distancia <= assign_radius y cluster < cap → debería estar asignado (bug).
"""

from pathlib import Path

import numpy as np

from backend.v6.core.network_design_engine.shuttle_stop_engine import (
    run_shuttle_stop_opening,
    _lat_lon_to_meters,
)
from backend.v6.domain.constraints import StructuralConstraints
from backend.v6.domain.models import Employee

from backend.v6.debug.evaluate_block4_v6 import (
    load_employees,
    _cluster_centroids_meters,
    DEFAULT_CSV,
    DEFAULT_OFFICE_LAT,
    DEFAULT_OFFICE_LNG,
    MAX_CLUSTER,
)

ASSIGN_RADIUS_COVERAGE = 1200.0
CAP = MAX_CLUSTER  # 50


def main():
    employees = load_employees(DEFAULT_CSV)
    id_to_index = {e.employee_id: i for i, e in enumerate(employees)}
    if "Emp_80" not in id_to_index:
        print("ERROR: Emp_80 no encontrado en el dataset")
        return 1

    constraints = StructuralConstraints(
        assign_radius_m=ASSIGN_RADIUS_COVERAGE,
        max_cluster_size=CAP,
        bus_capacity=50,
        min_shuttle_occupancy=0.7,
        detour_cap=2.2,
        backfill_max_delta_min=1.35,
        min_ok_far_m=3000.0,
        min_ok_far=6,
        pair_radius_m=450.0,
        assign_by_stop_radius_after=True,
    )
    final_clusters, carpool_set = run_shuttle_stop_opening(
        employees, DEFAULT_OFFICE_LAT, DEFAULT_OFFICE_LNG, constraints
    )

    X = _lat_lon_to_meters(employees, DEFAULT_OFFICE_LAT, DEFAULT_OFFICE_LNG)
    centroids = _cluster_centroids_meters(final_clusters, employees, id_to_index, X)

    emp80_idx = id_to_index["Emp_80"]
    emp80_xy = X[emp80_idx]
    in_carpool = "Emp_80" in carpool_set

    print("=" * 60)
    print("DIAGNÓSTICO Emp_80")
    print("=" * 60)
    print(f"  Emp_80 en carpool_set (rojo): {in_carpool}")
    print(f"  assign_radius (preset cobertura): {ASSIGN_RADIUS_COVERAGE} m")
    print(f"  cap (max_cluster_size): {CAP}")
    print()

    # Paradas 1, 9, 12 en notación usuario = índices 0, 8, 11
    for parada_num, k in [(1, 0), (9, 8), (12, 11)]:
        if k >= len(final_clusters):
            print(f"  Parada {parada_num}: no existe (solo hay {len(final_clusters)} paradas)")
            continue
        d_m = float(np.linalg.norm(emp80_xy - centroids[k]))
        size = len(final_clusters[k])
        dentro_radio = d_m <= ASSIGN_RADIUS_COVERAGE
        tiene_hueco = size < CAP
        deberia_asignado = dentro_radio and tiene_hueco
        print(f"  Parada {parada_num} (índice {k}):")
        print(f"    Distancia Emp_80 → centroide: {d_m:.1f} m")
        print(f"    Tamaño del cluster: {size} (cap {CAP})")
        print(f"    ¿Dentro del radio? {dentro_radio}")
        print(f"    ¿Cluster con hueco (< {CAP})? {tiene_hueco}")
        print(f"    ¿Debería estar asignado aquí? {deberia_asignado}")
        print()

    # ¿Alguna parada (cualquiera) debería haberlo cogido?
    candidatas = []
    for k in range(len(final_clusters)):
        d_m = float(np.linalg.norm(emp80_xy - centroids[k]))
        size = len(final_clusters[k])
        if d_m <= ASSIGN_RADIUS_COVERAGE and size < CAP:
            candidatas.append((k + 1, d_m, size))
    candidatas.sort(key=lambda x: x[1])

    print("  Todas las paradas dentro de 1200 m con hueco (< 50):")
    if not candidatas:
        print("    Ninguna.")
    else:
        for parada_num, d_m, size in candidatas:
            print(f"    Parada {parada_num}: {d_m:.1f} m, tamaño {size}")

    print()
    print("=" * 60)
    if in_carpool and candidatas:
        print("CONCLUSIÓN: BUG. Emp_80 está en carpool pero hay al menos una parada")
        print("  dentro del radio con hueco → debería haber sido asignado en el segundo paso.")
    elif in_carpool and not candidatas:
        print("CONCLUSIÓN: No bug. Emp_80 en carpool; todas las paradas a ≤1200 m están")
        print("  al cap (50) → se llenaron antes en el orden del segundo paso.")
    else:
        print("CONCLUSIÓN: Emp_80 no está en carpool (ya asignado).")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
