# Integración Block 4 en primera línea

Block 4 es ya la **primera línea** de generación de candidatos shuttle. El clustering legacy (generate_shuttle_candidates) queda en **sombra** opcional.

## Flujo actual

1. **`plan_population`** (`application/use_cases/plan_population.py`)
   - Llama a **`get_shuttle_candidates_block4`** (oficina y constraints por defecto o inyectados).
   - Recibe `(shuttle_options, carpool_set)`.
   - El **residual** para carpool es exactamente `carpool_set` (no se deriva de “no asignados a shuttle”).
   - Opcionalmente, si `include_shadow_metrics=True`, ejecuta `generate_shuttle_candidates` y rellena `DailyPlan.shuttle_shadow_metrics` (`n_clusters`, `coverage_pct`).

2. **`get_shuttle_candidates_block4`** (`application/shuttle_candidates.py`)
   - Llama a **`run_shuttle_stop_opening`** (motor Block 4 en `core/network_design_engine/shuttle_stop_engine.py`).
   - Convierte `final_clusters` (listas de employee_id) en **`list[ShuttleOption]`** con centroides en lat/lng para que el resto del pipeline (evaluación, assignment, DailyPlan) no cambie.

3. **Config por defecto** (`application/config.py`)
   - `DEFAULT_OFFICE_LAT`, `DEFAULT_OFFICE_LNG`.
   - `DEFAULT_STRUCTURAL_CONSTRAINTS` (preset cobertura: assign_radius 1200 m, min_ok_far, pair_radius, etc.).

4. **API** (`api/router.py`, `api/schemas.py`)
   - `POST /v6/plan`: no requiere cambios en el body; puede enviar `include_shadow_metrics: true` para recibir `shuttle_shadow_metrics` en la respuesta.
   - `DailyPlanSchema` incluye `shuttle_shadow_metrics: dict | None`.

## Orden del código

| Capa | Responsabilidad |
|------|-----------------|
| **domain/option.py** | `generate_shuttle_candidates` (sombra), `generate_carpool_candidates`. Sin cambios en la firma. |
| **core/.../shuttle_stop_engine.py** | Block 4: `run_shuttle_stop_opening`. Sin cambios. |
| **application/config.py** | Defaults oficina y StructuralConstraints. |
| **application/shuttle_candidates.py** | Adapter Block 4 → ShuttleOption; `get_shuttle_candidates_block4`. |
| **application/use_cases/plan_population.py** | Orquestación: Block 4 como fuente de shuttle + carpool_set como residual; sombra opcional. |
| **api/** | Pasa `include_shadow_metrics` y expone `shuttle_shadow_metrics`. |

No hay lógica duplicada: una sola fuente de verdad para “candidatos shuttle” en producción (Block 4), y el clustering legacy solo se invoca cuando se piden métricas de sombra.

## Cómo probar

Desde la raíz del repo:

```bash
python -m backend.v6.debug.smoke_plan_population
```

Comparación explícita Block 4 vs Generate (métricas y mapa):

```bash
python -m backend.v6.debug.evaluate_block4_v6 --map
python -m backend.v6.debug.evaluate_generate_shuttle_v6 --map
```
