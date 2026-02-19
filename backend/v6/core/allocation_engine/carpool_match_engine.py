"""
Carpool match (6B). MPs por DBSCAN, candidatos con coste α·walk + β·detour + γ·ETA,
matching greedy con bonus δ, routing cheapest insertion + 2-opt, validación detour.
"""

from typing import List, Tuple

import numpy as np
from sklearn.cluster import DBSCAN
from sklearn.neighbors import BallTree

from backend.v6.domain.constraints import CarpoolMatchConfig
from backend.v6.domain.models import (
    CarpoolMatch,
    CarpoolPerson,
    DriverRoute,
    MeetingPoint,
)
from backend.v6.core.allocation_engine.carpool_time_adapter import CarpoolTimeAdapter


def _mps_por_cobertura(
    census: List[CarpoolPerson],
    config: CarpoolMatchConfig,
    adapter: CarpoolTimeAdapter,
) -> List[MeetingPoint]:
    """DBSCAN sobre (lat, lon) del censo → centroides → cluster suave → MPs."""
    if not census:
        return []
    X = np.array([[p.lat, p.lng] for p in census], dtype=float)
    X_rad = np.radians(X)
    eps_rad = config.dbscan_eps_m / 6371000.0
    db = DBSCAN(
        eps=eps_rad,
        min_samples=config.dbscan_min_samples,
        algorithm="ball_tree",
        metric="haversine",
    ).fit(X_rad)
    labels = db.labels_

    mps_raw: List[Tuple[float, float]] = []
    for k in sorted(set(labels)):
        if k == -1:
            continue
        mask = labels == k
        centroid_rad = X_rad[mask].mean(axis=0)
        lat, lon = float(np.degrees(centroid_rad[0])), float(np.degrees(centroid_rad[1]))
        mps_raw.append((lat, lon))

    if not mps_raw:
        return []
    if len(mps_raw) == 1:
        return [MeetingPoint(id_mp="MP_1", lat=mps_raw[0][0], lng=mps_raw[0][1])]

    # Cluster suave para deduplicar MPs
    Xm = np.radians(np.array(mps_raw))
    eps_m_rad = config.mp_cluster_eps_m / 6371000.0
    db2 = DBSCAN(eps=eps_m_rad, min_samples=1, algorithm="ball_tree", metric="haversine").fit(Xm)
    rep_lat = []
    rep_lon = []
    for k in sorted(set(db2.labels_)):
        mask = db2.labels_ == k
        c = np.degrees(Xm[mask].mean(axis=0))
        rep_lat.append(float(c[0]))
        rep_lon.append(float(c[1]))
    return [
        MeetingPoint(id_mp=f"MP_{i+1}", lat=rep_lat[i], lng=rep_lon[i])
        for i in range(len(rep_lat))
    ]


def _cheapest_insertion_order(
    t_src_to_mp: np.ndarray,
    t_mp_to_off: np.ndarray,
    t_mp_mp: np.ndarray,
) -> List[int]:
    n = len(t_mp_to_off)
    if n <= 1:
        return list(range(n))
    start = int(np.argmin(t_src_to_mp + t_mp_to_off))
    route = [start]
    remaining = [i for i in range(n) if i != start]

    def inc_cost(insert_pos: int, i: int) -> float:
        if insert_pos == 0:
            return t_src_to_mp[i] + t_mp_mp[i, route[0]] - t_src_to_mp[route[0]]
        if insert_pos == len(route):
            return t_mp_mp[route[-1], i] + t_mp_to_off[i] - t_mp_to_off[route[-1]]
        a, b = route[insert_pos - 1], route[insert_pos]
        return t_mp_mp[a, i] + t_mp_mp[i, b] - t_mp_mp[a, b]

    while remaining:
        best_i, best_pos, best_inc = None, 0, np.inf
        for i in remaining:
            for pos in range(len(route) + 1):
                inc = inc_cost(pos, i)
                if inc < best_inc:
                    best_inc, best_i, best_pos = inc, i, pos
        if best_i is None:
            break
        route.insert(best_pos, best_i)
        remaining.remove(best_i)
    return route


def _two_opt(
    route: List[int],
    t_src_to_mp: np.ndarray,
    t_mp_to_off: np.ndarray,
    t_mp_mp: np.ndarray,
    iters: int = 200,
    seed: int = 42,
) -> List[int]:
    if len(route) < 3:
        return route
    rng = np.random.default_rng(seed)

    def total_cost(rt: List[int]) -> float:
        if not rt:
            return 0.0
        c = t_src_to_mp[rt[0]]
        for i in range(len(rt) - 1):
            c += t_mp_mp[rt[i], rt[i + 1]]
        c += t_mp_to_off[rt[-1]]
        return c

    best = list(route)
    best_cost = total_cost(best)
    n = len(best)
    for _ in range(iters):
        i = int(rng.integers(0, max(1, n - 2)))
        k = int(rng.integers(i + 1, max(i + 2, n - 1)))
        if k >= n:
            k = n - 1
        new = best[:i] + best[i : k + 1][::-1] + best[k + 1 :]
        c = total_cost(new)
        if c < best_cost:
            best, best_cost = new, c
    return best


def run_carpool_match(
    census: List[CarpoolPerson],
    office_lat: float,
    office_lng: float,
    adapter: CarpoolTimeAdapter,
    config: CarpoolMatchConfig,
) -> Tuple[List[CarpoolMatch], List[DriverRoute], List[str]]:
    """
    Ejecuta el matching carpool (6B): MPs → candidatos → greedy → routing 2-opt → validación detour.
    Devuelve (matches, driver_routes, unmatched_pax_ids).
    """
    drivers = [p for p in census if p.is_driver]
    pax_list = [p for p in census if not p.is_driver]
    if not pax_list:
        return [], [], []
    if not drivers:
        return [], [], [p.person_id for p in pax_list]

    # 1) MPs
    mps = _mps_por_cobertura(census, config, adapter)
    if not mps:
        return [], [], [p.person_id for p in pax_list]

    D, P, M = len(drivers), len(pax_list), len(mps)
    drv_lat = np.array([p.lat for p in drivers])
    drv_lon = np.array([p.lng for p in drivers])
    pax_lat = np.array([p.lat for p in pax_list])
    pax_lon = np.array([p.lng for p in pax_list])
    mp_lat = np.array([mp.lat for mp in mps])
    mp_lon = np.array([mp.lng for mp in mps])

    # 2) Matrices
    T_drv_mp = np.zeros((D, M))
    T_mp_off = np.zeros(M)
    T_drv_off = np.zeros(D)
    for m in range(M):
        T_mp_off[m] = adapter.tt_min(mp_lat[m], mp_lon[m], office_lat, office_lng)
    for d in range(D):
        T_drv_off[d] = adapter.tt_min(drv_lat[d], drv_lon[d], office_lat, office_lng)
        for m in range(M):
            T_drv_mp[d, m] = adapter.tt_min(drv_lat[d], drv_lon[d], mp_lat[m], mp_lon[m])

    Walk_pax_mp = np.full((P, M), np.inf)
    for p in range(P):
        for m in range(M):
            w = adapter.walk_dist_m(pax_lat[p], pax_lon[p], mp_lat[m], mp_lon[m])
            if w <= config.max_walk_m:
                Walk_pax_mp[p, m] = w

    # Drivers candidatos por MP (top-N cercanos)
    drv_tree = BallTree(np.radians(np.c_[drv_lat, drv_lon]), metric="haversine")
    k_drv = min(config.max_drivers_per_mp, D)
    drivers_por_mp: List[np.ndarray] = []
    for m in range(M):
        _, idx = drv_tree.query(np.radians([[mp_lat[m], mp_lon[m]]]), k=k_drv)
        drivers_por_mp.append(idx[0])

    # 3) Candidatos
    alpha, beta, gamma = config.alpha_walk, config.beta_detour, config.gamma_eta_off
    cand_rows: List[Tuple[str, str, str, float, float, float, float, float, float, float]] = []
    for p in range(P):
        order_m = [m for m in np.argsort(Walk_pax_mp[p]) if np.isfinite(Walk_pax_mp[p, m])][
            : config.k_mp_pax
        ]
        if not order_m:
            continue
        hora_obj = pax_list[p].hora_obj_min if pax_list[p].hora_obj_min is not None else np.nan
        for m in order_m:
            walk_m = Walk_pax_mp[p, m]
            for d in drivers_por_mp[m]:
                d = int(d)
                t_route = T_drv_mp[d, m] + T_mp_off[m]
                t_direct = max(T_drv_off[d], 1e-6)
                detour_min = max(0.0, t_route - t_direct)
                detour_ratio = t_route / t_direct
                if detour_min > config.max_detour_min or detour_ratio > config.max_detour_ratio:
                    continue
                eta_pen = abs(t_route - hora_obj) if np.isfinite(hora_obj) else 0.0
                cost = alpha * walk_m + beta * detour_min + gamma * eta_pen
                cand_rows.append(
                    (
                        drivers[d].person_id,
                        pax_list[p].person_id,
                        mps[m].id_mp,
                        mp_lat[m],
                        mp_lon[m],
                        walk_m,
                        detour_min,
                        detour_ratio,
                        t_route,
                        cost,
                    )
                )

    if not cand_rows:
        return [], [], [p.person_id for p in pax_list]

    # 4) Greedy match
    cap_left = {p.person_id: p.cap_efectiva for p in drivers}
    assigned_pax: set = set()
    match_rows: List[dict] = []
    sorted_cand = sorted(cand_rows, key=lambda x: x[9])
    by_pax: dict = {}
    for r in sorted_cand:
        pax_id = r[1]
        if pax_id not in by_pax:
            by_pax[pax_id] = []
        by_pax[pax_id].append(r)

    delta = config.delta_occupancy_bonus
    for pax_id in list(by_pax.keys()):
        if pax_id in assigned_pax:
            continue
        best = None
        best_score = np.inf
        for r in by_pax[pax_id]:
            drv_id = r[0]
            if cap_left.get(drv_id, 0) <= 0:
                continue
            n_assign = sum(1 for m in match_rows if m["driver_id"] == drv_id)
            score = r[9] - delta * n_assign
            if score < best_score:
                best_score = score
                best = r
        if best is not None:
            match_rows.append(
                {
                    "driver_id": best[0],
                    "pax_id": best[1],
                    "id_mp": best[2],
                    "mp_lat": best[3],
                    "mp_lng": best[4],
                    "walk_m": best[5],
                    "detour_min": best[6],
                    "detour_ratio": best[7],
                    "eta_oficina_min": best[8],
                    "cost": best[9],
                }
            )
            assigned_pax.add(best[1])
            cap_left[best[0]] = cap_left.get(best[0], 0) - 1

    matches = [
        CarpoolMatch(
            driver_id=m["driver_id"],
            pax_id=m["pax_id"],
            id_mp=m["id_mp"],
            mp_lat=m["mp_lat"],
            mp_lng=m["mp_lng"],
            walk_m=m["walk_m"],
            detour_min=m["detour_min"],
            detour_ratio=m["detour_ratio"],
            eta_oficina_min=m["eta_oficina_min"],
            cost=m["cost"],
        )
        for m in match_rows
    ]

    # 5) Routing por conductor: cheapest insertion + 2-opt + validación detour
    driver_routes: List[DriverRoute] = []
    mp_id_to_idx = {mps[i].id_mp: i for i in range(M)}
    T_mp_mp = np.zeros((M, M))
    for i in range(M):
        for j in range(M):
            if i != j:
                T_mp_mp[i, j] = adapter.tt_min(mp_lat[i], mp_lon[i], mp_lat[j], mp_lon[j])

    driver_ids_done = set()
    for m in match_rows:
        drv_id = m["driver_id"]
        if drv_id in driver_ids_done:
            continue
        driver_ids_done.add(drv_id)
        grp_mp_ids = list({row["id_mp"] for row in match_rows if row["driver_id"] == drv_id})
        m_idx = [mp_id_to_idx[mid] for mid in grp_mp_ids if mid in mp_id_to_idx]
        if not m_idx:
            continue
        d_idx = next(i for i, p in enumerate(drivers) if p.person_id == drv_id)
        t_src = np.array([T_drv_mp[d_idx, m] for m in m_idx])
        t_off = np.array([T_mp_off[m] for m in m_idx])
        t_mm = T_mp_mp[np.ix_(m_idx, m_idx)]
        order_local = _cheapest_insertion_order(t_src, t_off, t_mm)
        if config.do_2opt:
            order_local = _two_opt(order_local, t_src, t_off, t_mm)

        def route_time(ord_l: List[int]) -> float:
            if not ord_l:
                return 0.0
            t = t_src[ord_l[0]]
            for i in range(len(ord_l) - 1):
                t += t_mm[ord_l[i], ord_l[i + 1]]
            t += t_off[ord_l[-1]]
            return float(t)

        t_route = route_time(order_local)
        t_direct = max(T_drv_off[d_idx], 1e-6)
        detour_min = max(0.0, t_route - t_direct)
        detour_ratio = t_route / t_direct
        while order_local and (
            detour_min > config.max_detour_min or detour_ratio > config.max_detour_ratio
        ):
            order_local = order_local[:-1]
            t_route = route_time(order_local)
            detour_min = max(0.0, t_route - t_direct)
            detour_ratio = t_route / t_direct
        if not order_local:
            continue
        keep_mp_ids = set(grp_mp_ids[i] for i in order_local)
        n_pax = len([row for row in match_rows if row["driver_id"] == drv_id and row["id_mp"] in keep_mp_ids])
        driver_routes.append(
            DriverRoute(
                driver_id=drv_id,
                order_mp_ids=[grp_mp_ids[i] for i in order_local],
                total_dur_min=t_route,
                detour_min=detour_min,
                detour_ratio=detour_ratio,
                n_pax=n_pax,
            )
        )

    # Solo mantener matches cuyo (driver, id_mp) sigue en la ruta final del conductor
    keep_mp_by_driver = {r.driver_id: set(r.order_mp_ids) for r in driver_routes}
    matches_filtered = [
        mt
        for mt in matches
        if mt.id_mp in keep_mp_by_driver.get(mt.driver_id, set())
    ]
    assigned_after_trim = {m.pax_id for m in matches_filtered}
    unmatched = [p.person_id for p in pax_list if p.person_id not in assigned_after_trim]
    return matches_filtered, driver_routes, unmatched
