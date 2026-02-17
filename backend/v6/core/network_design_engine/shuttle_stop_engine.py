"""
V6 shuttle stop engine. Migrated from V4 Block 4. Pure logic only.
No Folium, Google, FastAPI. All globals become explicit parameters.
"""

import math
from dataclasses import dataclass
from typing import List, Set, Tuple

import numpy as np
from scipy.spatial import KDTree
from sklearn.cluster import KMeans

from backend.v6.domain.constraints import StructuralConstraints
from backend.v6.domain.models import Employee

# Defaults from V4 Block 4 (used when not on StructuralConstraints)
MIN_STOP_SEP_M = 350.0
FALLBACK_MIN = 8
FALLBACK_SEP_M = 300.0
PAIR_RADIUS_M = 350.0
MIN_OK = 8
MAX_OK = 40
FUSION_RADIUS = 150.0
DIAMETER_MAX_M = 1500.0
EXCLUDE_RADIUS_M = 1000.0
M_PER_DEG_LAT = 111320.0


@dataclass(frozen=True)
class ShuttleStopParams:
    """Block 4 parameters. Use getattr(constraints, name, default) or pass explicitly."""
    min_stop_sep_m: float = MIN_STOP_SEP_M
    fallback_min: int = FALLBACK_MIN
    fallback_sep_m: float = FALLBACK_SEP_M
    pair_radius_m: float = PAIR_RADIUS_M
    min_ok: int = MIN_OK
    max_ok: int = MAX_OK
    fusion_radius: float = FUSION_RADIUS
    diameter_max_m: float = DIAMETER_MAX_M
    exclude_radius_m: float = EXCLUDE_RADIUS_M


def _lat_lon_to_meters(
    employees: List[Employee], office_lat: float, office_lng: float
) -> np.ndarray:
    """Local tangent plane: origin at office. Returns (N, 2) in meters."""
    cos_lat = math.cos(math.radians(office_lat))
    ys = np.array([e.home_lat for e in employees])
    xs = np.array([e.home_lng for e in employees])
    y_m = (ys - office_lat) * M_PER_DEG_LAT
    x_m = (xs - office_lng) * M_PER_DEG_LAT * cos_lat
    return np.column_stack([y_m, x_m])


def coverage_for_center(
    i_center: int,
    X: np.ndarray,
    tree: KDTree,
    current_unassigned_mask: np.ndarray,
    radius: float,
    cap: int,
) -> Tuple[List[int], List[float]]:
    """Neighbors within radius that are unassigned, sorted by distance, capped."""
    nbrs = tree.query_ball_point(X[i_center : i_center + 1], r=radius)[0]
    nbrs = [j for j in nbrs if current_unassigned_mask[j]]
    if not nbrs:
        return [], []
    dists = np.linalg.norm(X[nbrs] - X[i_center], axis=1)
    order = np.argsort(dists)
    take = [nbrs[k] for k in order][:cap]
    return take, [float(dists[k]) for k in order][:cap]


def greedy_open_stops(
    X: np.ndarray,
    tree: KDTree,
    min_threshold: int,
    radius: float,
    cap: int,
    initial_unassigned_mask: np.ndarray,
    min_sep: float,
) -> Tuple[List[np.ndarray], List[List[int]], np.ndarray]:
    """
    Greedy stop opening: best gain >= min_threshold until no progress.
    Enforces minimum separation (min_sep) between stop centers.
    Tie-break: same gain -> smaller center index (deterministic).
    """
    unassigned = initial_unassigned_mask.copy()
    centers_xy: List[np.ndarray] = []
    members_list: List[List[int]] = []
    progressed = True
    while progressed:
        progressed = False
        best: dict = {"gain": 0, "center": None, "take": None}
        for i in np.where(unassigned)[0]:
            if too_close(X[i], centers_xy, min_sep):
                continue
            take, _ = coverage_for_center(
                int(i), X, tree, unassigned, radius=radius, cap=cap
            )
            gain = len(take)
            if gain > best["gain"] or (
                gain == best["gain"]
                and (best["center"] is None or i < best["center"])
            ):
                best.update({"gain": gain, "center": int(i), "take": take})
        if best["center"] is not None and best["gain"] >= min_threshold:
            centers_xy.append(X[best["center"]].copy())
            members_list.append(best["take"])
            unassigned[best["take"]] = False
            progressed = True
    return centers_xy, members_list, unassigned


def too_close(center_xy: np.ndarray, centers_xy: List[np.ndarray], min_sep: float) -> bool:
    """True if center_xy is within min_sep of any existing center."""
    if not centers_xy:
        return False
    dif = np.array(centers_xy) - center_xy
    return bool((dif[:, 0] ** 2 + dif[:, 1] ** 2 <= (min_sep ** 2)).any())


def best_medoid(members: List[int], X: np.ndarray) -> np.ndarray:
    """Point in members that minimizes sum of distances to others."""
    if not members:
        raise ValueError("empty members")
    pts = X[members]
    dmat = np.linalg.norm(pts[:, None, :] - pts[None, :, :], axis=2)
    idx = int(np.argmin(dmat.sum(axis=1)))
    return X[members[idx]].copy()


def cluster_center_xy(idx_list: List[int], X: np.ndarray) -> np.ndarray:
    """Mean of X at idx_list."""
    if not idx_list:
        raise ValueError("empty idx_list")
    return X[idx_list].mean(axis=0)


def cluster_diameter(idx_list: List[int], X: np.ndarray) -> float:
    """Max pairwise distance in cluster; for n>400 use bbox diagonal."""
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


def run_shuttle_stop_opening(
    employees: List[Employee],
    office_lat: float,
    office_lng: float,
    constraints: StructuralConstraints,
) -> Tuple[List[List[str]], Set[str]]:
    """
    Full Block 4 pipeline. Returns final_clusters (list of list of employee_id),
    carpool_set (set of employee_id for residual).
    Block 4 params come from constraints via getattr with V4 defaults.
    """
    if not employees:
        return [], set()
    ids = [e.employee_id for e in employees]
    X = _lat_lon_to_meters(employees, office_lat, office_lng)
    N = len(X)
    tree = KDTree(X)
    radius = constraints.assign_radius_m
    cap = constraints.max_cluster_size
    min_shuttle = getattr(constraints, "min_shuttle", 6)
    min_sep = getattr(constraints, "min_stop_sep_m", MIN_STOP_SEP_M)
    fallback_min = getattr(constraints, "fallback_min", FALLBACK_MIN)
    fallback_sep = getattr(constraints, "fallback_sep_m", FALLBACK_SEP_M)
    pair_radius = getattr(constraints, "pair_radius_m", None) or PAIR_RADIUS_M
    min_ok = getattr(constraints, "min_ok", MIN_OK)
    min_ok_far_m = getattr(constraints, "min_ok_far_m", None)
    min_ok_far = getattr(constraints, "min_ok_far", 6)
    max_ok = getattr(constraints, "max_ok", MAX_OK)
    fusion_radius = getattr(constraints, "fusion_radius", FUSION_RADIUS)
    diameter_max_m = getattr(constraints, "diameter_max_m", DIAMETER_MAX_M)
    exclude_radius_m = getattr(constraints, "exclude_radius_m", EXCLUDE_RADIUS_M)

    unassigned_shuttle_mask = np.ones(N, dtype=bool)
    centers_xy, members_list, unassigned = greedy_open_stops(
        X, tree, min_shuttle, radius, cap, unassigned_shuttle_mask, min_sep
    )
    if len(centers_xy) == 0:
        centers_xy, members_list, unassigned = greedy_open_stops(
            X, tree, fallback_min, radius, cap, unassigned_shuttle_mask, min_sep
        )

    for i in range(len(centers_xy)):
        if members_list[i]:
            centers_xy[i] = best_medoid(members_list[i], X)

    assigned_mask = np.zeros(N, dtype=bool)
    for mems in members_list:
        assigned_mask[mems] = True
    cap_left = [cap - len(m) for m in members_list]
    for i in range(N):
        if assigned_mask[i]:
            continue
        for k, mems in enumerate(members_list):
            if cap_left[k] <= 0:
                continue
            if any(np.linalg.norm(X[i] - X[j]) <= pair_radius for j in mems):
                members_list[k].append(i)
                cap_left[k] -= 1
                assigned_mask[i] = True
                break

    def effective_min_ok(members: List[int]) -> int:
        """min_ok adaptativo: si min_ok_far_m está definido, clusters lejos de oficina usan min_ok_far (ej. 6)."""
        if min_ok_far_m is None or min_ok_far_m <= 0 or min_ok_far >= min_ok:
            return min_ok
        cxy = cluster_center_xy(members, X)
        dist_to_office = float(np.linalg.norm(cxy))
        return min_ok_far if dist_to_office > min_ok_far_m else min_ok

    kept_clusters: List[List[int]] = []
    for mems in members_list:
        n = len(mems)
        eff_min = effective_min_ok(mems)
        if n < eff_min:
            continue
        if n > max_ok:
            k = int(math.ceil(n / max_ok))
            km = KMeans(n_clusters=k, n_init=10, random_state=42)
            labels = km.fit_predict(X[mems])
            for lab in range(k):
                sub = [mems[i] for i in range(n) if labels[i] == lab]
                if not sub:
                    continue
                sub_min = effective_min_ok(sub)
                if len(sub) >= sub_min:
                    kept_clusters.append(sub)
        else:
            kept_clusters.append(mems)

    changed = True
    while changed:
        changed = False
        centers_xy2 = [cluster_center_xy(c, X) for c in kept_clusters]
        to_remove: Set[int] = set()
        for i in range(len(kept_clusters)):
            if i in to_remove:
                continue
            for j in range(i + 1, len(kept_clusters)):
                if j in to_remove:
                    continue
                if np.linalg.norm(centers_xy2[i] - centers_xy2[j]) <= fusion_radius:
                    merged = sorted(set(kept_clusters[i] + kept_clusters[j]))
                    if len(merged) <= max_ok and cluster_diameter(merged, X) <= diameter_max_m:
                        kept_clusters[i] = merged
                        to_remove.add(j)
                        changed = True
        if to_remove:
            kept_clusters = [c for k, c in enumerate(kept_clusters) if k not in to_remove]

    all_indices = set(range(N))
    all_assigned_to_shuttle = set(idx for mems in kept_clusters for idx in mems)
    carpool_indices = all_indices - all_assigned_to_shuttle

    office_xy = np.array([0.0, 0.0])
    final_clusters_indices: List[List[int]] = []
    for mems in kept_clusters:
        cxy = cluster_center_xy(mems, X)
        if np.linalg.norm(cxy - office_xy) < exclude_radius_m:
            carpool_indices.update(mems)
            continue
        final_clusters_indices.append(mems)

    final_clusters: List[List[str]] = [
        [ids[i] for i in cluster] for cluster in final_clusters_indices
    ]
    carpool_set: Set[str] = {ids[i] for i in carpool_indices}
    return final_clusters, carpool_set
