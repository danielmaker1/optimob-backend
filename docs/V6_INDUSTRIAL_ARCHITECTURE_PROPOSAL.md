# V6 Industrial Planning Engine — Full Architectural Proposal

**Document:** Dissection of V4, Industrial V6 Architecture, Migration Map, Scalability, Improvements  
**Constraints:** No simplification of algorithms. Preserve 100% of V4 algorithmic intelligence. Industrialize via modularization and dependency isolation.

---

# PHASE 1 — COMPLETE DISSECTION OF V4

## 1.1 Logical Pipeline Flow

```
Input (config + seed)
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 1. EMPLOYEE GENERATION                                                       │
│    OSM residential sampling (ox.features_from_point → buildings + landuse)   │
│    → union_residencial → random points with contains() → empleados_data      │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 2. EMPLOYEE ENRICHMENT (3B)                                                  │
│    has_car, open_carpool, seats (rng) → df_empleados / empleados_data        │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 3. SHUTTLE STOP OPENING & CLEANING (Block 4)                                 │
│    latlon → GeoDataFrame UTM → KDTree(X)                                     │
│    → greedy_open_stops(ASSIGN_RADIUS_M, MAX_CLUSTER, unassigned)            │
│    → best_medoid refinement → pair radius reabsorption                      │
│    → KMeans split if len > MAX_OK → prudent merge (FUSION_RADIUS, DIAMETER)  │
│    → office exclusion (EXCLUDE_RADIUS_M) → final_clusters, carpool_set       │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 4. SHUTTLE VRP (Block 5)                                                     │
│    final_clusters → stops_coords, stops_demands                               │
│    → OSM graph G (ox.graph_from_point, add_edge_speeds, travel_times)         │
│    → Duration matrix D (Google API or OSMnx fallback) N×N                    │
│    → Route class (seq, load, dur, feasible_merge_with, merge_with)           │
│    → Clarke–Wright open (savings, capacity, MAX_STOPS, DETOUR_CAP)           │
│    → Small route absorption → BACKFILL (delta_min_per_pax ≤ BACKFILL_MAX)    │
│    → routes_idx, empleados_fuera (from stops_out_idx)                         │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 5. EVALUATION (Shuttle)                                                      │
│    IOE = 100 * sum(emp_ruta) / (BUS_CAPACITY * len(emp_ruta))                │
│    Balance max/min pax, rutas <20 pax, media pax por ruta                     │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 6. CARPOOL PREP (6A)                                                         │
│    df_carpool from df_empleados + carpool_set (empleados_no_shuttle_ids)     │
│    G_CARPOOL = ox.graph_from_point (drive) for routing                        │
│    nearest_node, tt_min_coords, walk_dist_m                                    │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 7. CARPOOL MATCH (6B)                                                        │
│    DBSCAN on (lat,lon) → meeting points → snap to G → MP cluster (DBSCAN)    │
│    T_drv_mp, T_mp_off, T_drv_off, Walk_pax_mp (matrices)                     │
│    Cost = alpha*walk + beta*detour + gamma*|ETA - hora_obj| - DELTA*n_pax     │
│    Greedy matching (best cost, MAX_DETOUR_MIN/RATIO)                          │
│    Per driver: cheapest_insertion_order → _two_opt → detour validation        │
│    → df_matches, df_driver_summary, df_routes                                 │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 8. KPIs & OUTPUT                                                             │
│    conductores_con_pax, pasajeros_asignados, etc.                             │
│    push_empleados, push_paradas, push_rutas_shuttle, push_carpool (Sheets)    │
│    Folium maps (shuttle stops, carpool, routes)                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 1.2 Logical Architecture Diagram (Text)

```
                    ┌──────────────────────────────────────────────────┐
                    │                 CONFIG / GLOBALS                  │
                    │  NUM_EMPLEADOS, SEED, COORDENADAS_OFICINA,        │
                    │  ASSIGN_RADIUS_M, MAX_CLUSTER, MIN_SHUTTLE,       │
                    │  BUS_CAPACITY, MAX_STOPS, DETOUR_CAP, CFG_MATCH   │
                    └─────────────────────┬────────────────────────────┘
                                          │
    ┌────────────────────────────────────┼────────────────────────────────────┐
    │                                    ▼                                      │
    │  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
    │  │ OSM Adapter │───▶│  Employee   │───▶│  Enrichment │───▶│   Shuttle   │
    │  │ (residential│    │  Generator  │    │  (carpool   │    │   Engine    │
    │  │  sampling)  │    │  (points)   │    │   attrs)     │    │ (stops+VRP) │
    │  └─────────────┘    └─────────────┘    └─────────────┘    └──────┬──────┘
    │         │                  │                  │                  │
    │         ▼                  ▼                  ▼                  ▼
    │  [ox.features_*]    [random+contains]   [rng]            [greedy_open,
    │  [geopandas]                                                            │
    │                                                                  KMeans,
    │                                                                  merge,
    │                                                                  office]
    │                                                                  │
    │                                                                  ▼
    │  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────────────┐
    │  │ Time/Dist   │◀───│  Duration   │    │  Clarke–Wright + Backfill    │
    │  │ Adapter     │    │  Matrix D   │    │  Route.feasible_merge_with   │
    │  │ (Google/OSM)│    │  (N×N)      │    │  Route.merge_with            │
    │  └─────────────┘    └─────────────┘    └──────────────┬──────────────┘
    │         │                                              │
    │         │                  ┌───────────────────────────┘
    │         │                  ▼
    │         │           ┌─────────────┐    ┌─────────────┐
    │         └──────────▶│  Evaluation │    │  Residual   │
    │                     │  (IOE, etc) │    │  carpool_set│
    │                     └─────────────┘    └──────┬──────┘
    │                                                │
    │                                                ▼
    │                     ┌──────────────────────────────────────────────────┐
    │                     │  Carpool Engine                                    │
    │                     │  DBSCAN MPs → snap → MP cluster                    │
    │                     │  T_drv_mp, T_mp_off, Walk_pax_mp                   │
    │                     │  Cost = α*walk + β*detour + γ*ETA_off - δ*n_pax   │
    │                     │  Greedy match → cheapest_insertion → 2-opt       │
    │                     │  Detour validation (MAX_DETOUR_MIN/RATIO)         │
    │                     └──────────────────────┬───────────────────────────┘
    │                                              │
    └─────────────────────────────────────────────┼─────────────────────────────┘
                                                  ▼
                    ┌──────────────────────────────────────────────────┐
                    │  KPIs / Output                                     │
                    │  (Sheets push, Folium maps = adapters)            │
                    └──────────────────────────────────────────────────┘
```

## 1.3 Functions/Modules to Migrate Intact (Algorithmic Core)

| Component | Location (V4 notebook) | Description |
|-----------|------------------------|-------------|
| `coverage_for_center` | Block 4 | Radius + cap coverage from KDTree; must stay identical. |
| `greedy_open_stops` | Block 4 | Greedy stop opening with unassigned mask; core of shuttle stop generation. |
| `too_close`, `best_medoid` | Block 4 | Medoid refinement and separation. |
| `cluster_center_xy`, `cluster_diameter` | Block 4 | Cluster geometry; diameter used in merge constraint. |
| KMeans split loop | Block 4 | Split oversized clusters into k subclusters (MIN_OK, MAX_OK). |
| Prudent merge loop | Block 4 | FUSION_RADIUS + DIAMETER_MAX_M; merge without exceeding MAX_OK. |
| Office exclusion | Block 4 | EXCLUDE_RADIUS_M; add excluded employees to carpool_set. |
| `Route` class | Block 5 | _calc_duration, feasible_merge_with (capacity, MAX_STOPS, DETOUR_CAP), merge_with. |
| Clarke–Wright open loop | Block 5 | Savings-based merge, best (saving, new_load). |
| Small-route absorption | Block 5 | Merge routes below MIN_EMP_SHUTTLE into larger routes. |
| Backfill loop | Block 5 | Pending stops, delta_min_per_pax ≤ BACKFILL_MAX_MIN_PER_PAX, DETOUR_CAP. |
| `duration_google` / fallback chain | Block 5 | Google → OSMnx → euclidean; must be behind adapter. |
| `_mps_por_cobertura` (DBSCAN MPs) | 6B | DBSCAN on (lat,lon), centroid, snap to graph; then MP cluster DBSCAN. |
| Cost composite (alpha, beta, gamma, DELTA) | 6B | Same formula: walk + detour + ETA penalty − occupancy bonus. |
| Greedy matching with detour filter | 6B | MAX_DETOUR_MIN, MAX_DETOUR_RATIO per candidate. |
| `_cheapest_insertion_order` | 6B | Order MPs for driver. |
| `_two_opt` | 6B | 2-opt on route order (iters=200). |
| Route-level detour validation | 6B | Reject route if detour_min or detour_ratio exceeds limit. |
| IOE and evaluation metrics | Post-VRP | 100*sum(emp_ruta)/(BUS_CAPACITY*len(emp_ruta)); balance, rutas <20. |
| `tt_min_coords` (Haversine time) | 6B | Geodetic time for matrices when not using graph. |

## 1.4 Global Parameters to Centralize

| Category | Parameters |
|----------|------------|
| **Scene** | NUM_EMPLEADOS, SEED, COORDENADAS_OFICINA, ZOOM_MAPA |
| **Shuttle stops** | ASSIGN_RADIUS_M, MAX_CLUSTER, MIN_SHUTTLE, MIN_STOP_SEP_M, FALLBACK_MIN, FALLBACK_SEP_M, PAIR_RADIUS_M, MIN_OK, MAX_OK, FUSION_RADIUS, DIAMETER_MAX_M, EXCLUDE_RADIUS_M |
| **VRP** | BUS_CAPACITY, MAX_STOPS, MAX_ROUTE_DURATION, MIN_EMP_SHUTTLE, SAFETY_BUFFER_KM, DETOUR_CAP, BACKFILL_MAX_MIN_PER_PAX |
| **Carpool** | CFG_MATCH (DBSCAN_EPS_M, DBSCAN_MIN_SAMPLES, MP_CLUSTER_EPS_M, MAX_WALK_M, K_MP_PAX, MAX_DETOUR_MIN, MAX_DETOUR_RATIO, ALPHA_WALK, BETA_DETOUR, GAMMA_ETA_OFF, DELTA_OCCUPANCY_BONUS, MAX_DRIVERS_PER_MP, MIN_PASSENGERS_PER_DRIVER, DO_2OPT) |
| **External** | API_KEY, USAR_API_GOOGLE_PARA_DURACION, MODO_DEBUG |
| **OSM sampling** | R_KM_MUESTREO (or equivalent), tags_buildings, tags_residential |

All of these must live in a single **domain/constraints.py** or **config** layer injectable per run (single-tenant) or per tenant (multi-tenant).

## 1.5 Fragile Couplings

| Coupling | Risk |
|----------|------|
| **empleados_data** is list of dicts; Block 4 uses index into this list; later blocks use **carpool_set** as set of indices. | Any change to ordering or structure of employees breaks shuttle↔carpool residual handoff. |
| **final_clusters** and **df_paradas_final** are built in Block 4; Block 5 uses **final_clusters** by name and index (stops_coords, stops_demands). | VRP assumes cluster index i maps to same stop everywhere; reordering or filtering must be explicit. |
| **G** (OSM graph) is built in Block 5 for shuttle; **G_CARPOOL** / **G** in 6A for carpool. 6B assumes **G** and **nearest_node** in scope. | Two graphs (shuttle vs carpool radius); must be clearly separated and passed explicitly. |
| **df_carpool** from 6A must have columns: id, lat, lon, office_lat, office_lon, has_car, seats_driver, open_carpool, hora_obj, rol. | 6B reads these by name; schema must be stable. |
| **get_duracion_google** is global; Block 5 duration matrix loop calls it. | Any refactor must keep the same call signature and fallback order (Google → OSMnx → euclidean). |
| **COORDENADAS_OFICINA** and **OFFICE** used in multiple blocks. | Single-office assumption; multi-center requires office_id or list of offices. |

## 1.6 Computational Bottlenecks

| Location | Operation | Cost |
|----------|-----------|------|
| Block 4 | `greedy_open_stops`: for each unassigned i, `coverage_for_center` → KDTree.query_radius | O(N × (neighbors in radius)) per round; multiple rounds until no progress. |
| Block 4 | `cluster_diameter(idx_list)` for large clusters | O(n²) in cluster size when len ≤ 400; else bbox. |
| Block 4 | Prudent merge: pairwise distance between cluster centers | O(K²) with K = number of clusters. |
| Block 5 | Duration matrix D | O(N²) Google or OSMnx calls (N = S+1). |
| Block 5 | Clarke–Wright: while merged, pairwise route merge feasibility | O(R²) per round with R = routes. |
| Block 5 | Backfill: for each pending stop, over all routes | O(P × R) with feasibility and duration recompute. |
| 6B | T_drv_mp, T_mp_off, Walk_pax_mp | O(D×M), O(M), O(P×M) with D drivers, P pax, M MPs. |
| 6B | Greedy matching (candidates per pax, then per driver) | Depends on K_MP_PAX and MAX_DRIVERS_PER_MP; inner cost evaluation. |
| 6B | _two_opt per driver | O(iters × L²) per route length L. |

---

# PHASE 2 — INDUSTRIAL V6 ARCHITECTURE

## 2.1 Target Layout

```
backend/v6/
├── core/
│   ├── shuttle_engine/
│   │   ├── stop_opening.py    # greedy_open_stops, coverage_for_center, medoid, split, merge
│   │   ├── cluster_utils.py   # cluster_center_xy, cluster_diameter, best_medoid
│   │   └── vrp_open.py        # Route, Clarke–Wright, backfill (pure in/out)
│   ├── vrp_engine/
│   │   ├── duration.py        # duration matrix builder (calls adapter interface)
│   │   └── route_model.py     # Route class, feasibility, merge
│   ├── carpool_engine/
│   │   ├── meeting_points.py  # DBSCAN MPs, snap, MP cluster
│   │   ├── cost.py            # composite cost (walk, detour, ETA, occupancy)
│   │   ├── matching.py        # greedy matching with detour filter
│   │   └── routing.py         # cheapest_insertion, two_opt, route detour validation
│   └── evaluation_engine/
│       ├── shuttle_kpis.py    # IOE, balance, rutas <20, media pax
│       └── carpool_kpis.py    # conductores_con_pax, pasajeros_asignados, etc.
├── domain/
│   ├── models.py              # Employee, Stop, Route, MeetingPoint, Match (dataclasses)
│   ├── constraints.py         # All numeric/radius params (single source of truth)
│   └── scoring.py             # Scoring constants (alpha, beta, gamma, delta) if not in constraints
├── infrastructure/
│   ├── osm_adapter.py         # OSMnx: features_from_point, graph_from_point, nearest_nodes, path
│   ├── time_adapter.py        # get_duration(o, d, mode) → Google or OSM or euclidean
│   ├── population_adapter.py  # load_employees: raw → list[Employee] (or OSM sampling behind interface)
│   └── sheets_adapter.py    # push_* (optional; can be no-op in engine)
├── application/
│   ├── plan_population.py     # Orchestrates: load → shuttle stops → VRP → eval → residual → carpool → KPIs
│   └── run_config.py         # Injects constraints + adapters per run
└── api/
    ├── router.py
    └── schemas.py
```

Engines receive **pure inputs** (lists/dicts of domain objects or arrays) and return **pure outputs** (no FastAPI, no gspread, no folium). All I/O and visualization live behind adapters.

## 2.2 Engine Contracts (Pure)

- **shuttle_engine.stop_opening:**  
  `(coordinates_utm, tree, constraints) → (centers_xy, members_list, unassigned_mask)`  
  No OSM, no Google, no Folium.

- **shuttle_engine.vrp_open:**  
  `(stops_coords, stops_demands, duration_matrix, office_index, constraints) → (routes, unserved_stop_indices)`  
  Duration matrix is provided by caller (built via time_adapter).

- **carpool_engine.meeting_points:**  
  `(df_pax_latlon, constraints) → df_meeting_points`  
  Snap to graph can be done via **infrastructure** (graph passed in or adapter that returns snapped coords).

- **carpool_engine.matching:**  
  `(drivers, pax, meeting_points, T_drv_mp, T_mp_off, Walk_pax_mp, constraints) → (matches, driver_summary)`  
  Matrices built outside using time_adapter / graph_adapter.

- **carpool_engine.routing:**  
  `(driver, assigned_pax, MPs, times_src_to_mp, times_mp_to_off, times_mp_mp, constraints) → (order_mp, detour_ok)`  
  Cheapest insertion + 2-opt; detour validation.

- **evaluation_engine.shuttle_kpis:**  
  `(routes, demands, BUS_CAPACITY) → {IOE, balance, rutas_menor_20, media_pax}`.

## 2.3 Adapters (Encapsulate Externals)

- **osm_adapter:**  
  - `features_from_point(center, tags, dist_m)` → GeoDataFrame  
  - `graph_from_point(center, dist_m)` → G with speeds/travel_times  
  - `nearest_node(G, lat, lon)`, `shortest_path(G, o, d, weight)`, `path_coords(G, path)`  
  All OSMnx and NetworkX calls only here.

- **time_adapter:**  
  - `duration_matrix(coords_list, mode, api_key?)` → 2D array  
  Internal: try Google, then OSMnx from graph, then euclidean. Same logic as V4 get_duracion_google + loop.

- **population_adapter:**  
  - `generate_employees(count, center, radius_km, seed)` → list[Employee]  
  Uses OSM adapter to get residential areas, then random points with contains().  
  Or `load_employees(raw_list)` for API-provided population.

- **sheets_adapter (optional):**  
  - `push_empleados(data)`, `push_paradas(data)`, `push_rutas_shuttle(data)`, `push_carpool(data)`  
  No engine calls these; application layer can call after plan is built.

## 2.4 No FastAPI in Domain/Core

- **domain/** and **core/** must not import FastAPI or Pydantic.
- **api/** imports application layer and schemas; application returns domain or DTOs; router serializes to Pydantic response.

## 2.5 Multi-Center and Multi-Tenant Readiness

- **constraints** per run (or per tenant): e.g. `ShuttleConstraints(office_lat, office_lon, assign_radius_m=1000, ...)`.
- **plan_population** accepts `center_id` or `office` and a **constraints** object; engines receive everything they need in the call (no global COORDENADAS_OFICINA).
- **Adapters** can be keyed by tenant/center for graph cache or API keys.

---

# PHASE 3 — SCALABILITY ANALYSIS

## 3.1 O(n²) and High-Cost Parts

| Part | Complexity | Notes |
|------|------------|--------|
| Duration matrix (shuttle) | O(N²) N = S+1 | N² duration lookups (Google/OSM). |
| Clarke–Wright merge loop | O(R²) per round | R = number of routes; multiple rounds. |
| Backfill | O(P × R) | P = pending stops, R = routes. |
| cluster_diameter (large cluster) | O(n²) n = cluster size | V4 caps with bbox for n>400. |
| Carpool T_drv_mp, Walk_pax_mp | O(D×M), O(P×M) | D drivers, P pax, M MPs. |
| Greedy carpool matching | O(P × K × D_cand) | K = K_MP_PAX, D_cand = drivers per MP. |
| 2-opt per driver | O(iters × L²) | L = number of MPs in route. |

## 3.2 What Breaks at 5,000 Employees

- **Shuttle:**  
  - N² duration matrix: 5k stops is unrealistic (stops are clusters, so S is smaller). For 5k employees, S might be 100–300 stops → 30k–90k duration calls. Acceptable if batched/cached.  
  - Greedy open: O(N) per round with radius query; many rounds. With 5k points, KDTree is fine; main cost is number of rounds.  
  - KMeans and merge: K cluster count stays manageable.

- **Carpool:**  
  - D and P can be 1000–2500 each (residual). D×M and P×M with M ≈ 50–200 → 50k–500k matrix cells; precompute with vectorized or parallel loops.  
  - Greedy matching: if every pax has 5 MPs and 40 drivers per MP, cost is manageable; but if “best cost” search is naive, it can be heavy.  
  - 2-opt: per driver, L small (e.g. 5–15 MPs) → fine.

- **OSM graph:**  
  - graph_from_point(center, dist) with large dist (e.g. 50 km) → 100k+ nodes. Build once per center and cache; avoid rebuilding per request.

- **Memory:**  
  - 5k employees × (coordinates + attributes) is small. Matrices D×M, P×M are the main memory; 2k×200 ≈ 400k floats → acceptable.

## 3.3 Where to Cache Aggressively

- **Duration matrix (shuttle):** Cache by (origin_key, dest_key) or by grid cell. Invalidate by TTL or when office/stops change.
- **Travel times (carpool):** Same: (lat,lon) → node, node→node travel time. Use in-memory or Redis with key (center_id, o_node, d_node).
- **OSM graph per center:** Cache G (and G_carpool) by (center_lat, center_lon, radius_km). One graph per center/radius.
- **Meeting points:** Cache DBSCAN result by (center_id, residual_employee_ids_hash) if population is stable day-over-day.

## 3.4 Where to Parallelize

- **Duration matrix fill:** Parallelize over (i,j) or over rows; each cell independent. Watch API rate limits (Google).
- **Walk_pax_mp / T_drv_mp:** Parallelize over p or d (per row/column).
- **2-opt:** Per-driver 2-opt is independent; run drivers in parallel.
- **Clarke–Wright:** Merge loop is sequential by nature; parallelize only the “best (a,b)” search in each round (evaluate all (a,b) in parallel).

## 3.5 Where to Introduce OR-Tools

- **VRP (shuttle):** Replace or complement Clarke–Wright + backfill with OR-Tools CVRP (or open VRP with end at office). Use when S or R is large (e.g. S > 50) or when exact/approximate MIP is acceptable. Keep Clarke–Wright as fast heuristic option.
- **Carpool matching:** Can be formulated as assignment or set-cover; OR-Tools CP-SAT or MIP for “best global assignment” instead of greedy. Introduce as optional path for smaller instances or when quality matters more than latency.

## 3.6 Where NumPy Vectorization Replaces Loops

- **Duration matrix:** Already a double loop; keep for clarity or replace with one adapter that returns full matrix (vectorized inside adapter if using a batch API).
- **Walk_pax_mp, T_drv_mp:** Replace double loops with broadcast: (P,1) vs (1,M) for distances; same for (D,M). Use Haversine vectorized over arrays.
- **cluster_diameter:** For clusters with n ≤ 400, avoid n² Python loop; use (pts[:,None,:] - pts[None,:,:]) and norm; for n > 400 keep bbox approximation.
- **Cost composite in carpool:** One 2D array for walk, one for detour, one for ETA; combine with alpha, beta, gamma, delta in one expression.

## 3.7 Preventing Combinatorial Explosion in Carpool Matching

- **Limit candidates:** K_MP_PAX (e.g. 5) MPs per pax; MAX_DRIVERS_PER_MP (e.g. 40) drivers per MP. So each pax has at most 5×40 = 200 (driver, MP) options.
- **Greedy, not full assignment:** Assign one pax at a time to best (driver, MP) and mark driver capacity / route; no global MIP unless explicitly opted in.
- **Early reject:** Filter by MAX_WALK_M, MAX_DETOUR_MIN, MAX_DETOUR_RATIO before cost sort; reduces list size.
- **Cap MPs:** DBSCAN + MP cluster keeps M in the tens to low hundreds.

---

# PHASE 4 — IMPROVEMENTS OVER V4 (WITHOUT SIMPLIFICATION)

## 4.1 Stop Opening Criteria

- **Current:** Greedy by coverage count (gain = len(take)), min_threshold, min_sep.
- **Improvement:** Add a **quality score** per candidate stop: e.g. coverage × (1 − dispersion/radius) or coverage / (1 + mean_walk_to_stop). Open stops by **score** instead of raw count so compact stops are preferred. Keep same greedy structure and radius/cap constraints.

## 4.2 Multi-Objective Scoring

- **Current:** Clarke–Wright uses saving; backfill uses (delta_min_per_pax, -demand, -load). Evaluation reports IOE, balance, rutas <20.
- **Improvement:** Explicit **multi-objective** in backfill: e.g. lexicographic (1) delta_min_per_pax ≤ cap, (2) maximize demand, (3) minimize imbalance vs mean load. Or scalarize: score = -delta_min_per_pax + w1*demand + w2*(1/|load - target|). Keep DETOUR_CAP and BACKFILL_MAX_MIN_PER_PAX as hard constraints.

## 4.3 Backfill Logic

- **Current:** One pass per pending stop; first feasible insertion wins (by key).
- **Improvement:** **Multi-pass backfill:** after a full pass, recompute “pending” and run again so that newly filled routes can make new insertions feasible. Cap passes (e.g. 3) to avoid long runs. Optionally **best insertion** over all (route, position) for each stop (cost = delta_time or delta_per_pax) instead of first feasible.

## 4.4 Dynamic Detour Penalties

- **Current:** Fixed MAX_DETOUR_MIN, MAX_DETOUR_RATIO; fixed DETOUR_CAP in VRP.
- **Improvement:** **Tiered detour:** e.g. 0–10 min detour → no penalty; 10–20 min → soft penalty in cost; > 20 min → hard reject. Or **time-of-day** multiplier (e.g. peak vs off-peak) so same detour is penalized more in peak. Carpool cost formula keeps beta*detour but beta can depend on time band or detour band.

## 4.5 Cost-per-Seat Optimization

- **Current:** IOE and occupancy bonus (DELTA) favor full cars.
- **Improvement:** In evaluation and in carpool matching, add **cost per seat** (e.g. total_route_cost / seats_used). Prefer routes with lower cost per seat when occupancy is equal. In matching, subtract a **cost_per_seat** term from the composite cost so that drivers with lower cost per seat are preferred. No removal of 2-opt or Clarke–Wright; this is an extra term in scoring.

---

# DELIVERABLE SUMMARY

## 1. Full Architectural Proposal

- **V6 layout:** core (shuttle_engine, vrp_engine, carpool_engine, evaluation_engine), domain (models, constraints, scoring), infrastructure (osm, time, population, sheets adapters), application (plan_population, run_config), api (router, schemas).
- **Engines:** Pure in/out; no FastAPI, no Google, no Folium inside.
- **Adapters:** Isolate OSMnx, Google, gspread, Folium; injectable per run/tenant.

## 2. Detailed Migration Map (V4 → V6)

| V4 Block / Concept | V6 Destination | Notes |
|--------------------|----------------|-------|
| Config / globals | domain/constraints.py + run_config | Single source; injectable. |
| OSM residential + random points | infrastructure/population_adapter.py | Uses osm_adapter for features. |
| Enrichment (has_car, seats, open_carpool) | application or domain | Pure function (rng or deterministic). |
| coverage_for_center, greedy_open_stops | core/shuttle_engine/stop_opening.py | Same logic; take tree + constraints. |
| cluster_center_xy, cluster_diameter, best_medoid | core/shuttle_engine/cluster_utils.py | Unchanged. |
| KMeans split, merge, office exclude | core/shuttle_engine/stop_opening.py | Same formulas. |
| get_duracion_google + matrix loop | infrastructure/time_adapter.py + application | Matrix built in application using adapter. |
| Route, Clarke–Wright, backfill | core/shuttle_engine/vrp_open.py (or vrp_engine) | Pure; receive D, return routes. |
| IOE, balance, rutas <20 | core/evaluation_engine/shuttle_kpis.py | Pure. |
| df_carpool, G_CARPOOL, nearest_node, tt_min_coords | application builds; carpool_engine uses passed matrices | Graph from osm_adapter; times from time_adapter or Haversine. |
| _mps_por_cobertura | core/carpool_engine/meeting_points.py | DBSCAN + snap; snap via adapter. |
| Cost composite, greedy matching | core/carpool_engine/cost.py, matching.py | Same formula; matrices in. |
| cheapest_insertion, _two_opt | core/carpool_engine/routing.py | Unchanged. |
| Detour validation | core/carpool_engine/routing.py | Unchanged. |
| push_* | infrastructure/sheets_adapter.py | Optional; called from application. |
| Folium maps | Not in engine; optional reporting service | Consume plan output and render elsewhere. |

## 3. Technical Risk Assessment

| Risk | Mitigation |
|------|------------|
| V4 notebook state order (cell execution) | Migration must run in a single deterministic flow in plan_population; no implicit globals. |
| Graph and node IDs differ between shuttle/carpool | Separate G_shuttle and G_carpool; pass explicitly; document which graph is used where. |
| Google quota at 5k scale | Prefer OSMnx or cached matrix; use Google only for critical samples or fallback. |
| Regression in KPIs | Keep V4 and V6 outputs comparable; add regression tests (same seed → same IOE, same match count within tolerance). |
| Multi-center data mixing | Constraints and graph keyed by center_id; no shared global office. |

## 4. Phased Implementation Roadmap

- **Phase A (Foundation):** domain/models.py, domain/constraints.py, infrastructure/population_adapter (load_employees only), infrastructure/time_adapter (duration matrix), no OSM yet.
- **Phase B (Shuttle):** core/shuttle_engine (stop_opening, cluster_utils), core/vrp_engine (Route, Clarke–Wright, backfill), application calls shuttle path with mock or simple duration (Haversine).
- **Phase C (Shuttle + OSM):** infrastructure/osm_adapter; plug into time_adapter and graph for VRP; evaluation_engine shuttle KPIs.
- **Phase D (Carpool):** core/carpool_engine (meeting_points, cost, matching, routing); application residual → carpool; carpool KPIs.
- **Phase E (Integrity):** Regression tests vs V4 notebook (frozen outputs); parameterize constraints; optional OR-Tools VRP path.
- **Phase F (Multi-center / SaaS):** Per-tenant constraints and adapter config; cache graphs and matrices by center.

## 5. Justification for Key Decisions

- **Engines pure:** Testability (no mocks of HTTP or DB in unit tests), deterministic runs, reuse in batch or serverless.
- **Adapters isolate OSM/Google/Sheets:** Swap provider (e.g. different map or time API) without touching algorithms; same engine works in Colab and in production.
- **Centralized constraints:** One place to tune for a new city or tenant; no magic numbers in notebooks.
- **Keep Clarke–Wright and 2-opt:** Proven quality and behavior; industrialization is structure, not algorithm change.
- **Carpool cost formula unchanged:** Alpha, beta, gamma, delta encode product decisions; changing them is product iteration, not architecture.
- **Cache duration and graph:** Largest cost at scale is external calls and graph build; caching is necessary for 5k employees and multi-tenant.
- **Optional OR-Tools:** Add when needed for larger VRP or global carpool assignment without replacing heuristics as default.

This document is the **structural and migration blueprint** for the V6 industrial planning engine. No code has been written; it is the analysis and design required before implementation.
