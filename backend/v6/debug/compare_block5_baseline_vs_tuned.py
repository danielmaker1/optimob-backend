"""
Comparación Block 5 V6: baseline (V4 frozen) vs parámetros afinados (bajo riesgo).

No modifica el motor Block 5: solo llama a run_shuttle_vrp dos veces con
distintos constraints y argumentos (MIN_EMP_SHUTTLE, BACKFILL_MAX_MIN_PER_PAX, etc.)
y compara KPIs sobre el mismo dataset y misma matriz D.

Uso (desde raíz del repo):
  python -m backend.v6.debug.compare_block5_baseline_vs_tuned
  python -m backend.v6.debug.compare_block5_baseline_vs_tuned --csv path/to/employees.csv

Salida: tabla lado a lado + resumen; opcional --out para guardar CSV/markdown.
"""

import argparse
import csv
import math
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

from backend.v6.application.config import (
    DEFAULT_OFFICE_LAT,
    DEFAULT_OFFICE_LNG,
    DEFAULT_STRUCTURAL_CONSTRAINTS,
)
from backend.v6.application.shuttle_candidates import block4_clusters_to_shuttle_options
from backend.v6.core.network_design_engine.shuttle_stop_engine import (
    run_shuttle_stop_opening,
)
from backend.v6.core.network_design_engine.shuttle_vrp_engine import (
    VRPResult,
    run_shuttle_vrp,
)
from backend.v6.domain.constraints import StructuralConstraints
from backend.v6.domain.models import Employee, ShuttleOption


DATA_CSV = (
    Path(__file__).resolve().parent.parent / "data" / "v4_employees_frozen.csv"
)

# ---------- Preset "tuned" (bajo riesgo): mismos algoritmos, otros parámetros ----------
# - MIN_EMP_SHUTTLE más bajo (12) → permitir rutas algo más pequeñas antes de absorber
# - BACKFILL_MAX_MIN_PER_PAX algo mayor (1.5) → aceptar un poco más de penalización por pax al rellenar
# Efecto esperado: posiblemente más paradas servidas y más empleados en shuttle; quizá más rutas o rutas algo más largas.
TUNED_MIN_EMP_SHUTTLE = 12
TUNED_BACKFILL_MAX_DELTA_MIN = 1.5

# Constraint "tuned": igual que default pero backfill_max_delta_min más permisivo
TUNED_STRUCTURAL_CONSTRAINTS = StructuralConstraints(
    assign_radius_m=DEFAULT_STRUCTURAL_CONSTRAINTS.assign_radius_m,
    max_cluster_size=DEFAULT_STRUCTURAL_CONSTRAINTS.max_cluster_size,
    bus_capacity=DEFAULT_STRUCTURAL_CONSTRAINTS.bus_capacity,
    min_shuttle_occupancy=DEFAULT_STRUCTURAL_CONSTRAINTS.min_shuttle_occupancy,
    detour_cap=DEFAULT_STRUCTURAL_CONSTRAINTS.detour_cap,
    backfill_max_delta_min=TUNED_BACKFILL_MAX_DELTA_MIN,
    min_ok_far_m=DEFAULT_STRUCTURAL_CONSTRAINTS.min_ok_far_m,
    min_ok_far=DEFAULT_STRUCTURAL_CONSTRAINTS.min_ok_far,
    pair_radius_m=DEFAULT_STRUCTURAL_CONSTRAINTS.pair_radius_m,
    assign_by_stop_radius_after=DEFAULT_STRUCTURAL_CONSTRAINTS.assign_by_stop_radius_after,
)


def _load_employees(csv_path: Path) -> List[Employee]:
    employees: List[Employee] = []
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


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    lat1_r = math.radians(lat1)
    lat2_r = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(
        dlon / 2
    ) ** 2
    c = 2 * math.asin(min(1.0, math.sqrt(a)))
    return r * c


def _build_duration_matrix(
    stops_coords: List[Tuple[float, float]],
    office_lat: float,
    office_lng: float,
    speed_kmh: float = 30.0,
) -> Tuple[np.ndarray, int]:
    S = len(stops_coords)
    N = S + 1
    D = np.zeros((N, N), dtype=float)
    office_idx = S
    all_coords: List[Tuple[float, float]] = stops_coords + [
        (office_lat, office_lng)
    ]
    for i in range(N):
        for j in range(N):
            if i == j:
                D[i, j] = 0.0
            else:
                lat1, lon1 = all_coords[i]
                lat2, lon2 = all_coords[j]
                dist_km = _haversine_km(lat1, lon1, lat2, lon2)
                hours = dist_km / max(speed_kmh, 1.0)
                D[i, j] = hours * 3600.0
    return D, office_idx


def _route_durations(
    routes_idx: List[List[int]], D: np.ndarray, office_idx: int
) -> List[float]:
    """Duración en segundos de cada ruta (misma fórmula que el motor)."""
    out: List[float] = []
    for seq in routes_idx:
        if not seq:
            out.append(0.0)
            continue
        t = 0.0
        for k in range(len(seq) - 1):
            t += float(D[seq[k], seq[k + 1]])
        t += float(D[seq[-1], office_idx])
        out.append(t)
    return out


def _compute_kpis(
    vrp_result: VRPResult,
    stops_demands: List[int],
    D: np.ndarray,
    office_idx: int,
    bus_capacity: int,
    label: str,
) -> Dict[str, Any]:
    n_routes = len(vrp_result.routes_idx)
    served = vrp_result.served_stop_indices
    out = vrp_result.unserved_stop_indices
    emp_served = sum(stops_demands[i] for i in served)
    emp_out = sum(stops_demands[i] for i in out)
    ioe = (
        100.0 * emp_served / (bus_capacity * n_routes)
        if n_routes > 0
        else 0.0
    )
    durs = _route_durations(vrp_result.routes_idx, D, office_idx)
    mean_dur_min = (np.mean(durs) / 60.0) if durs else 0.0
    max_dur_min = (max(durs) / 60.0) if durs else 0.0
    return {
        "label": label,
        "n_routes": n_routes,
        "n_served_stops": len(served),
        "n_out_stops": len(out),
        "emp_served": emp_served,
        "emp_out": emp_out,
        "ioe_pct": round(ioe, 1),
        "mean_route_dur_min": round(mean_dur_min, 1),
        "max_route_dur_min": round(max_dur_min, 1),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Comparar Block 5 baseline vs tuned (solo parámetros)"
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=DATA_CSV,
        help="CSV empleados",
    )
    parser.add_argument(
        "--office-lat",
        type=float,
        default=DEFAULT_OFFICE_LAT,
    )
    parser.add_argument(
        "--office-lng",
        type=float,
        default=DEFAULT_OFFICE_LNG,
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Guardar resumen en este path (extensión .md o .csv)",
    )
    args = parser.parse_args()

    if not args.csv.exists():
        print(f"ERROR: no existe {args.csv}")
        return 1

    employees = _load_employees(args.csv)
    print(f"Empleados: {len(employees)} desde {args.csv}")

    constraints_baseline = DEFAULT_STRUCTURAL_CONSTRAINTS
    final_clusters, _ = run_shuttle_stop_opening(
        employees, args.office_lat, args.office_lng, constraints_baseline
    )
    employees_by_id = {e.employee_id: e for e in employees}
    stops: List[ShuttleOption] = block4_clusters_to_shuttle_options(
        final_clusters, employees_by_id
    )
    if not stops:
        print("Block 4 no generó paradas; no hay nada que comparar.")
        return 0

    stops_coords = [(s.centroid_lat, s.centroid_lng) for s in stops]
    stops_demands = [s.estimated_size for s in stops]
    D, office_idx = _build_duration_matrix(
        stops_coords, args.office_lat, args.office_lng
    )

    # ---------- Baseline (V4 frozen) ----------
    baseline_min_emp = 15
    vrp_baseline = run_shuttle_vrp(
        stops_demands=stops_demands,
        duration_matrix=D,
        office_index=office_idx,
        constraints=constraints_baseline,
        min_emp_shuttle=baseline_min_emp,
    )
    kpis_baseline = _compute_kpis(
        vrp_baseline,
        stops_demands,
        D,
        office_idx,
        constraints_baseline.bus_capacity,
        "Baseline (V4 frozen)",
    )

    # ---------- Tuned (bajo riesgo) ----------
    vrp_tuned = run_shuttle_vrp(
        stops_demands=stops_demands,
        duration_matrix=D,
        office_index=office_idx,
        constraints=TUNED_STRUCTURAL_CONSTRAINTS,
        min_emp_shuttle=TUNED_MIN_EMP_SHUTTLE,
    )
    # Verificación: los parámetros usados son distintos
    assert constraints_baseline.backfill_max_delta_min != TUNED_STRUCTURAL_CONSTRAINTS.backfill_max_delta_min or baseline_min_emp != TUNED_MIN_EMP_SHUTTLE, (
        "Comparación inválida: baseline y tuned tienen los mismos parámetros."
    )
    kpis_tuned = _compute_kpis(
        vrp_tuned,
        stops_demands,
        D,
        office_idx,
        TUNED_STRUCTURAL_CONSTRAINTS.bus_capacity,
        "Tuned (bajo riesgo)",
    )

    # ---------- Tabla ----------
    print("\n--- Parámetros (realmente distintos) ---")
    print(
        f"  Baseline: MIN_EMP_SHUTTLE={baseline_min_emp}, BACKFILL_MAX_MIN_PER_PAX={constraints_baseline.backfill_max_delta_min}"
    )
    print(
        f"  Tuned:   MIN_EMP_SHUTTLE={TUNED_MIN_EMP_SHUTTLE}, BACKFILL_MAX_MIN_PER_PAX={TUNED_STRUCTURAL_CONSTRAINTS.backfill_max_delta_min}"
    )

    print("\n--- KPIs (mismo Block 5, mismos datos, distinta parametría) ---")
    print(f"  {'Métrica':<28}  {'Baseline (V4 frozen)':<22}  {'Tuned (bajo riesgo)':<22}")
    print("  " + "-" * 72)
    for key in [
        "n_routes",
        "n_served_stops",
        "n_out_stops",
        "emp_served",
        "emp_out",
        "ioe_pct",
        "mean_route_dur_min",
        "max_route_dur_min",
    ]:
        b = kpis_baseline[key]
        t = kpis_tuned[key]
        if isinstance(b, float):
            print(f"  {key:<28}  {b:<22}  {t:<22}")
        else:
            print(f"  {key:<28}  {b!s:<22}  {t!s:<22}")

    # Resumen breve
    print("\n--- Resumen ---")
    if kpis_tuned["emp_served"] > kpis_baseline["emp_served"]:
        print(
            f"  Tuned sirve a {kpis_tuned['emp_served'] - kpis_baseline['emp_served']} empleados más."
        )
    elif kpis_tuned["emp_served"] < kpis_baseline["emp_served"]:
        print(
            f"  Baseline sirve a {kpis_baseline['emp_served'] - kpis_tuned['emp_served']} empleados más."
        )
    else:
        print("  Mismo número de empleados servidos.")
    # Explicar por qué pueden ser idénticos
    if (
        kpis_baseline["n_routes"] == kpis_tuned["n_routes"]
        and kpis_baseline["n_out_stops"] == kpis_tuned["n_out_stops"]
        and kpis_baseline["n_out_stops"] == 0
    ):
        print(
            "  Nota: con 0 paradas fuera, el backfill no se ejecuta → BACKFILL_MAX no influye."
        )
        # Cargas por ruta (baseline) para ver si alguna está en [12, 15)
        loads = [
            sum(stops_demands[i] for i in seq)
            for seq in vrp_baseline.routes_idx
        ]
        small = [l for l in loads if 12 <= l < 15]
        if not small:
            print(
                "  Ninguna ruta tiene carga en [12, 15) → MIN_EMP_SHUTTLE 12 vs 15 no cambia qué se absorbe."
            )
    if kpis_tuned["ioe_pct"] > kpis_baseline["ioe_pct"]:
        print(f"  Tuned tiene mayor IOE (+{kpis_tuned['ioe_pct'] - kpis_baseline['ioe_pct']:.1f}%).")
    elif kpis_tuned["ioe_pct"] < kpis_baseline["ioe_pct"]:
        print(f"  Baseline tiene mayor IOE (+{kpis_baseline['ioe_pct'] - kpis_tuned['ioe_pct']:.1f}%).")
    if kpis_tuned["mean_route_dur_min"] > kpis_baseline["mean_route_dur_min"]:
        print(
            f"  Tuned tiene duración media de ruta mayor (+{kpis_tuned['mean_route_dur_min'] - kpis_baseline['mean_route_dur_min']:.1f} min)."
        )
    elif kpis_tuned["mean_route_dur_min"] < kpis_baseline["mean_route_dur_min"]:
        print(
            f"  Tuned tiene duración media de ruta menor ({kpis_baseline['mean_route_dur_min'] - kpis_tuned['mean_route_dur_min']:.1f} min)."
        )

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        if args.out.suffix.lower() == ".csv":
            with open(args.out, "w", encoding="utf-8") as f:
                f.write("metric,baseline,tuned\n")
                for key in [
                    "n_routes",
                    "n_served_stops",
                    "n_out_stops",
                    "emp_served",
                    "emp_out",
                    "ioe_pct",
                    "mean_route_dur_min",
                    "max_route_dur_min",
                ]:
                    f.write(
                        f"{key},{kpis_baseline[key]},{kpis_tuned[key]}\n"
                    )
        else:
            with open(args.out, "w", encoding="utf-8") as f:
                f.write("# Comparación Block 5 baseline vs tuned\n\n")
                f.write("| Métrica | Baseline | Tuned |\n")
                f.write("|---------|----------|-------|\n")
                for key in [
                    "n_routes",
                    "n_served_stops",
                    "n_out_stops",
                    "emp_served",
                    "emp_out",
                    "ioe_pct",
                    "mean_route_dur_min",
                    "max_route_dur_min",
                ]:
                    f.write(
                        f"| {key} | {kpis_baseline[key]} | {kpis_tuned[key]} |\n"
                    )
        print(f"\nResumen guardado en: {args.out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
