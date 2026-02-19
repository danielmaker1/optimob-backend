"""
Evaluación Carpool 6A+6B en V6.

Carga censo, ejecuta Block 4 → carpool_set → 6A (prep) → 6B (match).
Imprime KPIs: MPs, matches, conductores con pax, pax asignados, no asignados.

El CSV congelado no tiene willing_driver; por defecto se asigna un % como conductores (seed fija).
Uso (desde raíz):
  python -m backend.v6.debug.evaluate_carpool_6a_6b_v6
  python -m backend.v6.debug.evaluate_carpool_6a_6b_v6 --pct-drivers 0.4
  python -m backend.v6.debug.evaluate_carpool_6a_6b_v6 --map
"""

import argparse
import csv
from pathlib import Path
from typing import List, Set

from backend.v6.application.config import (
    DEFAULT_OFFICE_LAT,
    DEFAULT_OFFICE_LNG,
    DEFAULT_STRUCTURAL_CONSTRAINTS,
)
from backend.v6.application.shuttle_candidates import get_shuttle_candidates_block4
from backend.v6.core.allocation_engine.carpool_prep_engine import run_carpool_prep
from backend.v6.core.allocation_engine.carpool_match_engine import run_carpool_match
from backend.v6.core.allocation_engine.carpool_time_adapter import HaversineCarpoolAdapter
from backend.v6.domain.constraints import CarpoolMatchConfig
from backend.v6.domain.models import CarpoolMatch, CarpoolPerson, DriverRoute, Employee

DATA_CSV = Path(__file__).resolve().parent.parent / "data" / "v4_employees_frozen.csv"


def _build_carpool_map(
    census: List[CarpoolPerson],
    matches: List[CarpoolMatch],
    driver_routes: List[DriverRoute],
    unmatched: List[str],
    office_lat: float,
    office_lng: float,
    out_path: Path,
    open_browser: bool = True,
) -> None:
    """Mapa: masa de partida (conductores/pax), MPs, asignados (match) vs fuera (unmatched)."""
    import webbrowser
    import folium
    from branca.element import Element

    matched_pax_ids: Set[str] = {m.pax_id for m in matches}
    driver_ids_with_route: Set[str] = {r.driver_id for r in driver_routes}
    # MPs únicos (lat, lng) desde matches
    mp_coords = {(m.id_mp, m.mp_lat, m.mp_lng) for m in matches}
    person_by_id = {p.person_id: p for p in census}

    m = folium.Map(location=[office_lat, office_lng], zoom_start=11)

    # Oficina
    folium.Marker(
        [office_lat, office_lng],
        popup="Oficina",
        icon=folium.Icon(color="green", icon="building", prefix="fa"),
    ).add_to(m)

    # Meeting points
    for id_mp, lat, lng in mp_coords:
        folium.CircleMarker(
            [lat, lng],
            radius=10,
            color="orange",
            fill=True,
            fill_opacity=0.8,
            weight=2,
            popup=id_mp,
        ).add_to(m)

    # Masa de partida: conductores y pasajeros
    for p in census:
        if p.is_driver:
            if p.person_id in driver_ids_with_route:
                color = "blue"
                popup = f"{p.person_id} (conductor, con pax)"
            else:
                color = "lightblue"
                popup = f"{p.person_id} (conductor, sin pax)"
        else:
            if p.person_id in matched_pax_ids:
                color = "green"
                popup = f"{p.person_id} (pax, asignado)"
            elif p.person_id in unmatched:
                color = "red"
                popup = f"{p.person_id} (pax, fuera)"
            else:
                color = "gray"
                popup = f"{p.person_id} (pax)"
        folium.CircleMarker(
            [p.lat, p.lng],
            radius=6,
            color=color,
            fill=True,
            fill_opacity=0.8,
            weight=1,
            popup=popup,
        ).add_to(m)

    # Líneas conductor -> MPs -> oficina (solo primeros MPs de cada ruta para no saturar)
    for route in driver_routes[:15]:
        drv = person_by_id.get(route.driver_id)
        if not drv:
            continue
        pts = [[drv.lat, drv.lng]]
        for id_mp in route.order_mp_ids:
            for _id, lat, lng in mp_coords:
                if _id == id_mp:
                    pts.append([lat, lng])
                    break
        pts.append([office_lat, office_lng])
        if len(pts) >= 2:
            folium.PolyLine(pts, color="darkblue", weight=2, opacity=0.5).add_to(m)

    legend_html = """
    <div style="position: fixed; bottom: 30px; left: 10px; z-index: 1000; background: white; padding: 10px; border: 2px solid grey; border-radius: 5px;">
    <p><b>Carpool 6A+6B</b></p>
    <p><span style="color:blue;">● Azul</span> = Conductor con pax</p>
    <p><span style="color:lightblue;">● Azul claro</span> = Conductor sin pax</p>
    <p><span style="color:green;">● Verde</span> = Pax asignado (match)</p>
    <p><span style="color:red;">● Rojo</span> = Pax fuera (sin match)</p>
    <p><span style="color:gray;">● Gris</span> = Pax (otro)</p>
    <p><span style="color:orange;">○ Naranja</span> = Meeting point</p>
    <p><span style="color:green;">■ Verde</span> = Oficina</p>
    <p>Líneas = rutas conductor → MPs → oficina (hasta 15)</p>
    </div>
    """
    m.get_root().html.add_child(Element(legend_html))
    m.save(str(out_path))
    if open_browser:
        webbrowser.open(f"file://{out_path.resolve()}")
    print(f"Mapa guardado: {out_path}")


def load_employees(csv_path: Path, pct_drivers: float = 0.35, seed: int = 42) -> list[Employee]:
    import random
    rng = random.Random(seed)
    employees: list[Employee] = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            willing_driver = rng.random() < pct_drivers
            employees.append(
                Employee(
                    employee_id=row["employee_id"].strip(),
                    home_lat=float(row["home_lat"]),
                    home_lng=float(row["home_lng"]),
                    willing_driver=willing_driver,
                )
            )
    return employees


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluar Carpool 6A+6B V6")
    parser.add_argument("--csv", type=Path, default=DATA_CSV)
    parser.add_argument("--pct-drivers", type=float, default=0.35, help="Fracción empleados como conductores (CSV sin columna)")
    parser.add_argument("--map", action="store_true", help="Generar mapa HTML (masa partida, match, fuera)")
    args = parser.parse_args()

    if not args.csv.exists():
        print(f"ERROR: no existe {args.csv}")
        return 1

    employees = load_employees(args.csv, pct_drivers=args.pct_drivers)
    print(f"Empleados: {len(employees)} (conductores ~{args.pct_drivers*100:.0f}%)")

    _, carpool_set = get_shuttle_candidates_block4(
        employees, DEFAULT_OFFICE_LAT, DEFAULT_OFFICE_LNG, DEFAULT_STRUCTURAL_CONSTRAINTS
    )
    residual = [e for e in employees if e.employee_id in carpool_set]
    print(f"Residual (carpool_set Block 4): {len(residual)}")

    census = run_carpool_prep(residual, DEFAULT_OFFICE_LAT, DEFAULT_OFFICE_LNG)
    drivers = [p for p in census if p.is_driver]
    pax = [p for p in census if not p.is_driver]
    print(f"6A censo: {len(drivers)} conductores, {len(pax)} pasajeros")

    if not census or not pax:
        print("Sin pasajeros o sin censo; no se ejecuta 6B.")
        return 0

    adapter = HaversineCarpoolAdapter(speed_kmh=30.0)
    config = CarpoolMatchConfig()
    result = run_carpool_match(
        census, DEFAULT_OFFICE_LAT, DEFAULT_OFFICE_LNG, adapter, config
    )

    print("\n--- KPIs Carpool 6B ---")
    print(f"  MPs:                      {result.n_mp}")
    print(f"  Candidatos (tripletas driver,pax,MP viables): {result.n_candidates}")
    print(f"  Matches (driver, pax, MP): {result.n_matches}")
    print(f"  Conductores con ≥1 pax:   {len(result.driver_routes)}")
    print(f"  Pax no asignados:         {result.n_unmatched}")
    print(f"  Tiempo motor (ms):        {result.duration_ms:.0f}")
    if result.unmatched_reasons:
        from collections import Counter
        reasons = Counter(result.unmatched_reasons.values())
        print(f"  Motivos sin match:          {dict(reasons)}")
    if result.driver_routes:
        n_pax_list = [r.n_pax for r in result.driver_routes]
        print(f"  Pax por conductor (min/max/med): {min(n_pax_list)} / {max(n_pax_list)} / {sum(n_pax_list)/len(n_pax_list):.1f}")

    if args.map and census:
        out_path = Path(__file__).resolve().parent / "carpool_6a_6b_map.html"
        _build_carpool_map(
            census,
            result.matches,
            result.driver_routes,
            result.unmatched_pax_ids,
            DEFAULT_OFFICE_LAT,
            DEFAULT_OFFICE_LNG,
            out_path,
            open_browser=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
