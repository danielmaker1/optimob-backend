# Optimob V6 — Definitive Two-Layer Architecture

**Document:** Structural analysis from V4, two-layer core design, objective formalization, trigger logic, scalability, risks, roadmap.  
**Model:** Structural Network Design (weekly) + Daily Allocation (48h before operation). No simplification of V4 algorithms.

---

# PHASE 1 — STRUCTURAL ANALYSIS

## 1.1 What V4 Actually Does (Single Run)

V4 runs one end-to-end pipeline: generate population → open stops → VRP → evaluate shuttle → residual (carpool_set) → carpool MPs → carpool matching → KPIs → Sheets/Folium. There is no separate “reservation” or “daily allocation” step in the notebook; the **two-tier model is a product decision for V6**. We assign V4 components to layers by **semantic role**: what must be fixed for the week vs what depends on the day’s reservations.

## 1.2 Structural Components (ONLY for Weekly Network Design)

These define the **fixed network** that does not change day-to-day.

| V4 location | Component | Role in Layer A |
|-------------|-----------|------------------|
| Block 4 | Employee coordinates (lat/lon) → UTM, KDTree | Input to stop opening; census/snapshot. |
| Block 4 | `coverage_for_center`, `greedy_open_stops` | Shuttle stop generation (radius, cap). |
| Block 4 | `too_close`, `best_medoid` | Medoid refinement, min separation. |
| Block 4 | `cluster_center_xy`, `cluster_diameter` | Cluster geometry for merge constraint. |
| Block 4 | KMeans split (MIN_OK, MAX_OK) | Split oversized clusters. |
| Block 4 | Prudent merge (FUSION_RADIUS, DIAMETER_MAX_M) | Merge without exceeding MAX_OK. |
| Block 4 | Office exclusion (EXCLUDE_RADIUS_M) | Add excluded to carpool pool; define “residual” pool. |
| Block 4 | **Output:** `final_clusters`, `carpool_set` | Stops = clusters; residual = carpool candidate set. |
| Block 5 | `stops_coords`, `stops_demands` from final_clusters | Input to VRP. |
| Block 5 | Duration matrix D (N×N, N = S+1) | From time adapter; structural because stops are fixed. |
| Block 5 | `Route` class (seq, load, dur, feasible_merge_with, merge_with) | Open VRP model. |
| Block 5 | Clarke–Wright open loop (savings, capacity, MAX_STOPS, DETOUR_CAP) | Structural routes. |
| Block 5 | Small-route absorption, BACKFILL (delta_min_per_pax, DETOUR_CAP) | Final route set. |
| Block 5 | **Output:** `routes_idx`, served_idx, unserved stop indices | **Fixed shuttle routes** (sequence of stop indices). |
| Post-VRP | IOE, balance, rutas &lt;20, media pax | Structural evaluation of the network. |
| 6A | DBSCAN → meeting points → snap → MP cluster (`_mps_por_cobertura`) | **Structural carpool base:** fixed set of MPs. |
| 6A | Graph G (drive) for carpool, `nearest_node`, `tt_min_coords` | Used to build T_drv_mp, T_mp_off, Walk_pax_mp; structural if MPs are fixed. |

So for **Layer A** we need: **shuttle stop generation** (Block 4 logic) → **shuttle VRP** (Block 5) → **structural evaluation** (IOE, etc.) → **structural carpool base** (MPs only; no day-specific matching).

## 1.3 Components That Belong Exclusively to Daily Allocation

These run **on top of the existing network** and use day-specific data.

| Concept | V4 today | Role in Layer B |
|--------|----------|------------------|
| Seat reservation | Sheets table “reservas” (push_reservas); not used inside V4 optimization | **Seat allocator input:** who reserved for day D. |
| Who is “in scope” today | V4 assumes full census in one run | **Allocation input:** employees with reservation for day D (and optionally census for fallback). |
| Assignment to shuttle seats | V4: everyone in final_clusters is “assigned” by route membership | **Seat allocator:** map (employee_id, date) → (route_id, stop_id, seat_index) respecting capacity. |
| Validation | V4 has no explicit validation step | **Validation logic:** arrival window, capacity, no double-booking (daily only). |
| Residual for carpool | V4: carpool_set = not in shuttle + excluded by office | **Daily residual:** employees who reserved but did not get a shuttle seat (overflow) or chose carpool. |
| Carpool matching | V4 Block 6B: greedy match, cheapest insertion, 2-opt, detour validation | **Same algorithm**, but input = **day’s residual** (drivers + pax for day D); network (MPs, cost params) is fixed. |

So for **Layer B** we need: **seat_allocator** (assign reserved employees to fixed routes/stops), **validation** (capacity, windows), **overflow_carpool_engine** (same cost + matching + 2-opt + detour, on daily residual), **allocation_evaluation** (daily KPIs: filled seats, coverage today, avg travel time today).

## 1.4 Clean Separation Map

| Category | Contents | Layer |
|----------|----------|--------|
| **Pure optimization (structural)** | coverage_for_center, greedy_open_stops, medoid, KMeans split, prudent merge, office exclude, Route, Clarke–Wright, backfill, IOE/balance, DBSCAN MPs, MP cluster | A |
| **Pure optimization (allocation)** | Seat assignment to fixed routes (greedy or by cost), carpool greedy matching, cheapest_insertion, 2-opt, detour validation, cost composite (α, β, γ, δ) | B (carpool algo reused; MPs from A) |
| **Infrastructure** | OSMnx (features, graph, nearest_node, path), Google duration, Haversine/tt_min_coords | Used by A for design; by B only for carpool times if not cached |
| **Visualization / I/O** | Folium (all maps), gspread (push_empleados, push_paradas, push_rutas_shuttle, push_carpool, push_reservas) | Outside engines; adapters or reporting |

**Data flow:**

- **Layer A input:** Census (employee list with home/work, carpool attrs), office, constraints.  
- **Layer A output:** Stops (id, coords, label), Routes (route_id, sequence of stop_ids, capacity), optional Structural Carpool Base (MP list, cost params, graph snapshot key).  
- **Layer B input:** Same stops + routes + (optional) MP set; day D; reservations for D (employee_id, date, preferred route/stop or none).  
- **Layer B output:** Seat assignments (employee_id → route_id, stop_id, seat), residual list; carpool matches for residual (driver, pax, MP, order); daily KPIs.

---

# PHASE 2 — V6 CORE ARCHITECTURE (TWO-LAYER)

## 2.1 Directory Layout

```
backend/v6/
├── core/
│   ├── network_design_engine/
│   │   ├── shuttle_stop_engine.py   # stop opening, cluster utils, split, merge, office exclude
│   │   ├── shuttle_vrp_engine.py    # Route, Clarke–Wright, backfill (pure)
│   │   └── structural_evaluation.py # IOE, balance, rutas <20, cost-per-seat (structural)
│   │
│   ├── allocation_engine/
│   │   ├── seat_allocator.py        # assign employees to fixed routes/stops (capacity, policy)
│   │   ├── overflow_carpool_engine.py # same as V4: cost, greedy match, cheapest_insertion, 2-opt, detour
│   │   └── allocation_evaluation.py   # daily KPIs (coverage, avg travel time, cost per seat today)
│   │
│   domain/
│   ├── models.py       # Employee, Stop, Route, StructuralNetwork, SeatAssignment, CarpoolMatch, etc.
│   ├── constraints.py  # All numeric params (stops, VRP, carpool, triggers)
│   └── objective_function.py # Lexicographic: cost_per_seat, coverage, avg_travel_time
│   │
│   infrastructure/
│   ├── osm_adapter.py
│   ├── time_adapter.py
│   └── persistence_adapter.py  # load/save network, reservations (no Sheets inside core)
│   │
│   application/
│   ├── run_network_design.py   # orchestrate Layer A: census → stops → VRP → eval → structural carpool base
│   └── run_daily_allocation.py # orchestrate Layer B: network + reservations → seat_allocator → overflow_carpool → eval
│   │
│   api/   # optional; only for HTTP; no FastAPI in core/domain
│   ├── router.py
│   └── schemas.py
```

## 2.2 Engine Contracts (Pure, No Globals)

**network_design_engine**

- **shuttle_stop_engine**
  - Input: `coordinates_utm: ndarray (N,2)`, `tree: KDTree`, `constraints: ShuttleStopConstraints`
  - Output: `(centers_xy: list, members_list: list[list[int]], unassigned_mask: ndarray)`  
  - No OSM/Google/FastAPI/Sheets. Contains: coverage_for_center, greedy_open_stops, best_medoid, KMeans split, prudent merge, office exclude (receives office_xy and exclude_radius_m).

- **shuttle_vrp_engine**
  - Input: `stops_coords: list[(lat,lng)]`, `stops_demands: list[int]`, `duration_matrix: ndarray (N+1,N+1)`, `office_index: int`, `constraints: VRPConstraints`
  - Output: `(routes: list[Route], unserved_stop_indices: list[int])`  
  - Route = (seq, load, dur). Same Clarke–Wright + backfill logic as V4.

- **structural_evaluation**
  - Input: `routes`, `stops_demands`, `constraints` (BUS_CAPACITY, etc.)
  - Output: `StructuralKPIs` (IOE, balance, rutas_menor_20, media_pax, **cost_per_seat_structural**).

**allocation_engine**

- **seat_allocator**
  - Input: `structural_network: StructuralNetwork` (stops, routes with capacity), `reservations: list[Reservation]` (employee_id, date, optional preferred_route/stop), `constraints`
  - Output: `(assignments: list[SeatAssignment], residual_employee_ids: list[str])`  
  - Policy: e.g. greedy by reservation time or by cost (distance to stop); hard constraint: capacity per route/stop.

- **overflow_carpool_engine**
  - Input: `residual_employees` (with carpool attrs), `structural_carpool_base` (MPs, cost params), `time_matrices` (T_drv_mp, T_mp_off, Walk_pax_mp) or adapter to compute them, `constraints`
  - Output: `(matches: list[CarpoolMatch], driver_summary, unassigned_pax)`  
  - Same as V4: composite cost, greedy matching, cheapest_insertion, 2-opt, detour validation.

- **allocation_evaluation**
  - Input: `assignments`, `carpool_matches`, `structural_network`, `reservations`
  - Output: `AllocationKPIs` (coverage_today, avg_travel_time_today, cost_per_seat_today, operational stability metrics).

**domain**

- **models.py:** Employee, Stop, Route, StructuralNetwork (stops + routes + optional MP list), Reservation, SeatAssignment, CarpoolMatch, StructuralKPIs, AllocationKPIs.
- **constraints.py:** All radii, caps, BUS_CAPACITY, MAX_STOPS, DETOUR_CAP, BACKFILL_MAX_MIN_PER_PAX, CFG_MATCH (α, β, γ, δ, MAX_DETOUR_*, etc.), trigger thresholds.
- **objective_function.py:** Lexicographic comparison and scalar helpers (cost_per_seat, coverage, avg_travel_time).

**infrastructure**

- **osm_adapter:** features_from_point, graph_from_point, nearest_node, shortest_path (no change).
- **time_adapter:** duration_matrix(coords, mode) → 2D array; used by run_network_design and optionally by overflow_carpool (or cached from design).
- **persistence_adapter:** save_network(network), load_network(center_id, version), save_reservations(...), load_reservations(date). No gspread inside; can be implemented with DB or Sheets behind the adapter.

## 2.3 Exact Mapping from V4 to V6 Engines

| V4 component | V6 destination |
|--------------|----------------|
| coverage_for_center, greedy_open_stops | core/network_design_engine/shuttle_stop_engine.py |
| cluster_center_xy, cluster_diameter, best_medoid, too_close | core/network_design_engine/shuttle_stop_engine.py (or cluster_utils submodule) |
| KMeans split, prudent merge, office exclude | core/network_design_engine/shuttle_stop_engine.py |
| final_clusters, carpool_set | Output of shuttle_stop_engine; carpool_set = unassigned + excluded. |
| Route, feasible_merge_with, merge_with, Clarke–Wright, backfill | core/network_design_engine/shuttle_vrp_engine.py |
| Duration matrix build (get_duracion_google loop) | infrastructure/time_adapter.py; called from application/run_network_design.py |
| IOE, balance, rutas &lt;20, media pax | core/network_design_engine/structural_evaluation.py |
| _mps_por_cobertura (DBSCAN MPs, snap, MP cluster) | core/network_design_engine/ (structural carpool base) OR core/allocation_engine/ overflow_carpool_engine with MPs passed in; recommendation: compute MPs in run_network_design and attach to StructuralNetwork / structural_carpool_base. |
| Cost composite (α, β, γ, δ), greedy matching, cheapest_insertion, _two_opt, detour validation | core/allocation_engine/overflow_carpool_engine.py |
| Seat assignment to routes | core/allocation_engine/seat_allocator.py (new logic; V4 has no explicit “reservation → seat” step). |
| push_*, Folium | infrastructure/persistence_adapter.py (or sheets_adapter), reporting outside core. |

---

# PHASE 3 — FORMAL OBJECTIVE AND CONSTRAINTS

## 3.1 Lexicographic Objective (Strategic Priorities)

Order (dominant first):

1. **Minimize CostPerSeat** (dominant)
2. **Maximize Coverage** (fraction of in-scope employees served by shuttle + carpool)
3. **Minimize AverageTravelTime** (over served employees)
4. **Operational stability** (e.g. minimal change in assignments day-over-day; can be soft or constraint)

Definitions:

- **CostPerSeat (structural):** Total operational cost of shuttle network (e.g. route cost × frequency) / total seats offered (sum over routes of capacity). For allocation day: cost of used shuttle + carpool cost / seats_used.
- **Coverage:** (employees with shuttle seat + employees in carpool) / employees in scope (reserved or eligible).
- **AverageTravelTime:** Mean of (travel time from home to office) for all served employees (shuttle: to stop + route time; carpool: to MP + route time).

## 3.2 Hard Constraints

- **Shuttle:** BUS_CAPACITY per vehicle; MAX_STOPS per route; DETOUR_CAP and BACKFILL_MAX_MIN_PER_PAX in backfill; MAX_ROUTE_DURATION.
- **Seat allocator:** No over-capacity per route/stop; each reserved employee at most one seat (shuttle or carpool).
- **Carpool:** MAX_DETOUR_MIN, MAX_DETOUR_RATIO; driver capacity (seats); MAX_WALK_M; no passenger assigned to more than one driver.

## 3.3 Soft Constraints (Penalties in Objective or Secondary Criteria)

- Route balance (avoid very empty or very full routes when possible).
- Preference for arrival window (penalize assignments outside window).
- Operational stability: prefer continuing same route/stop for same employee when possible.

## 3.4 What Triggers Weekly Redesign (Layer A)

Defined in Phase 4 below.

## 3.5 What Remains Daily Only (Layer B)

- Which employees have a reservation for day D.
- Seat assignment (which employee → which route/stop/seat).
- Overflow carpool matching for day D’s residual.
- Daily KPIs and validation (capacity, double-booking checks).

---

# PHASE 4 — TRIGGER LOGIC (WEEKLY REDESIGN)

Trigger conditions (any one can trigger a structural recalculation):

1. **Shuttle occupancy below threshold for X consecutive days**  
   - e.g. IOE_today &lt; IOE_MIN for 3 consecutive days.  
   - Parameters: IOE_MIN, CONSECUTIVE_DAYS.

2. **Coverage drops below threshold**  
   - e.g. coverage_today &lt; COVERAGE_MIN for 2 consecutive days.  
   - Parameters: COVERAGE_MIN, CONSECUTIVE_DAYS_COVERAGE.

3. **Cost per seat increases above Y%**  
   - e.g. cost_per_seat_today &gt; (1 + COST_INCREASE_PCT) × cost_per_seat_baseline.  
   - Baseline = last network design run or rolling average.  
   - Parameters: COST_INCREASE_PCT, baseline reference.

4. **New employees / cluster exceeds structural capacity**  
   - e.g. new employees in a zone with no stop within ASSIGN_RADIUS_M, or total demand &gt; current network capacity (sum of route capacities).  
   - Parameters: ASSIGN_RADIUS_M, capacity margin (e.g. trigger if unserved &gt; UNSERVED_THRESHOLD_PCT).

5. **Explicit admin trigger**  
   - e.g. “recalculate network” button or scheduled weekly job (e.g. every Monday 00:00).

Formalization (pseudo):

- Store: `last_network_design_at`, `structural_baseline_kpis` (IOE, coverage, cost_per_seat).
- Every day after allocation: compute `AllocationKPIs`.
- If (IOE &lt; IOE_MIN for CONSECUTIVE_DAYS) OR (coverage &lt; COVERAGE_MIN for CONSECUTIVE_DAYS_COVERAGE) OR (cost_per_seat &gt; baseline × (1 + COST_INCREASE_PCT)) OR (new_cluster_exceeds_capacity) OR (admin_trigger):  
  - Run `run_network_design`; update `last_network_design_at` and `structural_baseline_kpis`.

All trigger parameters live in **domain/constraints.py** (e.g. TriggerConstraints).

---

# PHASE 5 — SCALABILITY PLAN (5,000 EMPLOYEES, SINGLE CENTER)

1. **What must be cached**  
   - Duration matrix for shuttle (stops + office). Key: (center_id, network_version or stop_set_hash). Invalidate when network is redesigned.  
   - OSM graph G (shuttle and carpool) by (center_id, radius_km).  
   - Travel times for carpool: T_drv_mp, T_mp_off, Walk_pax_mp can be cached by (center_id, MP_set_hash, driver/pax set hash) if MPs and employee locations are stable; otherwise recompute or partial update.

2. **What must be precomputed**  
   - In **run_network_design:** duration matrix, structural MPs, and optionally precomputed carpool time matrices for a “reference” residual set (e.g. last week’s carpool_set) so that Layer B can reuse or interpolate.  
   - Structural evaluation (IOE, cost_per_seat) at design time.

3. **What must run in batch**  
   - **Full network design (Layer A):** Always batch (nightly or on trigger).  
   - Duration matrix fill: batch (parallel or batched API calls).  
   - Carpool MPs and, if needed, full carpool matrices for a large residual set: batch.

4. **What must remain fast**  
   - **run_daily_allocation:** Seat allocator = O(R × S × log N) or similar (assign N reservations to R routes with S stops).  
   - Overflow carpool: greedy matching + 2-opt per driver; keep K_MP_PAX and MAX_DRIVERS_PER_MP bounded so that candidate set is small. Target: allocation + carpool &lt; 30 s for 5k employees (most on shuttle, residual ~1–2k).

5. **Where OR-Tools could be optionally integrated**  
   - **Shuttle VRP (Layer A):** Optional OR-Tools CVRP (or open VRP) when number of stops or routes is large (e.g. S &gt; 80) for better quality; keep Clarke–Wright as default.  
   - **Carpool matching (Layer B):** Optional OR-Tools assignment/MIP for global optimal matching on small residual sets (e.g. &lt; 500 pax); keep greedy as default.

6. **Preventing combinatorial explosion in carpool**  
   - Same as before: K_MP_PAX (e.g. 5), MAX_DRIVERS_PER_MP (e.g. 40); greedy assignment; early reject by MAX_WALK_M, MAX_DETOUR_*; cap M (MPs) via DBSCAN params.  
   - Structural MPs fixed at design time so that Layer B does not recompute MPs; only matches pax to drivers using existing MPs.

7. **Parallelization**  
   - Duration matrix: parallel over (i,j) or rows (respecting API limits).  
   - Carpool T_drv_mp, Walk_pax_mp: parallel over drivers / pax.  
   - 2-opt: one job per driver (independent).  
   - Clarke–Wright: parallelize the “best (a,b)” evaluation in each merge round.

---

# DELIVERABLES SUMMARY

## 1. Full V6 Definitive Architecture (Two-Layer)

- **Layer A — NetworkDesignEngine (batch, weekly or on trigger):**  
  shuttle_stop_engine → shuttle_vrp_engine → structural_evaluation; optional structural carpool base (MPs).  
  Output: StructuralNetwork (stops, routes, MPs, baseline KPIs).

- **Layer B — AllocationEngine (daily, 48h before):**  
  seat_allocator (on fixed network + reservations) → overflow_carpool_engine (on residual) → allocation_evaluation.  
  No structural change; only assignments and daily carpool matching.

## 2. Exact Mapping V4 → V6 Engines

(See table in Phase 2.3.)

## 3. Objective Function Formal Definition

- Lexicographic: (1) Minimize CostPerSeat, (2) Maximize Coverage, (3) Minimize AverageTravelTime, (4) Operational stability.  
- Hard/soft constraints as in Phase 3.  
- **domain/objective_function.py** implements comparison and scalar metrics.

## 4. Weekly Redesign Trigger Logic

- Four automatic conditions (IOE, coverage, cost increase, new cluster/capacity) + admin/scheduled trigger.  
- All parameters in constraints; logic in application or a small “trigger_evaluator” module that reads AllocationKPIs and baseline.

## 5. Scalability Blueprint

- Cache: duration matrix, OSM graph, carpool time matrices (by network/MP set).  
- Precompute: at design time, full matrix and MPs.  
- Batch: Layer A and heavy matrix builds.  
- Fast path: Layer B seat allocator + carpool matching with bounded candidates.  
- OR-Tools: optional for VRP and carpool assignment.  
- Parallel: matrix fill, 2-opt, CW round evaluation.

## 6. Risks and Mitigation

| Risk | Mitigation |
|------|------------|
| Layer B assumes fixed network; versioning | Persist StructuralNetwork with version/valid_from; allocation always references a version. |
| Reservation schema vs V4 | Define Reservation (employee_id, date, preferred_route/stop optional); persistence_adapter hides Sheets/DB. |
| Carpool MPs from Layer A vs day-specific residual | Compute MPs at design time on “design residual” (carpool_set); Layer B uses same MPs for any day’s residual. If geography shifts, trigger redesign. |
| Cost-per-seat baseline drift | Store baseline at last design; trigger when current &gt; baseline × (1 + pct). |
| 5k employees, 2k residual carpool | Cache matrices; greedy + 2-opt; optional OR-Tools for subproblems. |
| No regression vs V4 | Regression tests: same seed and census → same stops, same routes_idx, same IOE (tolerance); same residual → same carpool match count (tolerance). |

## 7. Implementation Roadmap (Phased)

- **Phase 1 — Domain and constraints:** models.py (Employee, Stop, Route, StructuralNetwork, Reservation, SeatAssignment, CarpoolMatch, KPIs), constraints.py (all params including triggers), objective_function.py (lexicographic + scalars).  
- **Phase 2 — Layer A core:** shuttle_stop_engine (migrate V4 Block 4), shuttle_vrp_engine (Route, CW, backfill), structural_evaluation; time_adapter, osm_adapter; run_network_design (census → stops → VRP → eval → structural carpool base).  
- **Phase 3 — Structural carpool base:** Compute MPs in run_network_design; attach to StructuralNetwork; persistence_adapter save/load network.  
- **Phase 4 — Layer B core:** seat_allocator (policy: e.g. greedy by distance to stop or by reservation order), overflow_carpool_engine (cost, matching, insertion, 2-opt, detour), allocation_evaluation; run_daily_allocation (load network + reservations → seat_allocator → overflow_carpool → eval).  
- **Phase 5 — Triggers and integration:** Trigger evaluator (read KPIs + baseline, recommend redesign); persistence for reservations and baseline; optional API (run_network_design batch, run_daily_allocation 48h before).  
- **Phase 6 — Scale and optional OR-Tools:** Caching, parallelization, optional OR-Tools VRP and carpool; regression tests vs V4.

---

# CRITICAL QUESTIONS BEFORE IMPLEMENTATION

1. **Reservation schema:** For day D, what exact fields does a “reservation” have? (e.g. employee_id, date, preferred_route_id or preferred_stop_id, arrival_window_override?) This defines the seat_allocator input contract.

2. **Seat allocator policy:** When there are more reservations than seats on a route, how do we choose who gets a seat? (First-come-first-served by reservation time? Minimize total travel time? Prefer employees with no carpool option?) This determines the objective inside Layer B.

3. **Structural carpool base scope:** Should we compute meeting points once per design using the **design-time carpool_set**, and reuse those MPs for every day’s residual? Or do we allow “MP refresh” on a different schedule (e.g. monthly) without full shuttle redesign?

4. **Baseline for cost-per-seat trigger:** Is the baseline the **structural** cost_per_seat from the last run_network_design, or a **rolling average of daily** cost_per_seat over the last N days? This fixes the trigger formula.

5. **Versioning and cutover:** When a new network is produced (after trigger or scheduled run), do we switch immediately for the next allocation, or is there a “valid_from” date (e.g. next Monday)? This affects persistence and run_daily_allocation.

Once these five points are decided, implementation can proceed without ambiguity.
