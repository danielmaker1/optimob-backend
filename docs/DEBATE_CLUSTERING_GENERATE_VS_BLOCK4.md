# Debate técnico: Clustering Generate vs Block 4 para Optimob

**Contexto:** Comparación en profundidad de los dos enfoques de clustering shuttle en V6, valorados desde la perspectiva del **pasajero** y del **operador de rutas de bus para empresas** (ej. BusUp).

---

## 1. Resumen ejecutivo

| Enfoque | Dónde está | Idea central |
|--------|------------|--------------|
| **Generate** | Producción actual (`option.py` → `generate_shuttle_candidates`) | Agrupar por proximidad casa–casa (radio 1,5 km). Todo el mundo acaba en exactamente un cluster. Sin concepto de “parada” ni de “carpool por cercanía a oficina”. |
| **Block 4** | Candidato a producción (`shuttle_stop_engine.py` → `run_shuttle_stop_opening`) | Abrir “paradas” con reglas operativas: radio de asignación (ej. 1200 m), separación mínima entre paradas, mínimo de pasajeros por parada, exclusión cerca de oficina (carpool). Resultado: paradas viables + residual a carpool. |

**Conclusión adelantada:** Generate es más simple y da cobertura 100% en papel; Block 4 es más alineado con la operación real (paradas, distancia a pie, carpool, viabilidad por ruta) y con lo que un pasajero y un operador esperan. Para un producto tipo BusUp, Block 4 es el enfoque recomendado; Generate puede mantenerse como referencia o MVP muy temprano.

---

## 2. Descripción técnica de ambos algoritmos

### 2.1 Generate (producción actual)

**Ubicación:** `backend/v6/domain/option.py` — `generate_shuttle_candidates(employees)`.

**Lógica:**

1. Ordenar empleados por `employee_id` (determinismo).
2. Para cada empleado aún no asignado:
   - Crear un nuevo cluster con ese empleado como “semilla”.
   - Añadir **todos** los no asignados cuya **casa** esté a ≤ **1,5 km** (Haversine) de la casa del primero.
3. Centroide del cluster = media de lat/lng de los miembros.
4. Cada empleado pertenece a **exactamente** un cluster.

**Parámetros relevantes:**

- `SHUTTLE_CLUSTER_RADIUS_KM = 1.5` — único radio; es **casa–casa**, no “casa–parada”.

**No existe:**

- Exclusión por cercanía a oficina (carpool).
- Límite de “distancia máxima a pie hasta la parada” (assign_radius).
- Mínimo de pasajeros por cluster (min_ok); clusters de 1 persona son válidos.
- Separación mínima entre “paradas” (min_sep).
- Concepto explícito de “parada” (solo centroide de cluster).

---

### 2.2 Block 4 (candidato a producción)

**Ubicación:** `backend/v6/core/network_design_engine/shuttle_stop_engine.py` — `run_shuttle_stop_opening(employees, office_lat, office_lng, constraints)`.

**Lógica resumida:**

1. **Greedy de apertura de paradas:** Se abren “paradas” (centros) de forma greedy: en cada paso se elige el centro que maximiza pasajeros nuevos dentro de **assign_radius_m** (ej. 1200 m), con **separación mínima** (min_sep, ej. 350 m) entre paradas. Solo se abre parada si tiene al menos **min_ok** (ej. 8) pasajeros; si no hay ninguna, se relaja a **fallback_min** (ej. 8).
2. **Centro = medoide** (punto real que minimiza suma de distancias), no media geométrica.
3. **Reabsorción:** Empleados no asignados que estén a ≤ **pair_radius_m** de algún **miembro** de una parada se asignan a esa parada (hasta cap).
4. **Filtro por tamaño:** Clusters con &lt; min_ok (o min_ok_far en zona lejana) se descartan; los &gt; max_ok se parten (KMeans).
5. **Fusión:** Clusters cuyo centroide esté a ≤ fusion_radius se fusionan si diámetro y tamaño lo permiten.
6. **Exclusión oficina:** Clusters cuyo **centroide** está a &lt; **exclude_radius_m** de la oficina se mandan **íntegros a carpool** (no son paradas shuttle).
7. **Segundo paso opcional:** Con `assign_by_stop_radius_after=True`, el residual que quede a ≤ assign_radius del **centroide** de alguna parada (y con hueco) se asigna a la parada más cercana.

**Parámetros típicos (preset cobertura):**

- `assign_radius_m = 1200` — “máximo a pie hasta la parada”.
- `exclude_radius_m = 1000` — zona carpool cerca de oficina.
- `min_ok = 8`, `min_ok_far = 6` (si centroide &gt; 3 km de oficina).
- `min_stop_sep_m = 350` — no dos paradas demasiado cerca.
- `pair_radius_m = 450` — reabsorción por cercanía a un miembro.
- `assign_by_stop_radius_after = True` — reasignar residual por distancia al centro de parada.

**Resultado:** Lista de clusters (paradas) + conjunto de empleados **carpool** (residual).

---

## 3. Criterios de comparación

Se valoran ambos enfoques en:

- **Pasajero:** distancia a pie, previsibilidad, equidad, experiencia real.
- **Operador (BusUp-style):** número y calidad de paradas, rutas realizables, coste, escalabilidad y mantenimiento.

---

## 4. Perspectiva pasajero

### 4.1 Distancia a pie hasta la “parada”

| Aspecto | Generate | Block 4 |
|--------|----------|---------|
| **Qué se garantiza** | Nadie está a más de **1,5 km** de **otro pasajero** (casa–casa). No se garantiza distancia a un “lugar de parada” común. | Se garantiza que quien está asignado a una parada está a ≤ **assign_radius** (ej. 1200 m) del **centro de la parada** (medoide). |
| **Interpretación** | En el peor caso, el pasajero puede estar a ~1,5 km de la “parada” (centroide), y en práctica a más si el centroide cae lejos de su casa. | La parada es un punto concreto; el operador puede colocar la parada física cerca del medoide. 1200 m es un estándar razonable “a pie”. |
| **Veredicto pasajero** | **Block 4 gana:** la promesa “a pie hasta la parada” es explícita y acotada (ej. 1200 m). En Generate la promesa es “cerca de otros pasajeros”, no “cerca de la parada”. |

### 4.2 Previsibilidad y claridad

- **Generate:** “Estás en la opción shuttle X” (centroide en (lat, lng)). No se distingue “irás a pie a una parada” vs “te recogen en un radio amplio”. El operador tiene que interpretar el centroide como parada.
- **Block 4:** “Tienes parada P a hasta 1200 m; si no, eres carpool.” Mensaje claro para el pasajero y para la app (“tu parada está aquí, a X m de tu casa”).

**Veredicto:** **Block 4** da un mensaje más previsible y honesto para el pasajero.

### 4.3 Equidad (quién va en shuttle y quién no)

- **Generate:** Todo el mundo aparece en alguna opción shuttle; no hay criterio de “demasiado cerca de oficina = carpool”. Quien vive al lado de la oficina puede aparecer en un cluster shuttle (poco realista).
- **Block 4:** Quien está en zona **exclude_radius** (cerca de oficina) va explícitamente a **carpool**. Quien no alcanza ninguna parada dentro de assign_radius queda residual (carpool u otra alternativa). La regla es la misma para todos y está parametrizada.

**Veredicto:** **Block 4** es más justo y comprensible: las reglas (radio a pie, zona carpool) son explícitas.

### 4.4 Experiencia real (lluvia, equipaje, tiempo)

- **Generate:** Un cluster puede tener diámetro grande (hasta ~1,5 km entre extremos). Quien queda en el borde puede tener 10–15 min andando hasta el centroide; en invierno o con equipaje es pesado.
- **Block 4:** 1200 m (o el valor configurado) es un tope conocido; se puede comunicar “máximo 12–15 min a pie” y diseñar paradas en sitios con acera/refugio.

**Veredicto:** **Block 4** permite diseñar la experiencia a pie con un límite claro; Generate no acota bien el peor caso para el pasajero.

---

## 5. Perspectiva operador (rutas bus para empresas, tipo BusUp)

### 5.1 Número y calidad de “paradas”

| Aspecto | Generate | Block 4 |
|--------|----------|---------|
| **Número de paradas** | Tantos clusters como “semillas” necesarias para cubrir a todos; puede haber muchos clusters pequeños (incluso de 1). | Solo paradas que cumplen **min_ok** (y min_sep, exclude, etc.). Menos paradas, pero cada una con volumen mínimo. |
| **Calidad** | Clusters pueden ser inviables operativamente (muy pocos pasajeros, o demasiado dispersos para una sola parada). | Cada parada tiene al menos min_ok pasajeros y está separada de otras (min_sep); mejor para planificar una ruta de bus. |

**Veredicto operador:** **Block 4** produce paradas que tienen sentido para una ruta: volumen mínimo y separación razonable. Generate puede generar muchas “paradas” que un operador no usaría tal cual.

### 5.2 Diseño de rutas y coste

- **Generate:** Muchos puntos (centroides); el operador debe decidir cuáles convertir en paradas reales y cuáles ignorar (p. ej. clusters de 2–3 personas). Riesgo de rutas con muchas paradas poco utilizadas.
- **Block 4:** Paradas ya filtradas por tamaño y por exclusión cerca de oficina. La ruta puede diseñarse uniendo estas paradas; menos paradas y más llenas suele implicar menos km y menos tiempo de ruta.

**Veredicto:** **Block 4** facilita el diseño de rutas y un coste más predecible (menos paradas, más pasajeros por parada en media).

### 5.3 Escalabilidad y mantenimiento

- **Generate:** Muy simple (solo Haversine y orden). Fácil de mantener; difícil de “afinar” sin añadir reglas (exclude_radius, assign_radius, min_ok) que acaban acercándolo a Block 4.
- **Block 4:** Más parámetros (assign_radius, exclude_radius, min_ok, min_sep, pair_radius, etc.), pero cada uno tiene un significado operativo claro. Un operador puede ajustar “radio a pie” o “mínimo pasajeros por parada” sin tocar la lógica core.

**Veredicto:** Para un producto en evolución (BusUp-style), **Block 4** ofrece más knobs útiles y un modelo mental (“paradas + carpool”) alineado con la operación.

### 5.4 Comunicación con cliente (empresa) y pasajeros

- **Generate:** “Tenemos N opciones shuttle” (a veces muchas, algunas muy pequeñas). Explicar por qué una “opción” no se convierte en parada es incómodo.
- **Block 4:** “Tenemos M paradas shuttle; el resto va en carpool u otras alternativas.” Mensaje claro para la empresa y para el dashboard (cobertura shuttle vs carpool).

**Veredicto:** **Block 4** encaja mejor con la narrativa operativa y comercial (paradas, cobertura, carpool).

---

## 6. Tabla comparativa global

| Criterio | Generate | Block 4 |
|----------|----------|---------|
| **Distancia a pie (límite claro)** | No (solo 1,5 km casa–casa) | Sí (assign_radius, ej. 1200 m) |
| **Zona carpool (cerca oficina)** | No | Sí (exclude_radius_m) |
| **Mínimo pasajeros por parada** | No (clusters de 1 válidos) | Sí (min_ok / min_ok_far) |
| **Separación entre paradas** | No | Sí (min_sep) |
| **Centro de parada** | Media (centroide) | Medoide (punto real) |
| **Cobertura en papel** | 100% (todos en algún cluster) | &lt; 100% (residual = carpool) |
| **Alineación con operación real** | Baja | Alta |
| **Complejidad implementación** | Baja | Media |
| **Determinismo** | Sí (orden employee_id) | Sí (tie-break por índice, KMeans seed fijo) |
| **Reabsorción residual** | No aplica | Sí (pair_radius + opcional assign_by_stop_radius_after) |

---

## 7. Riesgos y matices

### Generate

- **Riesgo:** Vender “100% cobertura shuttle” cuando en la práctica muchas “opciones” no son convertibles en paradas útiles (muy pocos pasajeros o andadura demasiado larga). Percepción de “promesa incumplida” cuando el operador no abre parada en cada cluster.
- **Cuándo puede tener sentido:** MVP muy temprano, solo para agrupar y visualizar; o como fallback si Block 4 no está disponible.

### Block 4

- **Riesgo:** Cobertura numérica menor (p. ej. 30–40% shuttle, resto carpool) puede chocar con expectativas de “máxima cobertura” si no se comunica bien que el objetivo es “paradas viables” y “carpool para el resto”.
- **Mitigación:** Preset cobertura (assign_radius 1200 m, min_ok_far, assign_by_stop_radius_after) ya implementado; documentar bien qué es “cobertura shuttle” vs “cobertura total (shuttle + carpool)”.

---

## 8. Conclusión y recomendación

- **Para el pasajero:** Block 4 ofrece una promesa clara (“a pie hasta X m de tu parada” o “carpool si estás muy cerca de oficina”) y un tope de distancia a pie realista. Generate no acota bien la experiencia a pie ni distingue shuttle vs carpool.
- **Para el operador (BusUp-style):** Block 4 entrega paradas con volumen mínimo y separación, lo que facilita rutas, costes y comunicación con la empresa. Generate entrega muchos clusters, algunos no viables como paradas únicas.

**Recomendación técnica:** Considerar **Block 4** como el modelo de clustering para producción en Optimob, manteniendo Generate como referencia o modo legacy. Implementar la puesta en producción mediante **modo sombra** (calcular ambos, comparar KPIs y mapas) y luego cambiar el flujo principal a Block 4 cuando los resultados estén validados.

---

## 9. Referencias en el repo

- Generate: `backend/v6/domain/option.py` — `generate_shuttle_candidates`, `SHUTTLE_CLUSTER_RADIUS_KM`.
- Block 4: `backend/v6/core/network_design_engine/shuttle_stop_engine.py` — `run_shuttle_stop_opening`; parámetros por defecto en `ShuttleStopParams` y `StructuralConstraints` (getattr con defaults V4).
- Constraints: `backend/v6/domain/constraints.py` — `StructuralConstraints` (assign_radius_m, min_ok_far_m, min_ok_far, pair_radius_m, assign_by_stop_radius_after).
- Evaluación: `evaluate_block4_v6.py` (Block 4), `evaluate_generate_shuttle_v6.py` (Generate); ver también `docs/BLOCK4_V6_ANALISIS_COBERTURA.md`.
