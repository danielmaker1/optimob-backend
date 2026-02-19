"""
V6 shuttle VRP engine. Migrated from V4 Block 5.

Pure logic only:
- No Google client, no OSMnx, no Folium, no FastAPI.
- Receives an already-built duration matrix D and high-level constraints.

Implements:
- Route class (seq, load, dur, feasible_merge_with, merge_with)
- Clarke–Wright open VRP (open routes that end at office)
- Small-route absorption (MIN_EMP_SHUTTLE)
- Backfill constrained by detour cap and BACKFILL_MAX_MIN_PER_PAX

The goal is to mirror V4 Block 5 semantics while keeping a clean, testable engine.
"""

from dataclasses import dataclass
from typing import List, Sequence, Set, Tuple

import numpy as np

from backend.v6.domain.constraints import StructuralConstraints


# Defaults taken from V4 frozen notebook (Block 5)
BUS_CAPACITY_DEFAULT = 50
MAX_STOPS_DEFAULT = 8  # máximo nº de paradas por ruta
MAX_ROUTE_DURATION_DEFAULT = 5400  # 90 minutos en segundos
MIN_EMP_SHUTTLE_DEFAULT = 15  # mínimo de empleados para que una ruta sea viable


@dataclass
class Route:
    """
    Open shuttle route: sequence of stop indices, total load (employees) and duration (seconds).

    Duration is computed as:
      sum_k D[seq[k], seq[k+1]] + D[seq[-1], office_index]
    mirroring V4 Block 5.
    """

    seq: List[int]
    stops_demands: Sequence[int]
    D: np.ndarray
    office_index: int
    T_to_office: np.ndarray
    bus_capacity: int
    max_stops: int
    max_route_duration: int
    detour_cap: float

    load: int = 0
    dur: int = 0

    def __post_init__(self) -> None:
        self.seq = list(self.seq)
        self.load = int(sum(self.stops_demands[i] for i in self.seq))
        self.dur = self._calc_duration()

    def _calc_duration(self) -> int:
        if not self.seq:
            return 0
        t = 0.0
        for k in range(len(self.seq) - 1):
            t += float(self.D[self.seq[k], self.seq[k + 1]])
        t += float(self.D[self.seq[-1], self.office_index])
        return int(t)

    def head(self) -> int:
        return self.seq[0]

    def tail(self) -> int:
        return self.seq[-1]

    def feasible_merge_with(
        self,
        other: "Route",
    ) -> Tuple[float, float, int, int] | None:
        """
        Check if self -> other merge is feasible under capacity, stops and detour caps.

        Returns:
            (saving, new_dur, new_load, new_len) or None if infeasible.
        """
        # Same directional condition as V4: no backwards towards office
        if self.T_to_office[self.tail()] <= self.T_to_office[other.head()]:
            return None

        new_load = self.load + other.load
        new_len = len(self.seq) + len(other.seq)
        if new_load > self.bus_capacity or new_len > self.max_stops:
            return None

        new_dur = (
            self.dur
            - float(self.D[self.tail(), self.office_index])
            + float(self.D[self.tail(), other.head()])
            + other.dur
        )
        if new_dur > self.max_route_duration:
            return None

        # Detour cap check
        combined = self.seq + other.seq
        base_mean = float(np.mean([self.T_to_office[i] for i in combined]))
        if base_mean > 0.0 and new_dur / base_mean > self.detour_cap:
            return None

        saving = float(self.D[self.tail(), self.office_index]) - float(
            self.D[self.tail(), other.head()]
        )
        return saving, new_dur, new_load, new_len

    def merge_with(self, other: "Route", new_dur: float, new_load: int) -> None:
        """In-place merge of other into self, updating seq/load/dur."""
        self.seq += other.seq
        self.load = new_load
        self.dur = int(new_dur)


@dataclass(frozen=True)
class VRPResult:
    """Output of the shuttle VRP engine."""

    routes_idx: List[List[int]]
    served_stop_indices: Set[int]
    unserved_stop_indices: List[int]


def run_shuttle_vrp(
    stops_demands: Sequence[int],
    duration_matrix: np.ndarray,
    office_index: int,
    constraints: StructuralConstraints,
    min_emp_shuttle: int = MIN_EMP_SHUTTLE_DEFAULT,
    max_stops: int = MAX_STOPS_DEFAULT,
    max_route_duration: int = MAX_ROUTE_DURATION_DEFAULT,
) -> VRPResult:
    """
    Run V4-style Clarke–Wright open VRP + small-route absorption + backfill.

    Args:
        stops_demands: demand (employees) per stop, length S.
        duration_matrix: ndarray (N,N) with travel times in seconds.
            V4 convention: N = S+1 and office_index = S, but we only require that
            duration_matrix has office_index as the row/col used for office travel times.
        office_index: index of the office node in duration_matrix.
        constraints: StructuralConstraints with at least:
            - bus_capacity
            - detour_cap
            - backfill_max_delta_min (BACKFILL_MAX_MIN_PER_PAX)
        min_emp_shuttle: MIN_EMP_SHUTTLE (minimum employees for a viable route).
        max_stops: MAX_STOPS (max number of stops per route).
        max_route_duration: MAX_ROUTE_DURATION (seconds).

    Returns:
        VRPResult with:
            - routes_idx: list of sequences of stop indices.
            - served_stop_indices: set of stops that belong to some route.
            - unserved_stop_indices: list of stops left out.
    """
    if not stops_demands:
        return VRPResult(routes_idx=[], served_stop_indices=set(), unserved_stop_indices=[])

    D = np.asarray(duration_matrix, dtype=float)
    S = len(stops_demands)
    if D.shape[0] != D.shape[1]:
        raise ValueError("duration_matrix must be square")
    if S >= D.shape[0]:
        raise ValueError("duration_matrix too small for number of stops")

    bus_capacity = constraints.bus_capacity if constraints.bus_capacity > 0 else BUS_CAPACITY_DEFAULT
    detour_cap = constraints.detour_cap
    backfill_max_min_per_pax = constraints.backfill_max_delta_min

    # Time from each stop to office
    T_to_office = np.array([D[i, office_index] for i in range(S)], dtype=float)

    # ---------- Inicialización ----------
    routes: List[Route] = [
        Route(
            seq=[i],
            stops_demands=stops_demands,
            D=D,
            office_index=office_index,
            T_to_office=T_to_office,
            bus_capacity=bus_capacity,
            max_stops=max_stops,
            max_route_duration=max_route_duration,
            detour_cap=detour_cap,
        )
        for i in range(S)
    ]

    # ---------- Clarke–Wright "open" ----------
    merged = True
    while merged and len(routes) > 1:
        merged = False
        best: Tuple[Tuple[float, int], int, int, float, int] | None = None
        for a in range(len(routes)):
            for b in range(len(routes)):
                if a == b:
                    continue
                feas = routes[a].feasible_merge_with(routes[b])
                if feas is None:
                    continue
                saving, new_dur, new_load, _ = feas
                key = (saving, new_load)
                if best is None or key > best[0]:
                    best = (key, a, b, new_dur, new_load)
        if best is not None:
            _, a_idx, b_idx, new_dur, new_load = best
            routes[a_idx].merge_with(routes[b_idx], new_dur, new_load)
            routes.pop(b_idx)
            merged = True

    # ---------- Limpieza: rutas pequeñas ----------
    small_idxs = [r for r in range(len(routes)) if routes[r].load < min_emp_shuttle]
    for r_idx in sorted(small_idxs, reverse=True):
        r_small = routes[r_idx]
        absorbed = False
        order = sorted(
            [i for i in range(len(routes)) if i != r_idx],
            key=lambda k: routes[k].load,
            reverse=True,
        )
        for k in order:
            feas = routes[k].feasible_merge_with(r_small)
            if feas:
                _, new_dur, new_load, _ = feas
                routes[k].merge_with(r_small, new_dur, new_load)
                routes.pop(r_idx)
                absorbed = True
                break
        if not absorbed:
            # keep small route as-is (same as V4: no explicit deletion here)
            pass

    # ---------- Backfill barato ----------
    served_idx: Set[int] = {i for r in routes for i in r.seq}
    pending = sorted(
        [i for i in range(S) if i not in served_idx],
        key=lambda i: (-stops_demands[i], -T_to_office[i]),
    )

    changed = True
    while changed and pending:
        changed = False
        for i in list(pending):
            best: Tuple[Tuple[float, int, int], int, float] | None = None
            for r_id, r in enumerate(routes):
                # Capacity and max stops
                if r.load + stops_demands[i] > bus_capacity:
                    continue
                if len(r.seq) + 1 > max_stops:
                    continue
                # Direction towards office
                if T_to_office[i] >= T_to_office[r.tail()]:
                    continue
                t_curr = float(r.dur)
                t_new = (
                    r.dur
                    - float(D[r.tail(), office_index])
                    + float(D[r.tail(), i])
                    + float(D[i, office_index])
                )
                if t_new > max_route_duration:
                    continue
                base_mean = float(np.mean([T_to_office[k] for k in (r.seq + [i])]))
                if base_mean <= 0.0:
                    continue
                detour_ratio = t_new / base_mean
                if detour_ratio > detour_cap:
                    continue

                delta_min_per_pax = ((t_new - t_curr) / 60.0) / max(1, stops_demands[i])
                if delta_min_per_pax <= backfill_max_min_per_pax:
                    key = (
                        delta_min_per_pax,
                        -stops_demands[i],
                        -(r.load + stops_demands[i]),
                    )
                    if best is None or key < best[0]:
                        best = (key, r_id, t_new)

            if best:
                _, r_id, t_new = best
                routes[r_id].seq.append(i)
                routes[r_id].load += stops_demands[i]
                routes[r_id].dur = int(t_new)
                pending.remove(i)
                changed = True

    routes_idx: List[List[int]] = [r.seq for r in routes]
    served_idx = {i for seq in routes_idx for i in seq}
    stops_out_idx = [i for i in range(S) if i not in served_idx]

    return VRPResult(
        routes_idx=routes_idx,
        served_stop_indices=served_idx,
        unserved_stop_indices=stops_out_idx,
    )

