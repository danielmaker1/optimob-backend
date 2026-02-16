"""
Scientific comparison: V4 Block 4 vs V6 shuttle stop engine.
Uses frozen V4 employee dataset. Deterministic, no randomness.
"""

import csv
import math
import webbrowser
from pathlib import Path

import folium
import geopandas as gpd
import numpy as np
from shapely.geometry import Point
from sklearn.cluster import KMeans
from sklearn.neighbors import KDTree

from backend.v6.core.network_design_engine.shuttle_stop_engine import run_shuttle_stop_opening
from backend.v6.domain.constraints import StructuralConstraints
from backend.v6.domain.models import Employee

# ---------- V4 constants (Block 4) ----------
COORDENADAS_OFICINA = (40.4168, -3.7038)
ASSIGN_RADIUS_M = 1000
MAX_CLUSTER = 50
MIN_SHUTTLE = 6
MIN_STOP_SEP_M = 350
FALLBACK_MIN = 8
FALLBACK_SEP_M = 300
PAIR_RADIUS_M = 350
MIN_OK = 8
MAX_OK = 40
FUSION_RADIUS = 150
DIAMETER_MAX_M = 1500
EXCLUDE_RADIUS_M = 1000

FROZEN_CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "v4_employees_frozen.csv"


def _load_frozen_employees():
    """Load employees from frozen V4 CSV. Returns (empleados_data, employees). Deterministic."""
    empleados_data = []
    employees = []
    with open(FROZEN_CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            eid = row["employee_id"].strip()
            lat = float(row["home_lat"])
            lng = float(row["home_lng"])
            empleados_data.append({
                "id": eid,
                "coordenadas_casa": (lat, lng),
                "coordenadas_trabajo": COORDENADAS_OFICINA,
            })
            employees.append(
                Employee(employee_id=eid, home_lat=lat, home_lng=lng, willing_driver=False)
            )
    return empleados_data, employees


def _run_v4_block4(empleados_data):
    """Exact V4 Block 4 logic. Returns final_clusters (list of dicts with parada, n_empleados, employee ids), carpool_set (set of indices)."""
    latlon = [e["coordenadas_casa"] for e in empleados_data]
    gdf_wgs = gpd.GeoDataFrame(
        {"idx": list(range(len(latlon)))},
        geometry=[Point(lon, lat) for lat, lon in latlon],
        crs="EPSG:4326",
    )
    gdf_utm = gdf_wgs.to_crs(epsg=25830)
    X = np.column_stack([gdf_utm.geometry.x.values, gdf_utm.geometry.y.values])
    N = len(X)
    tree = KDTree(X)
    unassigned_shuttle_mask = np.ones(N, dtype=bool)

    def coverage_for_center(i_center, current_unassigned_mask, radius=ASSIGN_RADIUS_M, cap=MAX_CLUSTER):
        nbrs = tree.query_radius(X[i_center : i_center + 1], r=radius)[0]
        nbrs = [j for j in nbrs if current_unassigned_mask[j]]
        if not nbrs:
            return [], []
        dists = np.linalg.norm(X[nbrs] - X[i_center], axis=1)
        order = np.argsort(dists)
        take = [nbrs[k] for k in order][:cap]
        return take, [dists[k] for k in order][:cap]

    def greedy_open_stops(min_threshold, min_sep, initial_unassigned_mask):
        unassigned = initial_unassigned_mask.copy()
        centers_xy, members_list = [], []
        progressed = True
        while progressed:
            progressed = False
            best = {"gain": 0, "center": None, "take": None}
            for i in np.where(unassigned)[0]:
                take, _ = coverage_for_center(int(i), unassigned, radius=ASSIGN_RADIUS_M, cap=MAX_CLUSTER)
                gain = len(take)
                if gain > best["gain"]:
                    best.update({"gain": gain, "center": int(i), "take": take})
            if best["center"] is not None and best["gain"] >= min_threshold:
                centers_xy.append(X[best["center"]].copy())
                members_list.append(best["take"])
                unassigned[best["take"]] = False
                progressed = True
        return centers_xy, members_list, unassigned

    def best_medoid(members):
        if not members:
            return None
        pts = X[members]
        dmat = np.linalg.norm(pts[:, None, :] - pts[None, :, :], axis=2)
        return X[members[np.argmin(dmat.sum(axis=1))]].copy()

    def cluster_center_xy(idx_list):
        return X[idx_list].mean(axis=0) if idx_list else None

    def cluster_diameter(idx_list):
        if len(idx_list) <= 1:
            return 0.0
        pts = X[idx_list]
        if len(idx_list) <= 400:
            dx = pts[:, 0][:, None] - pts[:, 0][None, :]
            dy = pts[:, 1][:, None] - pts[:, 1][None, :]
            return float(np.sqrt((dx * dx + dy * dy).max()))
        minx, miny = pts.min(axis=0)
        maxx, maxy = pts.max(axis=0)
        return float(np.hypot(maxx - minx, maxy - miny))

    def to_wgs84_from_xy(xy):
        p_wgs = gpd.GeoSeries([Point(xy[0], xy[1])], crs="EPSG:25830").to_crs("EPSG:4326").iloc[0]
        return (float(p_wgs.y), float(p_wgs.x))

    centers_xy, members_list, unassigned = greedy_open_stops(MIN_SHUTTLE, MIN_STOP_SEP_M, unassigned_shuttle_mask)
    if len(centers_xy) == 0:
        centers_xy, members_list, unassigned = greedy_open_stops(FALLBACK_MIN, FALLBACK_SEP_M, unassigned_shuttle_mask)

    for i in range(len(centers_xy)):
        if members_list[i]:
            centers_xy[i] = best_medoid(members_list[i])

    assigned_mask = np.zeros(N, dtype=bool)
    for mems in members_list:
        assigned_mask[mems] = True
    cap_left = [MAX_CLUSTER - len(m) for m in members_list]
    for i in range(N):
        if assigned_mask[i]:
            continue
        for k, mems in enumerate(members_list):
            if cap_left[k] <= 0:
                continue
            if any(np.linalg.norm(X[i] - X[j]) <= PAIR_RADIUS_M for j in mems):
                members_list[k].append(i)
                cap_left[k] -= 1
                assigned_mask[i] = True
                break

    kept_clusters = []
    for mems in members_list:
        n = len(mems)
        if n < MIN_OK:
            continue
        if n > MAX_OK:
            k = int(math.ceil(n / MAX_OK))
            km = KMeans(n_clusters=k, n_init=10, random_state=42)
            labels = km.fit_predict(X[mems])
            for lab in range(k):
                sub = [mems[i] for i in range(n) if labels[i] == lab]
                if len(sub) >= MIN_OK:
                    kept_clusters.append(sub)
        else:
            kept_clusters.append(mems)

    changed = True
    while changed:
        changed = False
        centers_xy2 = [cluster_center_xy(c) for c in kept_clusters]
        to_remove = set()
        for i in range(len(kept_clusters)):
            if i in to_remove:
                continue
            for j in range(i + 1, len(kept_clusters)):
                if j in to_remove:
                    continue
                if np.linalg.norm(centers_xy2[i] - centers_xy2[j]) <= FUSION_RADIUS:
                    merged = sorted(set(kept_clusters[i] + kept_clusters[j]))
                    if len(merged) <= MAX_OK and cluster_diameter(merged) <= DIAMETER_MAX_M:
                        kept_clusters[i] = merged
                        to_remove.add(j)
                        changed = True
        if to_remove:
            kept_clusters = [c for k, c in enumerate(kept_clusters) if k not in to_remove]

    all_indices = set(range(N))
    all_assigned_to_shuttle = set(idx for mems in kept_clusters for idx in mems)
    carpool_set = all_indices - all_assigned_to_shuttle

    pt_utm = gpd.GeoSeries(
        [Point(COORDENADAS_OFICINA[1], COORDENADAS_OFICINA[0])],
        crs="EPSG:4326",
    ).to_crs(epsg=25830).iloc[0]
    oficina_xy = np.array([pt_utm.x, pt_utm.y])

    final_clusters = []
    for new_label, mems in enumerate(kept_clusters):
        cxy = cluster_center_xy(mems)
        if np.linalg.norm(cxy - oficina_xy) < EXCLUDE_RADIUS_M:
            carpool_set.update(mems)
            continue
        parada_latlon = to_wgs84_from_xy(cxy)
        final_clusters.append({
            "label": f"P{new_label}",
            "n_empleados": len(mems),
            "parada": parada_latlon,
            "employee_ids": [empleados_data[i]["id"] for i in mems],
        })
    return final_clusters, carpool_set


def _cluster_centroid_latlon(employee_ids, employees_by_id):
    lat = sum(employees_by_id[eid].home_lat for eid in employee_ids) / len(employee_ids)
    lng = sum(employees_by_id[eid].home_lng for eid in employee_ids) / len(employee_ids)
    return (lat, lng)


def _cluster_radius_m(latlon_list):
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


def main():
    empleados_data, employees = _load_frozen_employees()
    print(f"Loaded {len(employees)} employees from frozen V4 dataset")
    office_lat, office_lng = COORDENADAS_OFICINA

    final_clusters_v4, carpool_set_v4 = _run_v4_block4(empleados_data)
    num_excluded_v4 = len(carpool_set_v4)

    constraints = StructuralConstraints(
        assign_radius_m=float(ASSIGN_RADIUS_M),
        max_cluster_size=MAX_CLUSTER,
        bus_capacity=50,
        min_shuttle_occupancy=0.7,
        detour_cap=2.2,
        backfill_max_delta_min=1.35,
    )
    final_clusters_v6, carpool_set_v6 = run_shuttle_stop_opening(employees, office_lat, office_lng, constraints)
    num_excluded_v6 = len(carpool_set_v6)

    sizes_v4 = [c["n_empleados"] for c in final_clusters_v4]
    sizes_v6 = [len(c) for c in final_clusters_v6]
    num_clusters_v4 = len(final_clusters_v4)
    num_clusters_v6 = len(final_clusters_v6)
    mean_v4 = float(np.mean(sizes_v4)) if sizes_v4 else 0.0
    mean_v6 = float(np.mean(sizes_v6)) if sizes_v6 else 0.0
    std_v4 = float(np.std(sizes_v4)) if sizes_v4 else 0.0
    std_v6 = float(np.std(sizes_v6)) if sizes_v6 else 0.0

    print("--- Block 4 comparison ---")
    print("num_clusters_v4:", num_clusters_v4)
    print("num_clusters_v6:", num_clusters_v6)
    print("mean_cluster_size_v4:", mean_v4)
    print("mean_cluster_size_v6:", mean_v6)
    print("std_cluster_size_v4:", std_v4)
    print("std_cluster_size_v6:", std_v6)
    print("num_excluded_v4:", num_excluded_v4)
    print("num_excluded_v6:", num_excluded_v6)

    m = folium.Map(location=list(COORDENADAS_OFICINA), zoom_start=11)
    employees_by_id = {e.employee_id: e for e in employees}

    for e in employees:
        folium.CircleMarker(
            location=(e.home_lat, e.home_lng),
            radius=3,
            color="gray",
            fill=True,
            fill_opacity=0.7,
            weight=1,
            popup=e.employee_id,
        ).add_to(m)

    for c in final_clusters_v4:
        parada = c["parada"]
        folium.CircleMarker(
            location=parada,
            radius=12,
            color="blue",
            fill=True,
            fill_opacity=0.8,
            weight=2,
            popup=f"V4 {c['label']} n={c['n_empleados']}",
        ).add_to(m)
        pts = [(employees_by_id[eid].home_lat, employees_by_id[eid].home_lng) for eid in c["employee_ids"]]
        r_m = _cluster_radius_m(pts)
        folium.Circle(
            location=parada,
            radius=r_m,
            color="blue",
            fill=False,
            weight=2,
            dash_array="5,5",
        ).add_to(m)

    for c in final_clusters_v6:
        lat, lng = _cluster_centroid_latlon(c, employees_by_id)
        folium.CircleMarker(
            location=(lat, lng),
            radius=12,
            color="red",
            fill=True,
            fill_opacity=0.8,
            weight=2,
            popup=f"V6 n={len(c)}",
        ).add_to(m)
        pts = [(employees_by_id[eid].home_lat, employees_by_id[eid].home_lng) for eid in c]
        r_m = _cluster_radius_m(pts)
        folium.Circle(
            location=(lat, lng),
            radius=r_m,
            color="red",
            fill=False,
            weight=2,
            dash_array="2,4",
        ).add_to(m)

    folium.Marker(
        location=COORDENADAS_OFICINA,
        popup="Oficina",
        icon=folium.Icon(color="green", icon="building", prefix="fa"),
    ).add_to(m)

    out_path = Path(__file__).resolve().parent / "compare_block4.html"
    m.save(str(out_path))
    webbrowser.open(f"file://{out_path}")


if __name__ == "__main__":
    main()
