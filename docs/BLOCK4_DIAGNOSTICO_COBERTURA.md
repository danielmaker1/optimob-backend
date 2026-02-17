# Diagnóstico: ¿Por qué la cobertura es 28%?

**Pregunta:** ¿El resultado es malo por el algoritmo, los parámetros, limitaciones de los datos, o por otra cosa?

---

## 1. ¿El algoritmo es incorrecto?

**Conclusión: No.** La evidencia es directa:

- Ejecutamos **V4** (Block 4 original) y **V6** (motor actual) sobre **el mismo CSV**.
- Resultado: **mismos números** (15 paradas, 141 asignados, 28,2% cobertura).
- Si el algoritmo V6 estuviera mal, daría algo distinto a V4. Da lo mismo → la lógica está bien implementada y alineada con V4.

El mapa no indica errores de asignación: las paradas están donde hay densidad suficiente y los excluidos están fuera de los círculos, como cabría esperar del diseño.

---

## 2. ¿Los parámetros son incorrectos?

**Conclusión: Depende del objetivo.**

- Los parámetros actuales son los **por defecto de V4** (radio 1000 m, min_ok=8, reabsorción 350 m, etc.).
- Para un **objetivo de máxima cobertura** en datos dispersos, esos valores son **conservadores**:
  - Radio 1000 m → en zonas dispersas pocos tienen 8 vecinos en 1000 m (solo ~13% en tu dataset).
  - min_ok=8 → se descartan clusters de 6–7 que en zonas lejanas podrían ser válidos.
- Si cambias a **preset cobertura** (`--coverage`: radio 1200 m, reabsorción 450 m, min_ok adaptativo 6 en zona lejana), la cobertura puede subir algo, pero con datos tan dispersos el techo sigue limitado por la densidad.

Así que: los parámetros no están “mal” en abstracto; están pensados para un equilibrio conservador. Para priorizar cobertura en una masa dispersa, **sí** tiene sentido probar parámetros más permisivos (como el preset `--coverage`).

---

## 3. ¿Hay limitaciones obvias y no se puede hacer mejor clustering para una masa dispersa?

**Conclusión: Sí, en gran parte.**

- **Datos:** Con 500 empleados, mediana de distancia a oficina ~8,5 km y solo ~13% con 8+ vecinos en 1000 m, la **geometría** del problema es de poca densidad.
- **Reglas de negocio:** Block 4 exige:
  - Mínimo de personas por parada (min_ok=8, o 6 en lejanas con el preset).
  - Radio máximo de asignación (ej. 1000–1200 m).
  - Exclusión de paradas demasiado cerca de la oficina.
- Con esas reglas, **no es posible** asignar a shuttle a empleados que están solos o en grupos muy pequeños dentro del radio: no forman cluster válido. Eso no es un fallo del algoritmo; es que el problema está mal condicionado para alta cobertura shuttle con esta dispersión.

El mapa lo refleja: muchas zonas con puntos rojos (excluidos) sin parada azul cerca. No es que el algoritmo “no los vea”; es que **no hay suficiente densidad** allí para abrir una parada que cumpla las reglas.

Por tanto: **sí hay limitaciones estructurales**. Con esta masa dispersa y las reglas actuales, una cobertura shuttle del orden 25–40% es lo que cabe esperar. Subir mucho más exigiría relajar bastante reglas (p. ej. paradas de 4–5 personas, radios mayores) o tener datos más densos.

---

## 4. ¿Algo diferente?

Posibles matices (no cambian el diagnóstico principal):

- **Umbral de “nivel” 85%:** Está pensado para escenarios más densos. Con este dataset, ese umbral es poco realista; el “FAIL” de nivel indica “no se alcanza 85%”, no “el motor está roto”.
- **Carpool como complemento:** Los 359 excluidos del shuttle son candidatos a carpool/otras soluciones. El sistema está diseñado para que shuttle + carpool cubran; la cobertura shuttle sola no tiene por qué ser alta en entornos dispersos.

---

## Resumen en una tabla

| Hipótesis | ¿Es la causa del 28%? | Evidencia |
|-----------|------------------------|-----------|
| **Algoritmo incorrecto** | **No** | V4 y V6 coinciden; mapa coherente con la lógica. |
| **Parámetros incorrectos** | **Parcial** | Son conservadores; el preset `--coverage` puede mejorar algo, pero no hace milagros con esta dispersión. |
| **Limitaciones de los datos (masa dispersa)** | **Sí, principal** | Poca densidad (13% con 8+ vecinos en 1 km); las reglas no permiten paradas donde no hay masa crítica. |
| **Algo diferente** | **Secundario** | Umbral 85% poco realista aquí; carpool cubre el resto. |

---

## Qué hacer en la práctica

1. **No buscar un “bug” en el algoritmo:** El comportamiento es el esperado dado V4 y el diseño.
2. **Probar preset cobertura:** Ejecutar con `--coverage --map` y comparar KPIs y mapa; verás si ganas unos puntos de cobertura sin relajar mucho las reglas.
3. **Ajustar expectativas para datos dispersos:** Cobertura shuttle 25–40% con min_ok=8 y radio ~1 km es coherente con la geometría; 85% sería razonable solo con datos mucho más densos o reglas más permisivas.
4. **Si necesitas más cobertura shuttle:** Valorar relajar reglas (min_ok más bajo, radio mayor) o asumir que una parte importante irá en carpool y medir KPIs de **shuttle + carpool** juntos.

En una frase: **el algoritmo es correcto, los parámetros son conservadores, y la limitación principal es la dispersión de los datos; el 28% es consecuencia de esa combinación, no de un error único.**
