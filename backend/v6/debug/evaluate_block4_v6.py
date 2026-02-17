"""
Evaluación del nivel del Block 4 en V6.

Ejecuta solo el motor de paradas shuttle (run_shuttle_stop_opening) y reporta:
- Métricas: clusters, tamaños, excluidos, cobertura.
- Cumplimiento: separación mínima entre paradas, determinismo.
- Nivel: OK / WARN / FAIL por criterio y resumen.

Criterios de nivel:
- Cobertura: OK >= 85%, WARN >= 70%, FAIL < 70%.
- Separación mínima: todas las paradas a >= min_stop_sep_m (350 m por defecto).
- Determinismo: dos ejecuciones deben dar el mismo resultado.

Uso (desde raíz del repo):
  python -m backend.v6.debug.evaluate_block4_v6
  python -m backend.v6.debug.evaluate_block4_v6 --coverage   # preset cobertura Optimob
  python -m backend.v6.debug.evaluate_block4_v6 --map        # KPIs + mapa HTML (paradas, empleados, oficina)
  python -m backend.v6.debug.evaluate_block4_v6 --coverage --map
"""

import argparse
import csv
import math
from pathlib import Path

import numpy as np

from backend.v6.core.network_design_engine.shuttle_stop_engine import (
    MIN_STOP_SEP_M,
    run_shuttle_stop_opening,
    _lat_lon_to_meters,
)
from backend.v6.domain.constraints import StructuralConstraints
from backend.v6.domain.models import Employee

# Oficina por defecto (Madrid)
DEFAULT_OFFICE_LAT = 40.4168
DEFAULT_OFFICE_LNG = -3.7038
ASSIGN_RADIUS_M = 1000
MAX_CLUSTER = 50
MIN_SHUTTLE = 6

DEFAULT_CSV = Path(__file__).resolve().parent.parent / "data" / "v4_employees_frozen.csv"


def load_employees(csv_path: Path) -> list[Employee]:
    """Carga empleados desde CSV con columnas employee_id, home_lat, home_lng."""
    employees = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            employees.append(
                Employee(
                    employee_id=row["employee_id"].strip(),
                    home_lat=float(row["home_lat"]),
                    home_lng=float(row["home_lng"]),
                    willing_driver=False,
                )
            )
    return employees


def _cluster_centroids_meters(
    final_clusters: list[list[str]],
    employees: list[Employee],
    id_to_index: dict[str, int],
    X: np.ndarray,
) -> list[np.ndarray]:
    """Centroide en metros de cada cluster (mismo criterio que el motor)."""
    out = []
    for cluster_ids in final_clusters:
        indices = [id_to_index[eid] for eid in cluster_ids]
        out.append(np.mean(X[indices], axis=0))
    return out


def check_min_separation(
    final_clusters: list[list[str]],
    employees: list[Employee],
    office_lat: float,
    office_lng: float,
    min_sep_m: float,
) -> tuple[bool, float]:
    """
    Verifica que entre cada par de paradas (centroides) haya al menos min_sep_m.
    Returns (all_ok, min_pairwise_distance).
    """
    if len(final_clusters) < 2:
        return True, float("inf")
    id_to_index = {e.employee_id: i for i, e in enumerate(employees)}
    X = _lat_lon_to_meters(employees, office_lat, office_lng)
    centroids = _cluster_centroids_meters(final_clusters, employees, id_to_index, X)
    min_dist = float("inf")
    for i in range(len(centroids)):
        for j in range(i + 1, len(centroids)):
            d = float(np.linalg.norm(centroids[i] - centroids[j]))
            min_dist = min(min_dist, d)
    return min_dist >= min_sep_m, min_dist


def check_determinism(
    employees: list[Employee],
    office_lat: float,
    office_lng: float,
    constraints: StructuralConstraints,
) -> tuple[bool, str]:
    """Ejecuta dos veces y comprueba mismo resultado. Returns (ok, message)."""
    c1, cp1 = run_shuttle_stop_opening(employees, office_lat, office_lng, constraints)
    c2, cp2 = run_shuttle_stop_opening(employees, office_lat, office_lng, constraints)
    if len(c1) != len(c2):
        return False, f"Distinto número de clusters: {len(c1)} vs {len(c2)}"
    if cp1 != cp2:
        return False, f"Distinto carpool_set (tamaños {len(cp1)} vs {len(cp2)})"
    # Mismos clusters (contenido igual, orden puede variar en teoría; contenido por conjunto)
    set_c1 = [frozenset(cl) for cl in c1]
    set_c2 = [frozenset(cl) for cl in c2]
    if sorted(set_c1) != sorted(set_c2):
        return False, "Distinta asignación de clusters entre ejecuciones"
    return True, "Dos ejecuciones idénticas"


def run_evaluation(
    employees: list[Employee],
    office_lat: float = DEFAULT_OFFICE_LAT,
    office_lng: float = DEFAULT_OFFICE_LNG,
    min_sep_m: float = MIN_STOP_SEP_M,
    use_coverage_params: bool = False,
) -> dict:
    """Ejecuta Block 4 V6 y devuelve métricas. Si use_coverage_params, usa preset cobertura Optimob."""
    if use_coverage_params:
        constraints = StructuralConstraints(
            assign_radius_m=1200.0,
            max_cluster_size=MAX_CLUSTER,
            bus_capacity=50,
            min_shuttle_occupancy=0.7,
            detour_cap=2.2,
            backfill_max_delta_min=1.35,
            min_ok_far_m=3000.0,
            min_ok_far=6,
            pair_radius_m=450.0,
        )
    else:
        constraints = StructuralConstraints(
            assign_radius_m=float(ASSIGN_RADIUS_M),
            max_cluster_size=MAX_CLUSTER,
            bus_capacity=50,
            min_shuttle_occupancy=0.7,
            detour_cap=2.2,
            backfill_max_delta_min=1.35,
        )
    final_clusters, carpool_set = run_shuttle_stop_opening(
        employees, office_lat, office_lng, constraints
    )
    n = len(employees)
    assigned = n - len(carpool_set)
    coverage = (assigned / n * 100.0) if n else 0.0
    sizes = [len(c) for c in final_clusters]
    sep_ok, min_pairwise = check_min_separation(
        final_clusters, employees, office_lat, office_lng, min_sep_m
    )
    det_ok, det_msg = check_determinism(employees, office_lat, office_lng, constraints)

    return {
        "n_employees": n,
        "n_clusters": len(final_clusters),
        "n_excluded": len(carpool_set),
        "coverage_pct": coverage,
        "sizes": sizes,
        "mean_size": float(np.mean(sizes)) if sizes else 0.0,
        "std_size": float(np.std(sizes)) if sizes else 0.0,
        "min_sep_ok": sep_ok,
        "min_pairwise_m": min_pairwise,
        "determinism_ok": det_ok,
        "determinism_msg": det_msg,
        "final_clusters": final_clusters,
        "carpool_set": carpool_set,
    }


def _cluster_centroid_latlon(employee_ids: list[str], employees_by_id: dict) -> tuple[float, float]:
    lat = sum(employees_by_id[eid].home_lat for eid in employee_ids) / len(employee_ids)
    lng = sum(employees_by_id[eid].home_lng for eid in employee_ids) / len(employee_ids)
    return (lat, lng)


def _cluster_radius_m(latlon_list: list[tuple[float, float]]) -> float:
    if len(latlon_list) < 2:
        return 50.0
    latlon_arr = np.array(latlon_list)
    lat_rad = np.radians(latlon_arr[:, 0])
    lng_rad = np.radians(latlon_arr[:, 1])
    dlat = lat_rad[:, None] - lat_rad[None, :]
    dlng = lng_rad[:, None] - lng_rad[None, :]
    a = np.sin(dlat / 2) ** 2 + np.cos(lat_rad[:, None]) * np.cos(lat_rad[None, :]) * np.sin(dlng / 2) ** 2
    c = 2 * np.arcsin(np.minimum(1.0, np.sqrt(a)))
    dist_m = 6371000 * c
    return float(np.max(dist_m)) + 20.0


def _build_map(
    employees: list[Employee],
    final_clusters: list[list[str]],
    carpool_set: set[str],
    office_lat: float,
    office_lng: float,
    out_path: Path,
    open_browser: bool = True,
) -> None:
    """Genera mapa Folium: empleados, paradas V6, oficina. Guarda HTML y opcionalmente abre en navegador."""
    import webbrowser
    import folium
    employees_by_id = {e.employee_id: e for e in employees}
    m = folium.Map(location=[office_lat, office_lng], zoom_start=11)
    for e in employees:
        color = "red" if e.employee_id in carpool_set else "gray"
        folium.CircleMarker(
            location=(e.home_lat, e.home_lng),
            radius=4,
            color=color,
            fill=True,
            fill_opacity=0.7,
            weight=1,
            popup=f"{e.employee_id} (carpool)" if e.employee_id in carpool_set else e.employee_id,
        ).add_to(m)
    for i, c in enumerate(final_clusters):
        lat, lng = _cluster_centroid_latlon(c, employees_by_id)
        pts = [(employees_by_id[eid].home_lat, employees_by_id[eid].home_lng) for eid in c]
        r_m = _cluster_radius_m(pts)
        folium.CircleMarker(
            location=(lat, lng),
            radius=12,
            color="blue",
            fill=True,
            fill_opacity=0.8,
            weight=2,
            popup=f"Parada {i+1} · n={len(c)}",
        ).add_to(m)
        folium.Circle(
            location=(lat, lng),
            radius=r_m,
            color="blue",
            fill=False,
            weight=2,
            dash_array="5,5",
        ).add_to(m)
    folium.Marker(
        location=[office_lat, office_lng],
        popup="Oficina",
        icon=folium.Icon(color="green", icon="building", prefix="fa"),
    ).add_to(m)
    m.save(str(out_path))
    if open_browser:
        webbrowser.open(f"file://{out_path.resolve()}")
    print(f"\nMapa guardado: {out_path}")


def level_for_coverage(coverage_pct: float) -> str:
    if coverage_pct >= 85:
        return "OK"
    if coverage_pct >= 70:
        return "WARN"
    return "FAIL"


def main():
    parser = argparse.ArgumentParser(description="Evaluar nivel Block 4 V6")
    parser.add_argument(
        "--csv",
        type=Path,
        default=DEFAULT_CSV,
        help="CSV con employee_id, home_lat, home_lng",
    )
    parser.add_argument(
        "--office-lat", type=float, default=DEFAULT_OFFICE_LAT, help="Latitud oficina"
    )
    parser.add_argument(
        "--office-lng", type=float, default=DEFAULT_OFFICE_LNG, help="Longitud oficina"
    )
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="Preset cobertura: assign_radius=1200m, pair_radius=450m, min_ok adaptativo (6 en zona lejana)",
    )
    parser.add_argument(
        "--map",
        action="store_true",
        help="Genera mapa HTML (paradas, empleados, oficina) y abre en el navegador",
    )
    args = parser.parse_args()

    if not args.csv.exists():
        print(f"ERROR: No existe el archivo {args.csv}")
        return 1

    employees = load_employees(args.csv)
    print(f"Empleados cargados: {len(employees)} desde {args.csv}")
    if args.coverage:
        print("Preset: cobertura Optimob (radio 1200 m, reabsorción 450 m, min_ok adaptativo)")

    r = run_evaluation(
        employees,
        office_lat=args.office_lat,
        office_lng=args.office_lng,
        use_coverage_params=args.coverage,
    )

    # ---- KPIs (resumen) ----
    print("\n--- KPIs Block 4 V6 ---")
    print(f"  Cobertura: {r['coverage_pct']:.1f}%  |  Paradas: {r['n_clusters']}  |  Asignados shuttle: {r['n_employees'] - r['n_excluded']}  |  Excluidos: {r['n_excluded']}  |  Tamaño medio: {r['mean_size']:.1f}")

    # ---- Métricas ----
    print("\n--- Métricas Block 4 V6 ---")
    print(f"  Clusters:        {r['n_clusters']}")
    print(f"  Asignados:       {r['n_employees'] - r['n_excluded']}")
    print(f"  Excluidos:       {r['n_excluded']}")
    print(f"  Cobertura:       {r['coverage_pct']:.1f}%")
    print(f"  Tamaño medio:    {r['mean_size']:.1f} (std {r['std_size']:.1f})")

    # ---- Cumplimiento ----
    print("\n--- Cumplimiento ---")
    sep_level = "OK" if r["min_sep_ok"] else "FAIL"
    print(f"  Separación mínima (>{MIN_STOP_SEP_M}m): {sep_level} (min par = {r['min_pairwise_m']:.0f}m)")
    print(f"  Determinismo: {'OK' if r['determinism_ok'] else 'FAIL'} — {r['determinism_msg']}")

    # ---- Nivel ----
    cov_level = level_for_coverage(r["coverage_pct"])
    print("\n--- Nivel Block 4 V6 ---")
    print(f"  Cobertura:       {cov_level} ({r['coverage_pct']:.1f}%)")
    print(f"  Separación:      {'OK' if r['min_sep_ok'] else 'FAIL'}")
    print(f"  Determinismo:    {'OK' if r['determinism_ok'] else 'FAIL'}")
    if cov_level == "OK" and r["min_sep_ok"] and r["determinism_ok"]:
        print("  Resumen:         NIVEL OK (Block 4 V6 listo para uso)")
    elif cov_level == "FAIL" or not r["min_sep_ok"] or not r["determinism_ok"]:
        print("  Resumen:         NIVEL FAIL (revisar criterios)")
    else:
        print("  Resumen:         NIVEL WARN (aceptable con revisión)")

    # ---- Mapa ----
    if args.map:
        out_path = Path(__file__).resolve().parent / "block4_v6_map.html"
        _build_map(
            employees,
            r["final_clusters"],
            r["carpool_set"],
            args.office_lat,
            args.office_lng,
            out_path,
            open_browser=True,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
