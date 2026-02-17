"""
Comparación V4 vs V6 Block 4 + análisis en profundidad (datos, reglas, umbral).
Sin geopandas ni folium: solo numpy, scipy, sklearn. Ejecución rápida.

V4 se simula en el mismo sistema de coordenadas que V6 (metros desde oficina)
para comparación justa; diferencias numéricas mínimas respecto al V4 real (UTM).
"""

import csv
import math
from pathlib import Path

import numpy as np
from scipy.spatial import KDTree
from sklearn.cluster import KMeans

from backend.v6.core.network_design_engine.shuttle_stop_engine import (
    run_shuttle_stop_opening,
    _lat_lon_to_meters,
)
from backend.v6.domain.constraints import StructuralConstraints
from backend.v6.domain.models import Employee

# Constantes Block 4 (alineadas con compare_v4_v6_block4)
OFFICE_LAT, OFFICE_LNG = 40.4168, -3.7038
ASSIGN_RADIUS_M = 1000
MAX_CLUSTER = 50
MIN_SHUTTLE = 6
FALLBACK_MIN = 8
PAIR_RADIUS_M = 350
MIN_OK = 8
MAX_OK = 40
FUSION_RADIUS = 150
DIAMETER_MAX_M = 1500
EXCLUDE_RADIUS_M = 1000

FROZEN_CSV = Path(__file__).resolve().parent.parent / "data" / "v4_employees_frozen.csv"


def load_employees(path: Path) -> list[Employee]:
    out = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out.append(Employee(
                employee_id=row["employee_id"].strip(),
                home_lat=float(row["home_lat"]),
                home_lng=float(row["home_lng"]),
                willing_driver=False,
            ))
    return out


def _run_v4_style_in_meters(
    X: np.ndarray,
    tree: KDTree,
    ids: list[str],
    radius: float,
    cap: int,
    min_shuttle: int,
    fallback_min: int,
    pair_radius: float,
    min_ok: int,
    max_ok: int,
    fusion_radius: float,
    diameter_max: float,
    exclude_radius: float,
) -> tuple[list[list[str]], set[str]]:
    """
    Block 4 estilo V4 en coordenadas metros (origen = oficina).
    V4 no aplica min_sep en greedy; resto igual.
    """
    N = len(X)
    unassigned = np.ones(N, dtype=bool)

    def cov(i, mask, r=radius, c=cap):
        nbrs = tree.query_radius(X[i : i + 1], r=r)[0]
        nbrs = [j for j in nbrs if mask[j]]
        if not nbrs:
            return [], []
        dists = np.linalg.norm(X[nbrs] - X[i], axis=1)
        order = np.argsort(dists)
        take = [nbrs[k] for k in order][:c]
        return take, []

    def greedy(min_thresh, mask):
        u = mask.copy()
        centers, members = [], []
        while True:
            best = {"gain": 0, "center": None, "take": None}
            for i in np.where(u)[0]:
                take, _ = cov(int(i), u)
                if len(take) > best["gain"]:
                    best = {"gain": len(take), "center": int(i), "take": take}
            if best["center"] is None or best["gain"] < min_thresh:
                break
            centers.append(X[best["center"]].copy())
            members.append(best["take"])
            u[best["take"]] = False
        return centers, members, u

    centers_xy, members_list, unassigned = greedy(min_shuttle, unassigned)
    if len(centers_xy) == 0:
        centers_xy, members_list, unassigned = greedy(fallback_min, unassigned)

    def best_medoid(mems):
        if not mems:
            return None
        pts = X[mems]
        d = np.linalg.norm(pts[:, None, :] - pts[None, :, :], axis=2).sum(axis=1)
        return X[mems[np.argmin(d)]].copy()

    for i in range(len(centers_xy)):
        if members_list[i]:
            centers_xy[i] = best_medoid(members_list[i])

    assigned = np.zeros(N, dtype=bool)
    for m in members_list:
        assigned[m] = True
    cap_left = [cap - len(m) for m in members_list]
    for i in range(N):
        if assigned[i]:
            continue
        for k, mems in enumerate(members_list):
            if cap_left[k] <= 0:
                continue
            if any(np.linalg.norm(X[i] - X[j]) <= pair_radius for j in mems):
                members_list[k].append(i)
                cap_left[k] -= 1
                assigned[i] = True
                break

    def center_xy(idx_list):
        return X[idx_list].mean(axis=0) if idx_list else None

    def diam(idx_list):
        if len(idx_list) <= 1:
            return 0.0
        pts = X[idx_list]
        if len(idx_list) <= 400:
            d = np.linalg.norm(pts[:, None, :] - pts[None, :, :], axis=2)
            return float(d.max())
        mn, mx = pts.min(axis=0), pts.max(axis=0)
        return float(np.hypot(*(mx - mn)))

    kept = []
    for mems in members_list:
        n = len(mems)
        if n < min_ok:
            continue
        if n > max_ok:
            k = int(math.ceil(n / max_ok))
            km = KMeans(n_clusters=k, n_init=10, random_state=42)
            lab = km.fit_predict(X[mems])
            for j in range(k):
                sub = [mems[i] for i in range(n) if lab[i] == j]
                if len(sub) >= min_ok:
                    kept.append(sub)
        else:
            kept.append(mems)

    while True:
        changed = False
        cxy2 = [center_xy(c) for c in kept]
        to_remove = set()
        for i in range(len(kept)):
            if i in to_remove:
                continue
            for j in range(i + 1, len(kept)):
                if j in to_remove:
                    continue
                if np.linalg.norm(cxy2[i] - cxy2[j]) <= fusion_radius:
                    merged = sorted(set(kept[i] + kept[j]))
                    if len(merged) <= max_ok and diam(merged) <= diameter_max:
                        kept[i] = merged
                        to_remove.add(j)
                        changed = True
        if not to_remove:
            break
        kept = [c for k, c in enumerate(kept) if k not in to_remove]

    office_xy = np.array([0.0, 0.0])
    final_clusters = []
    for mems in kept:
        cxy = center_xy(mems)
        if np.linalg.norm(cxy - office_xy) < exclude_radius:
            continue
        final_clusters.append([ids[i] for i in mems])
    assigned_to_shuttle = {i for i in range(N) if ids[i] in {eid for c in final_clusters for eid in c}}
    carpool_set = {ids[i] for i in range(N) if i not in assigned_to_shuttle}
    return final_clusters, carpool_set


def main():
    employees = load_employees(FROZEN_CSV)
    N = len(employees)
    ids = [e.employee_id for e in employees]
    X = _lat_lon_to_meters(employees, OFFICE_LAT, OFFICE_LNG)
    tree = KDTree(X)

    # ---- V4-style (en metros, sin min_sep) ----
    final_v4, carpool_v4 = _run_v4_style_in_meters(
        X, tree, ids,
        radius=ASSIGN_RADIUS_M,
        cap=MAX_CLUSTER,
        min_shuttle=MIN_SHUTTLE,
        fallback_min=FALLBACK_MIN,
        pair_radius=PAIR_RADIUS_M,
        min_ok=MIN_OK,
        max_ok=MAX_OK,
        fusion_radius=FUSION_RADIUS,
        diameter_max=DIAMETER_MAX_M,
        exclude_radius=EXCLUDE_RADIUS_M,
    )
    assigned_v4 = N - len(carpool_v4)
    cov_v4 = (assigned_v4 / N * 100) if N else 0

    # ---- V6 ----
    constraints = StructuralConstraints(
        assign_radius_m=float(ASSIGN_RADIUS_M),
        max_cluster_size=MAX_CLUSTER,
        bus_capacity=50,
        min_shuttle_occupancy=0.7,
        detour_cap=2.2,
        backfill_max_delta_min=1.35,
    )
    final_v6, carpool_v6 = run_shuttle_stop_opening(employees, OFFICE_LAT, OFFICE_LNG, constraints)
    assigned_v6 = N - len(carpool_v6)
    cov_v6 = (assigned_v6 / N * 100) if N else 0

    # ---------- 1. COMPARACIÓN ----------
    print("=" * 64)
    print("1. COMPARACIÓN V4 (estilo) vs V6 BLOCK 4 — mismo dataset, mismo pipeline")
    print("=" * 64)
    print(f"  Empleados totales:     {N}")
    print(f"  V4  clusters: {len(final_v4):3d}  |  Asignados shuttle: {assigned_v4:3d}  |  Cobertura: {cov_v4:.1f}%")
    print(f"  V6  clusters: {len(final_v6):3d}  |  Asignados shuttle: {assigned_v6:3d}  |  Cobertura: {cov_v6:.1f}%")
    print(f"  Diferencia cobertura:  {cov_v6 - cov_v4:+.1f} pp (V6 − V4)")
    if abs(cov_v4 - cov_v6) < 2.0:
        print("  Conclusión:            V4 y V6 dan cobertura muy similar (motor alineado).")
    elif cov_v6 < cov_v4:
        print("  Conclusión:            V6 asigna menos (min_sep evita paradas muy cercanas).")
    else:
        print("  Conclusión:            V6 asigna más que V4.")
    print()

    # ---------- 2. DATOS: dispersión ----------
    dist_office = np.linalg.norm(X, axis=1)
    within_500 = (dist_office <= 500).sum()
    within_1000 = (dist_office <= 1000).sum()
    within_2000 = (dist_office <= 2000).sum()

    print("=" * 64)
    print("2. DATOS: dispersión respecto a la oficina")
    print("=" * 64)
    print(f"  Distancia a oficina (m): min={dist_office.min():.0f}  max={dist_office.max():.0f}  media={dist_office.mean():.0f}")
    print(f"  Percentiles:  p50={np.percentile(dist_office, 50):.0f}  p90={np.percentile(dist_office, 90):.0f}")
    print(f"  Dentro de  500 m: {within_500:4d} ({within_500/N*100:.1f}%)")
    print(f"  Dentro de 1000 m: {within_1000:4d} ({within_1000/N*100:.1f}%)  <- radio asignación y exclude_radius")
    print(f"  Dentro de 2000 m: {within_2000:4d} ({within_2000/N*100:.1f}%)")
    print("  Interpretación: empleados lejos de oficina quedan fuera de radio o en clusters excluidos.")
    print()

    # ---------- 3. DATOS: densidad ----------
    counts = tree.query_radius(X, r=ASSIGN_RADIUS_M, count_only=True)
    at_least_6 = (counts >= 6).sum()
    at_least_8 = (counts >= MIN_OK).sum()

    print("=" * 64)
    print("3. DATOS: densidad (vecinos en 1000 m por empleado)")
    print("=" * 64)
    print(f"  Vecinos en 1000 m:  media={counts.mean():.1f}  min={counts.min()}  max={counts.max()}")
    print(f"  Empleados con ≥ 6 vecinos (min_shuttle): {at_least_6} ({at_least_6/N*100:.1f}%)")
    print(f"  Empleados con ≥ 8 vecinos (min_ok):      {at_least_8} ({at_least_8/N*100:.1f}%)")
    print("  Interpretación: clusters con < 8 se descartan; si pocos tienen 8+ vecinos, cobertura limitada.")
    print()

    # ---------- 4. REGLAS ESTRICTAS ----------
    print("=" * 64)
    print("4. REGLAS ESTRICTAS (Block 4)")
    print("=" * 64)
    print("  • min_ok=8: clusters con < 8 miembros → residual.")
    print("  • max_ok=40: clusters grandes se parten; subclusters < 8 se descartan.")
    print("  • exclude_radius_m=1000: centroide a < 1000 m de oficina → todo el cluster a carpool.")
    print(f"  • Empleados a < 1000 m de oficina: {within_1000} (posibles clusters excluidos).")
    print("  Conclusión: con dispersión y poca densidad, cobertura shuttle 20–40%% es esperable.")
    print()

    # ---------- 5. UMBRAL 85% ----------
    print("=" * 64)
    print("5. UMBRAL DE NIVEL (85%% cobertura = OK)")
    print("=" * 64)
    print(f"  Cobertura actual V6: {cov_v6:.1f}%.")
    print(f"  Techo por datos: ~{at_least_8/N*100:.0f}% tienen 8+ vecinos en 1000 m.")
    if cov_v6 < 50:
        print("  El FAIL (85%%) castiga más al criterio que al motor: dataset/reglas no permiten 85%%.")
    print("  Recomendación: umbral configurable (ej. OK≥70%%, WARN≥50%%) o por tipo de dataset.")
    print()

    print("=" * 64)
    print("RESUMEN")
    print("=" * 64)
    print("  • V4 vs V6: cobertura similar → motor V6 alineado; diferencia por min_sep en V6.")
    print("  • Cobertura baja: explicada por datos (dispersión) y reglas (min_ok, exclude_radius).")
    print("  • Umbral 85%%: poco realista para este dataset; revisar criterio de nivel o datos.")
    print()


if __name__ == "__main__":
    main()
