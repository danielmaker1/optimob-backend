# Carpool 6A+6B — Limitaciones y alcance MVP

Documento para equipo y due diligence: qué cubre el MVP y qué se deja para producción completa.

---

## Alcance MVP (frugal e inteligente)

- **Matching greedy** con coste α·walk + β·detour + γ·|ETA−hora_obj| y bonus δ por ocupación.
- **MPs por densidad** (DBSCAN + cluster suave); sin snap a red viaria.
- **Tiempos y distancias:** adapter inyectable; por defecto **Haversine + velocidad constante** (estimado).
- **Observabilidad:** el motor devuelve `CarpoolMatchResult` con métricas (n_mp, n_candidates, n_matches, n_unmatched, duration_ms) y **unmatched_reasons** (no_candidate, trimmed_by_detour, no_drivers, no_mp) para explicar por qué un pax no tiene match.
- **Sin preferencias ni exclusiones** (género, no-match explícito); MVP = mismo cliente/empresa, confianza implícita.
- **Sin ventana horaria** más allá de hora_obj opcional en el coste; capacidad por conductor = cap_efectiva fija en el censo.

---

## Limitaciones conocidas (no implementadas en MVP)

| Limitación | Impacto | Previsto para producción |
|------------|---------|---------------------------|
| Tiempos Haversine (no red real) | Detours y ETAs estimados; pueden desviarse en ciudad | Adapter con OSM o API de tiempos |
| MPs = centroides (sin snap a red) | Punto puede quedar en sitio no accesible a pie | Snap a nodo/arista cuando exista adapter con red |
| Matching greedy (no óptimo global) | Posiblemente menos asignaciones que un matching óptimo | Comparación con assignment óptimo en muestras; documentar gap |
| Sin preferencias / exclusiones | No se pueden expresar “no con X” o reglas de seguridad | Capa de filtrado pre/post match cuando el producto lo exija |
| Sin capacidad “por día” | cap_efectiva fija; no “hoy el conductor tiene 2 plazas” | Extensión del censo o de la capa diaria (Layer B) |

---

## Uso en producción

- Comunicar a usuario/operador que **tiempos y distancias son estimados** hasta que se use un adapter con red real.
- Los **MPs** son puntos de encuentro sugeridos; validar en campo o con snap a red antes de fijarlos en app.
- **unmatched_reasons** permite explicar a un pasajero por qué no hay plaza (“no encontramos conductor con desvío aceptable” vs “recorte por límite de desvío”).

---

*Actualizado con la salida del motor 6B (CarpoolMatchResult y observabilidad frugal).*
