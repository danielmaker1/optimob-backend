# Comparación Block 5: baseline vs tuned (bajo riesgo)

El motor Block 5 **no se modifica**. Solo se comparan dos ejecuciones del mismo `run_shuttle_vrp` con distinta parametría.

## Qué hace el script

- **Entrada común:** mismo censo (CSV), mismo Block 4 (paradas), misma matriz de tiempos D (Haversine).
- **Ejecución A (baseline):** parámetros V4 frozen:
  - `MIN_EMP_SHUTTLE = 15`
  - `BACKFILL_MAX_MIN_PER_PAX = 1.35` (desde `StructuralConstraints.backfill_max_delta_min`)
- **Ejecución B (tuned):** preset de bajo riesgo:
  - `MIN_EMP_SHUTTLE = 12` → se permiten rutas algo más pequeñas antes de absorberlas.
  - `BACKFILL_MAX_MIN_PER_PAX = 1.5` → se acepta un poco más de penalización por pasajero al rellenar paradas pendientes.

## KPIs comparados

| KPI | Descripción |
|-----|-------------|
| `n_routes` | Número de rutas shuttle |
| `n_served_stops` | Paradas incluidas en alguna ruta |
| `n_out_stops` | Paradas que quedan fuera |
| `emp_served` | Empleados en paradas servidas |
| `emp_out` | Empleados en paradas fuera |
| `ioe_pct` | Ocupación efectiva (%) = 100 × emp_served / (BUS_CAPACITY × n_routes) |
| `mean_route_dur_min` | Duración media de ruta (min) |
| `max_route_dur_min` | Duración máxima de ruta (min) |

## Uso

Desde la raíz del repo:

```bash
python -m backend.v6.debug.compare_block5_baseline_vs_tuned
python -m backend.v6.debug.compare_block5_baseline_vs_tuned --out docs/block5_comparison.md
```

Con `--out` se guarda la tabla en CSV o Markdown según la extensión del path.

## Cómo cambiar el preset "tuned"

En `backend/v6/debug/compare_block5_baseline_vs_tuned.py`:

- `TUNED_MIN_EMP_SHUTTLE`: mínimo de empleados por ruta para considerarla viable (tuned más bajo = más rutas pequeñas permitidas).
- `TUNED_BACKFILL_MAX_DELTA_MIN`: tope de minutos extra por pasajero al insertar una parada en backfill (tuned más alto = más inserciones permitidas, posiblemente más cobertura y algo más de duración).

No hace falta tocar el motor en `shuttle_vrp_engine.py` para probar otros valores; basta con definir otro `StructuralConstraints` y otro `min_emp_shuttle` en el script.
