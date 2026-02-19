# Diseño Carpool 6A + 6B en V6

Documento de diseño para migrar la lógica de carpool del notebook V4 frozen (Bloques 6A y 6B) a motores V6 puros, sin depender del notebook ni de Sheets/Folium. Incluye contratos de entrada/salida y dependencias opcionales (grafo OSM / adapter de tiempos).

---

## 1. Resumen ejecutivo

- **6A (prep estructural):** A partir del residual de Block 4 (`carpool_set`), normalizar a un “censo carpool” (conductores y pasajeros), opcionalmente construir grafo OSM para routing, y exponer helpers de tiempo/distancia (driver→MP, MP→oficina, pax→MP a pie). **Salida:** lista de MPs no se calcula en 6A en V4; en V4 el grafo y `df_carpool` son la base para 6B.
- **6B (matching diario):** DBSCAN sobre (lat, lon) del censo carpool → meeting points (MPs) → snap a red → cluster suave de MPs. Matrices T_drv_mp, T_mp_off, Walk_pax_mp. Candidatos (driver, pax, MP) con coste α·walk + β·detour + γ·|ETA−hora_obj|. Matching greedy con bonus δ por ocupación. Por conductor: cheapest insertion del orden de MPs + 2-opt + validación detour. **Salida:** matches (driver, pax, id_mp), rutas por conductor, pax no asignados.

Para V6 conviene separar:
- **Motor 6A:** “Carpool prep” = residual → censo carpool (conductores/pax) + opcionalmente grafo/adapter de tiempos. No incluye DBSCAN ni MPs; eso es 6B.
- **Motor 6B:** “Carpool match” = censo carpool + oficina + adapter de tiempos (y opcionalmente grafo para snap) → MPs (DBSCAN + cluster suave) → candidatos → matching greedy → routing (cheapest insertion + 2-opt) → matches + rutas + no asignados.

---

## 2. Block 6A en V4 (qué hace)

1. **Entradas:** `df_empleados`, `carpool_set` (ids de empleados no shuttle), `COORDENADAS_OFICINA`.
2. **Normalización:** Construir `df_carpool_all` con columnas id, lat, lon, office_lat, office_lon, has_car, seats_driver, open_carpool, hora_obj (min desde medianoche). Filtrar por `carpool_set` → `df_carpool`.
3. **Roles:** conductor = has_car y seats_driver > 0; pasajero = no has_car; resto "none". Filtrar solo driver y pax.
4. **Grafo OSM:** `ox.graph_from_point(office, dist=radius_km*1000, drive)` + speeds + travel_time; `travel_time_min` por arista. Radio dinámico según dispersión de hogares (margen 6 km, max 28 km).
5. **Helpers:** `nearest_node(lat, lon)`, `sp_time_min(u, v)`, `tt_min_coords(latA, lonA, latB, lonB)`, `walk_dist_m(lat1, lon1, lat2, lon2)` (Haversine).

**Salida 6A:** `df_carpool` (id, lat, lon, office_*, has_car, seats_driver, rol, hora_obj, cap_efectiva), grafo `G` (alias G_CARPOOL), `nearest_node`, `tt_min_coords`, `walk_dist_m`, oficina (OFFICE_LAT, OFFICE_LON).

---

## 3. Block 6B en V4 (qué hace)

### 3.1 Configuración (CFG_MATCH)

| Parámetro | Valor V4 | Descripción |
|-----------|----------|-------------|
| DBSCAN_EPS_M | 500 | Radio (m) para DBSCAN de población → clusters MP. |
| DBSCAN_MIN_SAMPLES | 3 | Mínimo puntos por cluster. |
| MP_CLUSTER_EPS_M | 300 | Radio (m) para segundo DBSCAN (deduplicar MPs). |
| MAX_WALK_M | 800 | Máximo andando pax → MP (m). |
| K_MP_PAX | 5 | MPs candidatos por pasajero (top-K por walk). |
| MAX_DETOUR_MIN | 25.0 | Límite desvío (min) por candidato/ruta. |
| MAX_DETOUR_RATIO | 1.6 | Límite ratio tiempo_ruta / tiempo_directo. |
| ALPHA_WALK | 1.0 | Peso coste: metros andando. |
| BETA_DETOUR | 60.0 | Peso coste: minutos de desvío. |
| GAMMA_ETA_OFF | 2.0 | Peso coste: \|ETA − hora_obj\| (min). |
| DELTA_OCCUPANCY_BONUS | 50.0 | Bonus (se resta) por asiento ya ocupado del conductor. |
| MAX_DRIVERS_PER_MP | 40 | Top-N conductores más cercanos por MP. |
| MIN_PASSENGERS_PER_DRIVER | 1 | Mínimo pax por conductor para aparecer en resumen. |
| DO_2OPT | True | Aplicar 2-opt al orden de MPs por conductor. |

### 3.2 Flujo 6B

1. **MPs por cobertura (`_mps_por_cobertura`):**
   - DBSCAN(eps=DBSCAN_EPS_M/6371000 rad, min_samples=DBSCAN_MIN_SAMPLES, metric=haversine) sobre (lat, lon) de `df_carpool`.
   - Por cada cluster (label != -1): centroide en rad → deg → `nearest_node(lat, lon)` → coordenadas del nodo en G → (lat, lon) del MP.
   - Segundo DBSCAN sobre MPs (eps=MP_CLUSTER_EPS_M, min_samples=1) → promediar (lat, lon) por cluster → lista final de MPs con id_mp (MP_1, MP_2, …).

2. **Matrices:**
   - T_drv_mp[D, M], T_mp_off[M], T_drv_off[D], Walk_pax_mp[P, M] (inf si walk > MAX_WALK_M).
   - Drivers candidatos por MP: BallTree sobre (lat, lon) conductores → por cada MP, top MAX_DRIVERS_PER_MP.

3. **Candidatos:**
   - Por cada pax p, MPs alcanzables a pie (Walk_pax_mp[p,m] ≤ MAX_WALK_M), ordenados por walk, top K_MP_PAX.
   - Por cada (pax, MP), por cada driver d en candidatos del MP: t_route = T_drv_mp[d,m] + T_mp_off[m], t_direct = T_drv_off[d]. detour_min = max(0, t_route − t_direct), detour_ratio = t_route/t_direct.
   - Si detour_min > MAX_DETOUR_MIN o detour_ratio > MAX_DETOUR_RATIO → descartar.
   - cost = ALPHA_WALK·walk_m + BETA_DETOUR·detour_min + GAMMA_ETA_OFF·|t_route − hora_obj|.
   - Filas (driver, pax, id_mp, mp_lat, mp_lon, walk_m, detour_min, detour_ratio, eta_oficina_min, cost).

4. **Matching greedy:**
   - Ordenar candidatos por cost. Por cada pax (groupby pax): elegir mejor (driver, id_mp) con score = cost − DELTA·(nº pax ya asignados a ese driver); respetar cap_efectiva. Ir restando capacidad y añadiendo matches.

5. **Routing por conductor:**
   - Por cada driver con matches: MPs únicos que visita. T_src_to_mp, T_mp_to_off, T_mp_mp (matriz entre esos MPs).
   - Orden inicial: cheapest insertion (inc_cost en primera/última/entre posiciones).
   - Si DO_2OPT: 2-opt aleatorio (iters=200) sobre orden de MPs.
   - Calcular t_route total; si detour_min > MAX_DETOUR_MIN o detour_ratio > MAX_DETOUR_RATIO: ir quitando MPs del final hasta cumplir; actualizar matches (quitar pax de MPs eliminados).

6. **Salidas:** df_matches (driver, pax, id_mp, …), df_driver_summary (driver, n_pax, ocupacion_pct, duracion_min, detour_min, detour_ratio, eta_oficina_min, offset_min), df_routes (driver, order, lat, lon, is_mp, is_office, id_mp, pax_suben), pax no asignados.

---

## 4. Contratos propuestos para V6

### 4.1 Tipos de dominio (resumen)

- **CarpoolPerson:** id, lat, lon, office_lat, office_lon, is_driver, seats_driver (0 si pasajero), hora_obj_min (opcional), cap_efectiva (para conductores).
- **MeetingPoint:** id_mp, lat, lon.
- **CarpoolMatch:** driver_id, pax_id, id_mp, mp_lat, mp_lon, walk_m, detour_min, cost (u otros campos útiles).
- **DriverRoute:** driver_id, order_mp_ids, total_dur_min, detour_min, detour_ratio, n_pax (y opcional lista pax por MP).

### 4.2 Motor 6A (carpool_prep)

- **Nombre sugerido:** `carpool_prep_engine` o módulo dentro de `network_design_engine` / `allocation_engine` según se considere estructural o diario. En V4 6A es “prep” que alimenta 6B; no genera MPs.
- **Entrada:**
  - `residual_employees: List[Employee]` (o equivalente con has_car, seats, hora_obj).
  - `office_lat: float`, `office_lng: float`.
  - Opcional: radio_km para grafo (si no se usa grafo dinámico).
- **Salida:**
  - `carpool_census: List[CarpoolPerson]` (solo driver y pax; cada uno con rol, cap_efectiva para conductores).
  - Opcional: grafo G (o interfaz `TimeAdapter`: tt_min_coords, walk_dist_m, nearest_node para snap). Para MVP se puede usar solo Haversine + velocidad constante (como en Block 5) sin OSM.

**Nota:** En V4 el “grafo” se usa en 6A para construir G y en 6B para `nearest_node` (snap de centroides a nodo) y para `tt_min_coords`. En V6 se puede inyectar un adapter que, sin OSM, devuelva tiempos por Haversine; el snap a “nodo” en ese caso puede ser (lat, lon) del centroide sin cambiar.

### 4.3 Motor 6B (carpool_match)

- **Nombre sugerido:** `carpool_match_engine` (por ejemplo en `core/allocation_engine/` o `core/network_design_engine/`).
- **Entrada:**
  - `carpool_census: List[CarpoolPerson]` (salida de 6A o equivalente).
  - `office_lat, office_lng: float`.
  - `time_adapter`: interfaz con `tt_min(lat1, lon1, lat2, lon2) -> float` (min), `walk_dist_m(lat1, lon1, lat2, lon2) -> float`. Opcional `nearest_node(lat, lon) -> (lat, lon)` para snap (si no hay, usar (lat, lon) directo).
  - `config: CarpoolMatchConfig` (DBSCAN_EPS_M, DBSCAN_MIN_SAMPLES, MP_CLUSTER_EPS_M, MAX_WALK_M, K_MP_PAX, MAX_DETOUR_MIN, MAX_DETOUR_RATIO, ALPHA_WALK, BETA_DETOUR, GAMMA_ETA_OFF, DELTA_OCCUPANCY_BONUS, MAX_DRIVERS_PER_MP, MIN_PASSENGERS_PER_DRIVER, DO_2OPT).
- **Salida:**
  - `matches: List[CarpoolMatch]`.
  - `driver_routes: List[DriverRoute]` (orden de MPs, duración, detour, n_pax).
  - `unmatched_pax_ids: List[str]`.

---

## 5. Dependencias y adapters

- **Tiempos / distancias:** V4 usa OSM (nx.shortest_path_length por travel_time_min) y walk_dist_m Haversine. Para V6:
  - **Opción A (MVP):** adapter que use solo Haversine + velocidad (ej. 30 km/h) para tt_min y walk_dist_m = Haversine; sin grafo. Snap de MP = centroide sin cambiar.
  - **Opción B:** adapter que use grafo OSM (ox, nx) cuando esté disponible; misma interfaz.
- **DBSCAN:** ya usado en V4 con sklearn.cluster.DBSCAN (haversine en radianes). Mantener en V6 con la misma métrica.
- **BallTree:** sklearn.neighbors.BallTree para “drivers cercanos a MP”; mantener en V6.

No se requiere Sheets ni Folium dentro de los motores; la persistencia y los mapas quedan en capas superiores.

---

## 6. Integración con el flujo actual V6

- **plan_population actual:** usa Block 4 → shuttle_options + carpool_set; residual → `generate_carpool_candidates` (option.py) que solo agrupa por proximidad y willing_driver. No hay MPs ni coste α,β,γ,δ.
- **Objetivo:** sustituir o complementar `generate_carpool_candidates` con:
  1. **6A:** residual_employees (carpool_set) → carpool_census (lista CarpoolPerson con rol driver/pax). Opcional: grafo/adapter.
  2. **6B:** carpool_census + office + adapter + config → matches + driver_routes + unmatched_pax_ids.
  3. Convertir `matches` y `driver_routes` al formato que consuma el assignment/caso de uso (p. ej. CarpoolOption o estructura equivalente) para no romper el resto del pipeline.

La capa diaria (Layer B) podrá reutilizar los mismos motores 6A/6B con el residual del día (quien reservó pero no tiene plaza shuttle) y opcionalmente con MPs precalculados en diseño estructural (si en el futuro se fijan MPs por semana).

---

## 7. Próximos pasos sugeridos

1. **Implementar `carpool_prep_engine` (6A):** residual → carpool_census; adapter de tiempo/distancia con default Haversine.
2. **Implementar `carpool_match_engine` (6B):** DBSCAN MPs, matrices, candidatos, greedy match, cheapest insertion + 2-opt, validación detour; salidas matches, driver_routes, unmatched_pax_ids.
3. **Añadir `CarpoolMatchConfig`** (y opcionalmente CarpoolPerson, MeetingPoint, etc.) en `domain/constraints.py` o `domain/models.py`.
4. **Script de evaluación:** cargar censo congelado, ejecutar Block 4 → carpool_set → 6A → 6B, comparar nº matches y KPIs con V4 (o con generate_carpool_candidates) sin tocar la API hasta validar.
5. **Wire en plan_population o run_daily_allocation:** una vez validado, sustituir o combinar con `generate_carpool_candidates` y exponer en la API.

---

*Documento listo para usar como referencia al implementar los motores 6A y 6B en V6. Cuando la implementación esté avanzada, se puede actualizar este doc con nombres definitivos de módulos y firmas de funciones.*
