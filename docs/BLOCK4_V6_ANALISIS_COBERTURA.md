# Análisis en profundidad: cobertura Block 4 V6

## Mejoras para Optimob (parámetros y algoritmo)

Se añadieron opciones para **priorizar cobertura** sin romper paridad con V4:

| Mejora | Dónde | Efecto |
|--------|--------|--------|
| **min_ok adaptativo** | Motor | Clusters con centroide a **> 3 km** de oficina pueden mantenerse con **≥ 6** miembros (en vez de 8). Zonas dispersas ganan paradas. |
| **Preset cobertura** | `StructuralConstraints` opcionales | `min_ok_far_m=3000`, `min_ok_far=6`, `pair_radius_m=450`, `assign_radius_m=1200` para más asignación. |
| **Asignar por distancia a parada** | `assign_by_stop_radius_after=True` | Segundo paso: todo residual que quede a ≤ radio de una parada (y con hueco) se asigna a la parada más cercana. Evita que haya excluidos más cerca del centro de una parada que algunos asignados (reabsorción solo mira distancia a *miembros*, no al centro). Incluido en preset `--coverage`. |
| **Evaluador** | `evaluate_block4_v6` | Por defecto usa preset cobertura; con `--v4-parity` usa parámetros V4 estrictos. |

**Uso en evaluación:**
```bash
python -m backend.v6.debug.evaluate_block4_v6        # preset cobertura (por defecto)
python -m backend.v6.debug.evaluate_block4_v6 --v4-parity   # parámetros V4 (paridad)
```

**Uso en código:** pasar `StructuralConstraints(..., min_ok_far_m=3000.0, min_ok_far=6, pair_radius_m=450.0)` y, si se quiere, `assign_radius_m=1200` para radio mayor. Sin estos campos el motor usa parámetros por defecto V4.

---

## Cómo obtener la comparación V4 vs V6 y el análisis

**Opción A – CMD (recomendado)**  
1. Abre **CMD** (no PowerShell).  
2. `cd c:\dev\optimob-backend`  
3. `python -m backend.v6.debug.analyze_block4_coverage_light`

**Opción B – PowerShell**  
1. Abre PowerShell.  
2. `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`  
3. `cd c:\dev\optimob-backend`  
4. `python -m backend.v6.debug.analyze_block4_coverage_light`

El script no usa geopandas ni folium; suele tardar **pocos segundos**. La salida incluye la comparación V4 vs V6 y el análisis de datos, reglas y umbral.

---

## 1. ¿Es normal la cobertura baja? Comparación con V4

Si V4 y V6 dan **cobertura muy similar** (mismo orden de magnitud, p. ej. ~28% ambos), entonces:

- El motor V6 está **alineado** con la lógica de V4.
- La cobertura baja **no es un fallo de V6**, sino del dataset y de las reglas de negocio (que son las mismas en V4 y V6).

La única diferencia relevante es que **V6 aplica separación mínima** (`min_sep`) entre paradas; V4 no. Eso puede hacer que V6 abra un poco menos de paradas (más conservador), pero el nivel de cobertura debería ser del mismo orden.

**Conclusión:** Hacer la comparación con V4 antes de cambiar el motor. Si ambos dan ~25–35%, el criterio de “nivel” (umbral 85%) es lo que hay que revisar, no el algoritmo.

---

## 2. Datos: dispersión y densidad

### 2.1 Dispersión respecto a la oficina

- **Radio de asignación** = 1000 m y **exclude_radius_m** = 1000 m.
- Empleados **muy lejos** de la oficina:
  - Pueden quedar fuera del radio de 1000 m de cualquier parada candidata.
  - O formar clusters cuyo **centroide** cae a < 1000 m de la oficina → todo el cluster se manda a carpool (regla de exclusión).
- Si la **mayoría** de los 500 empleados está a > 2000 m de la oficina, es normal que solo una parte pueda entrar en shuttle.

El script muestra:
- Distancia mínima, máxima y media a la oficina.
- Porcentaje dentro de 500 m, 1000 m, 2000 m.

**Interpretación:** Cuantos más empleados lejos de la oficina, más limitada la cobertura shuttle por definición del negocio (radio y exclusión).

### 2.2 Densidad (vecinos en 1000 m)

- Cada parada agrupa empleados dentro de **assign_radius_m = 1000 m**.
- Para que un cluster se **mantenga**, debe tener al menos **min_ok = 8** miembros (los que tienen < 8 se descartan).
- Si **pocos** empleados tienen “≥ 8 vecinos dentro de 1000 m”, el algoritmo no puede formar muchos clusters válidos.

El script muestra:
- Número de vecinos en 1000 m (media, min, max).
- Cuántos empleados tienen ≥ 6 vecinos (min_shuttle) y ≥ 8 (min_ok).

**Interpretación:** Si solo un 20–30% tiene 8+ vecinos en 1000 m, la cobertura shuttle tiene un **techo** natural por densidad; 85% sería inalcanzable sin relajar reglas o cambiar datos.

---

## 3. Reglas estrictas

Block 4 aplica varias reglas que **reducen** la cobertura shuttle:

| Regla | Efecto |
|-------|--------|
| **min_ok = 8** | Clusters con < 8 miembros se descartan → esos empleados van a residual/carpool. |
| **max_ok = 40** | Clusters grandes se parten (KMeans); subclusters con < 8 se descartan. |
| **exclude_radius_m = 1000** | Si el **centroide** del cluster está a < 1000 m de la oficina, todo el cluster va a carpool (no se considera parada shuttle). |
| **Fusión** | Clusters muy cercanos se fusionan si cumplen tamaño y diámetro; puede dejar menos paradas. |

Con **poca densidad** y **dispersión**:
- Se forman pocos clusters con ≥ 8 miembros.
- Varios clusters pueden quedar “cerca de oficina” y excluirse.
- Resultado típico: **20–40%** de cobertura shuttle. No es un bug; es consecuencia de datos + reglas.

---

## 4. Umbral de “nivel” (85% = OK)

- El evaluador marca **FAIL** si cobertura < 85%.
- En un dataset **disperso** y con las reglas actuales, 85% es **poco realista**.
- Entonces el **FAIL** está castigando más al **criterio de evaluación** que al motor: el motor se comporta como se diseñó; el umbral no está adaptado a este tipo de datos.

**Recomendaciones:**

1. **Umbral configurable** según tipo de dataset (p. ej. OK ≥ 70%, WARN ≥ 50% para datos dispersos).
2. **Documentar** que 85% es un objetivo para datos densos / cercanos a oficina.
3. **No** usar el FAIL actual como indicador de “motor malo”; usarlo como “objetivo de cobertura no alcanzado con estos datos/reglas”.

---

## 5. Solape entre clusters (trade-off cobertura vs redundancia)

El **solape** que se ve en el mapa (varios círculos azules cubriendo la misma zona) es **esperado**, no un fallo:

- Los **centros** de parada solo se separan por **min_sep** (p. ej. 350 m).
- Cada parada tiene **radio de cobertura** mucho mayor: **assign_radius** (1000–1200 m).
- Con 350 m entre centros y 1000 m de radio, los círculos se solapan en zonas densas. El algoritmo no intenta reducir solape; prioriza cobertura.

**Implicaciones:**

- **Asignación:** Cada empleado pertenece a **una sola** parada (la más cercana con capacidad). El solape es visual, no ambigüedad operativa.
- **Negocio:** Muchos círculos solapados implican **más paradas** en poco espacio → posible redundancia y mayor coste (más rutas/paradas). A cambio se obtiene buena cobertura y clusters compactos.
- **Trade-off:** Menos solape (p. ej. subir `min_sep` a 500–600 m) reduciría paradas en zonas densas pero podría bajar algo la cobertura. Es una decisión de diseño: priorizar cobertura y calidad de cluster vs. menos paradas y menor coste.

El evaluador incluye un indicador de **paradas con solape** (cuántas tienen al menos otra parada a ≤ radio) para poder decidir si se quiere actuar (p. ej. aumentar `min_sep` o usar un preset “bajo solape” en el futuro).

---

## 6. Resumen

| Pregunta | Respuesta |
|----------|-----------|
| ¿V6 está mal? | No; si V4 y V6 dan cobertura similar, el motor está alineado. |
| ¿Por qué cobertura baja? | Datos (dispersión, poca densidad) + reglas (min_ok, exclude_radius). |
| ¿85% es razonable? | Para este dataset, no; conviene umbral más bajo o configurable. |
| ¿Por qué hay tanto solape? | min_sep << assign_radius; es el trade-off actual (cobertura vs. redundancia). |

Ejecutando `analyze_block4_coverage_light` obtienes los números concretos (V4 vs V6, distancias, densidad) para validar este análisis en tu entorno.
