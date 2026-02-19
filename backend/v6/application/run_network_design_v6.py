"""
Run full V6 network design (Layer A) using Block 4 + Block 5.

Uso (desde raíz del repo):
  python -m backend.v6.application.run_network_design_v6
  python -m backend.v6.application.run_network_design_v6 --map

Flujo:
  census (CSV congelado) →
  Block 4 (paradas shuttle) →
  stops_coords / stops_demands →
  matriz de tiempos D sencilla (Haversine) →
  Block 5 (VRP) →
  rutas shuttle + KPIs estructurales (IOE, rutas, paradas fuera, etc.).
"""

import argparse
import math
from pathlib import Path
from typing import List, Tuple

import numpy as np

from backend.v6.application.config import (
    DEFAULT_OFFICE_LAT,
    DEFAULT_OFFICE_LNG,
    DEFAULT_STRUCTURAL_CONSTRAINTS,
)
from backend.v6.application.shuttle_candidates import (
    block4_clusters_to_shuttle_options,
)
from backend.v6.core.network_design_engine.shuttle_stop_engine import (
    run_shuttle_stop_opening,
)
from backend.v6.core.network_design_engine.shuttle_vrp_engine import (
    VRPResult,
    run_shuttle_vrp,
)
from backend.v6.domain.models import Employee, ShuttleOption


DATA_CSV = (
    Path(__file__).resolve().parent.parent / "data" / "v4_employees_frozen.csv"
)


def _load_employees(csv_path: Path) -> List[Employee]:
    import csv

    employees: List[Employee] = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            employees.append(
                Employee(
                    employee_id=row["employee_id"].strip(),
                    home_lat=float(row["home_lat"]),
                    home_lng=float(row["home_lng"]),
                    willing_driver=False,
                )
            )
    return employees


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia en km entre dos coordenadas (lat, lon)."""
    r = 6371.0
    lat1_r = math.radians(lat1)
    lat2_r = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(
        dlon / 2
    ) ** 2
    c = 2 * math.asin(min(1.0, math.sqrt(a)))
    return r * c


def _build_duration_matrix(
    stops_coords: List[Tuple[float, float]],
    office_lat: float,
    office_lng: float,
    speed_kmh: float = 30.0,
) -> Tuple[np.ndarray, int]:
    """
    Construye D (N×N) en segundos usando Haversine + velocidad constante.

    Convención:
      - N = S + 1, donde S = nº de paradas.
      - Índice de oficina = S.
    """
    S = len(stops_coords)
    N = S + 1
    D = np.zeros((N, N), dtype=float)
    office_idx = S

    # nodos: 0..S-1 = paradas, S = oficina
    all_coords: List[Tuple[float, float]] = stops_coords + [(office_lat, office_lng)]

    for i in range(N):
        for j in range(N):
            if i == j:
                D[i, j] = 0.0
            else:
                lat1, lon1 = all_coords[i]
                lat2, lon2 = all_coords[j]
                dist_km = _haversine_km(lat1, lon1, lat2, lon2)
                # tiempo = distancia / velocidad
                hours = dist_km / max(speed_kmh, 1.0)
                D[i, j] = hours * 3600.0
    return D, office_idx


def _build_map(
    stops: List[ShuttleOption],
    vrp_result: VRPResult,
    office_lat: float,
    office_lng: float,
    out_path: Path,
) -> None:
    """Mapa sencillo de rutas shuttle: líneas rectas entre paradas y oficina."""
    import folium
    import webbrowser

    if not stops:
        print("No hay paradas; no se genera mapa.")
        return

    m = folium.Map(location=[office_lat, office_lng], zoom_start=11)
    folium.Marker(
        [office_lat, office_lng],
        popup="Oficina",
        icon=folium.Icon(color="blue", icon="building"),
    ).add_to(m)

    # índice → coords
    coords = [(s.centroid_lat, s.centroid_lng) for s in stops]

    palette = [
        "red",
        "purple",
        "orange",
        "darkred",
        "darkgreen",
        "black",
        "darkblue",
        "pink",
        "cadetblue",
        "beige",
    ]

    for r_id, seq in enumerate(vrp_result.routes_idx):
        if not seq:
            continue
        color = palette[r_id % len(palette)]
        # paradas en la ruta
        route_coords = [coords[i] for i in seq]
        # líneas entre paradas
        for a, b in zip(route_coords, route_coords[1:]):
            folium.PolyLine(
                [a, b],
                color=color,
                weight=4,
                opacity=0.9,
            ).add_to(m)
        # último tramo hasta oficina (en línea recta)
        folium.PolyLine(
            [route_coords[-1], (office_lat, office_lng)],
            color=color,
            weight=4,
            opacity=0.9,
        ).add_to(m)
        # marcar paradas
        for k, i in enumerate(seq, start=1):
            lat, lng = coords[i]
            folium.CircleMarker(
                (lat, lng),
                radius=9,
                color=color,
                fill=True,
                fill_opacity=0.9,
                weight=2,
                popup=f"Ruta {r_id} · #{k} · {stops[i].estimated_size} emp",
            ).add_to(m)

    for i in vrp_result.unserved_stop_indices:
        lat, lng = coords[i]
        folium.CircleMarker(
            (lat, lng),
            radius=8,
            color="gray",
            fill=True,
            fill_opacity=0.7,
            weight=2,
            popup=f"PARADA FUERA · {stops[i].estimated_size} emp",
        ).add_to(m)

    m.save(str(out_path))
    webbrowser.open(f"file://{out_path.resolve()}")
    print(f"Mapa guardado en: {out_path}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Optimob V6 — Block 4 + Block 5 (network design estructural)"
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=DATA_CSV,
        help="CSV de empleados (por defecto v4_employees_frozen.csv)",
    )
    parser.add_argument(
        "--office-lat",
        type=float,
        default=DEFAULT_OFFICE_LAT,
        help="Latitud oficina",
    )
    parser.add_argument(
        "--office-lng",
        type=float,
        default=DEFAULT_OFFICE_LNG,
        help="Longitud oficina",
    )
    parser.add_argument(
        "--map",
        action="store_true",
        help="Generar mapa Folium con rutas shuttle",
    )
    args = parser.parse_args()

    if not args.csv.exists():
        print(f"ERROR: no existe el CSV {args.csv}")
        return 1

    employees = _load_employees(args.csv)
    print(f"Empleados cargados: {len(employees)} desde {args.csv}")

    constraints = DEFAULT_STRUCTURAL_CONSTRAINTS
    print(
        "Parámetros VRP: "
        f"BUS_CAPACITY={constraints.bus_capacity}, DETOUR_CAP={constraints.detour_cap}, "
        f"BACKFILL_MAX_MIN_PER_PAX={constraints.backfill_max_delta_min}"
    )

    # ---------- Block 4 ----------
    final_clusters, carpool_set = run_shuttle_stop_opening(
        employees, args.office_lat, args.office_lng, constraints
    )
    employees_by_id = {e.employee_id: e for e in employees}
    stops: List[ShuttleOption] = block4_clusters_to_shuttle_options(
        final_clusters, employees_by_id
    )
    print(
        f"Block 4: {len(stops)} paradas shuttle, "
        f"{len(carpool_set)} empleados a carpool (residual)"
    )

    if not stops:
        print("No hay paradas shuttle; no se ejecuta VRP.")
        return 0

    stops_coords = [(s.centroid_lat, s.centroid_lng) for s in stops]
    stops_demands = [s.estimated_size for s in stops]

    # ---------- Matriz de tiempos D (Haversine simple) ----------
    D, office_idx = _build_duration_matrix(
        stops_coords, args.office_lat, args.office_lng
    )

    # ---------- Block 5 ----------
    vrp_result = run_shuttle_vrp(
        stops_demands=stops_demands,
        duration_matrix=D,
        office_index=office_idx,
        constraints=constraints,
    )

    # ---------- KPIs estructurales ----------
    num_routes = len(vrp_result.routes_idx)
    num_served_stops = len(vrp_result.served_stop_indices)
    num_out_stops = len(vrp_result.unserved_stop_indices)
    served_employees = sum(stops_demands[i] for i in vrp_result.served_stop_indices)
    out_employees = sum(stops_demands[i] for i in vrp_result.unserved_stop_indices)

    ioE = (
        100.0
        * served_employees
        / (constraints.bus_capacity * num_routes)
        if num_routes > 0
        else 0.0
    )

    print("\n--- KPIs estructurales (Block 4 + 5) ---")
    print(f"  Rutas shuttle:          {num_routes}")
    print(f"  Paradas servidas:       {num_served_stops}")
    print(f"  Paradas fuera:          {num_out_stops}")
    print(f"  Empleados servidos:     {served_employees}")
    print(f"  Empleados fuera (solo VRP): {out_employees}")
    print(f"  IOE (ocupación efectiva):  {ioE:.1f}%")

    if args.map:
        out_path = Path(__file__).resolve().parent / "network_design_v6_map.html"
        _build_map(stops, vrp_result, args.office_lat, args.office_lng, out_path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

