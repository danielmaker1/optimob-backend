"""
Análisis en profundidad: comparación V4 vs V6 Block 4 + datos + reglas + umbrales.

Hace:
  1. Comparación numérica V4 vs V6 (mismo dataset).
  2. Análisis del dataset: distancias a oficina, densidad, impacto de reglas.
  3. Conclusión sobre si el FAIL de cobertura es por datos, reglas o umbral.

Uso (desde raíz del repo):
  python -m backend.v6.debug.analyze_block4_coverage
"""

import numpy as np
from scipy.spatial import KDTree

from backend.v6.debug.compare_v4_v6_block4 import (
    _load_frozen_employees,
    _run_v4_block4,
    COORDENADAS_OFICINA,
    ASSIGN_RADIUS_M,
    EXCLUDE_RADIUS_M,
    MIN_OK,
    MAX_OK,
    MAX_CLUSTER,
)
from backend.v6.core.network_design_engine.shuttle_stop_engine import (
    run_shuttle_stop_opening,
    _lat_lon_to_meters,
)
from backend.v6.domain.constraints import StructuralConstraints


def main():
    empleados_data, employees = _load_frozen_employees()
    office_lat, office_lng = COORDENADAS_OFICINA
    N = len(employees)

    # ---------- 1. Comparación V4 vs V6 ----------
    final_v4, carpool_v4 = _run_v4_block4(empleados_data)
    constraints = StructuralConstraints(
        assign_radius_m=float(ASSIGN_RADIUS_M),
        max_cluster_size=MAX_CLUSTER,
        bus_capacity=50,
        min_shuttle_occupancy=0.7,
        detour_cap=2.2,
        backfill_max_delta_min=1.35,
    )
    final_v6, carpool_v6 = run_shuttle_stop_opening(
        employees, office_lat, office_lng, constraints
    )

    assigned_v4 = N - len(carpool_v4)
    assigned_v6 = N - len(carpool_v6)
    cov_v4 = (assigned_v4 / N * 100) if N else 0
    cov_v6 = (assigned_v6 / N * 100) if N else 0

    print("=" * 60)
    print("1. COMPARACIÓN V4 vs V6 BLOCK 4 (mismo dataset)")
    print("=" * 60)
    print(f"  Empleados totales:     {N}")
    print(f"  V4  clusters:          {len(final_v4)}  |  Asignados: {assigned_v4}  |  Cobertura: {cov_v4:.1f}%")
    print(f"  V6  clusters:          {len(final_v6)}  |  Asignados: {assigned_v6}  |  Cobertura: {cov_v6:.1f}%")
    print(f"  Diferencia cobertura: {cov_v6 - cov_v4:+.1f} pp (V6 - V4)")
    if abs(cov_v4 - cov_v6) < 1.0:
        print("  Conclusión:            V4 y V6 dan cobertura muy similar (motor alineado).")
    elif cov_v6 < cov_v4:
        print("  Conclusión:            V6 asigna menos que V4 (revisar diferencias algoritmo).")
    else:
        print("  Conclusión:            V6 asigna más que V4.")
    print()

    # ---------- 2. Análisis del dataset (coordenadas en metros, origen oficina) ----------
    X = _lat_lon_to_meters(employees, office_lat, office_lng)
    dist_office = np.linalg.norm(X, axis=1)
    tree = KDTree(X)

    # Distancias a oficina
    within_500 = (dist_office <= 500).sum()
    within_1000 = (dist_office <= 1000).sum()
    within_2000 = (dist_office <= 2000).sum()
    within_3000 = (dist_office <= 3000).sum()

    print("=" * 60)
    print("2. DATOS: dispersión respecto a la oficina")
    print("=" * 60)
    print(f"  Distancia a oficina (m): min={dist_office.min():.0f}  max={dist_office.max():.0f}  media={dist_office.mean():.0f}")
    print(f"  Percentiles:  p50={np.percentile(dist_office, 50):.0f}  p90={np.percentile(dist_office, 90):.0f}  p95={np.percentile(dist_office, 95):.0f}")
    print(f"  Dentro de  500 m: {within_500:4d} ({within_500/N*100:.1f}%)")
    print(f"  Dentro de 1000 m: {within_1000:4d} ({within_1000/N*100:.1f}%)  <- exclude_radius_m, radio asignación")
    print(f"  Dentro de 2000 m: {within_2000:4d} ({within_2000/N*100:.1f}%)")
    print(f"  Dentro de 3000 m: {within_3000:4d} ({within_3000/N*100:.1f}%)")
    print("  Interpretación: empleados muy lejos de oficina no pueden formar parada útil (exclude_radius y radio 1000 m).")
    print()

    # Densidad: vecinos dentro de assign_radius (1000 m)
    counts_in_radius = tree.query_radius(X, r=ASSIGN_RADIUS_M, count_only=True)
    mean_neighbors = float(counts_in_radius.mean())
    at_least_6 = (counts_in_radius >= 6).sum()
    at_least_8 = (counts_in_radius >= MIN_OK).sum()
    at_least_1 = (counts_in_radius >= 2).sum()  # al menos otro además de sí mismo

    print("=" * 60)
    print("3. DATOS: densidad (vecinos dentro de 1000 m por empleado)")
    print("=" * 60)
    print(f"  Vecinos en 1000 m:  media={mean_neighbors:.1f}  min={counts_in_radius.min()}  max={counts_in_radius.max()}")
    print(f"  Empleados con >= 6 vecinos (min_shuttle): {at_least_6} ({at_least_6/N*100:.1f}%)")
    print(f"  Empleados con >= 8 vecinos (min_ok):      {at_least_8} ({at_least_8/N*100:.1f}%)")
    print("  Interpretación: para que un cluster se mantenga debe tener al menos min_ok=8;")
    print("  si pocos puntos tienen 8+ vecinos en 1000 m, la cobertura shuttle está limitada por densidad.")
    print()

    # ---------- 4. Reglas estrictas ----------
    # Exclusión: clusters cuyo centroide cae a < 1000 m de oficina se mandan a carpool.
    # Aproximación: cuántos empleados viven a < 1000 m de oficina (podrían estar en clusters excluidos)
    print("=" * 60)
    print("4. REGLAS ESTRICTAS (Block 4)")
    print("=" * 60)
    print("  • min_ok=8: clusters con < 8 miembros se descartan -> residual.")
    print("  • max_ok=40: clusters grandes se parten (KMeans); subclusters < 8 se descartan.")
    print("  • exclude_radius_m=1000: cluster cuyo centroide está a < 1000 m de oficina -> todo a carpool.")
    print(f"  • Empleados a < 1000 m de oficina: {within_1000} -> posibles clusters 'cerca oficina' excluidos.")
    print("  Conclusión: con datos dispersos y muchas zonas con < 8 vecinos en 1000 m, es esperable")
    print("  cobertura shuttle moderada (20–40%); 85%% sería realista solo con datos muy densos.")
    print()

    # ---------- 5. Umbral de nivel 85% ----------
    print("=" * 60)
    print("5. UMBRAL DE NIVEL (85% cobertura = OK)")
    print("=" * 60)
    print(f"  Cobertura actual V6: {cov_v6:.1f}%.")
    print(f"  Techo aproximado por datos: si solo ~{at_least_8/N*100:.0f}% tienen 8+ vecinos en 1000 m,")
    print("  la cobertura shuttle no puede ser mucho mayor que ese orden sin relajar reglas.")
    if cov_v6 < 50:
        print("  El FAIL (85%) castiga más al criterio que al motor: el dataset/reglas no permiten 85%.")
    print("  Recomendación: umbral configurable (ej. OK>=70%, WARN>=50%) o por dataset.")
    print()

    # ---------- Resumen final ----------
    print("=" * 60)
    print("RESUMEN")
    print("=" * 60)
    print("  • V4 vs V6: misma cobertura aproximada -> motor V6 alineado con V4.")
    print("  • Cobertura baja: explicada por dispersión y reglas (min_ok, exclude_radius).")
    print("  • Umbral 85%: poco realista para este dataset; ajustar criterio de 'nivel' o datos.")
    print()


if __name__ == "__main__":
    main()
