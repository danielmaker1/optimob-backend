"""
Evaluación de la rama actual de shuttle en V6 (generate_shuttle_candidates).

Objetivo: obtener KPIs comparables con Block 4 (run_shuttle_stop_opening).

Uso (desde raíz del repo):
  python -m backend.v6.debug.evaluate_generate_shuttle_v6
  python -m backend.v6.debug.evaluate_generate_shuttle_v6 --map
"""

import argparse
import csv
from pathlib import Path

import numpy as np

from backend.v6.domain.models import Employee
from backend.v6.domain.option import (
    SHUTTLE_CLUSTER_RADIUS_KM,
    ShuttleOption,
    generate_shuttle_candidates,
)

DEFAULT_OFFICE_LAT = 40.4168
DEFAULT_OFFICE_LNG = -3.7038
DEFAULT_CSV = (
    Path(__file__).resolve().parent.parent / "data" / "v4_employees_frozen.csv"
)


def load_employees(csv_path: Path) -> list[Employee]:
    employees: list[Employee] = []
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


def _cluster_radius_m(latlon_list: list[tuple[float, float]]) -> float:
    """Radio en m (max dist entre puntos + 20) para dibujar extensión del cluster."""
    if len(latlon_list) < 2:
        return 50.0
    latlon_arr = np.array(latlon_list)
    lat_rad = np.radians(latlon_arr[:, 0])
    lng_rad = np.radians(latlon_arr[:, 1])
    dlat = lat_rad[:, None] - lat_rad[None, :]
    dlng = lng_rad[:, None] - lng_rad[None, :]
    a = np.sin(dlat / 2) ** 2 + np.cos(lat_rad[:, None]) * np.cos(lat_rad[None, :]) * np.sin(dlng / 2) ** 2
    c = 2 * np.arcsin(np.minimum(1.0, np.sqrt(a)))
    dist_m = 6371000 * c
    return float(np.max(dist_m)) + 20.0


def _build_map(
    employees: list[Employee],
    options: list[ShuttleOption],
    office_lat: float,
    office_lng: float,
    out_path: Path,
    open_browser: bool = True,
) -> None:
    """Genera mapa Folium: empleados (todos asignados a una opción), centroides y círculos."""
    import webbrowser
    import folium
    from branca.element import Element

    employees_by_id = {e.employee_id: e for e in employees}
    m = folium.Map(location=[office_lat, office_lng], zoom_start=11)
    for e in employees:
        folium.CircleMarker(
            location=(e.home_lat, e.home_lng),
            radius=4,
            color="gray",
            fill=True,
            fill_opacity=0.7,
            weight=1,
            popup=e.employee_id,
        ).add_to(m)
    radius_cluster_m = SHUTTLE_CLUSTER_RADIUS_KM * 1000.0
    for i, opt in enumerate(options):
        lat, lng = opt.centroid_lat, opt.centroid_lng
        pts = [
            (employees_by_id[eid].home_lat, employees_by_id[eid].home_lng)
            for eid in opt.employee_ids
        ]
        r_m = _cluster_radius_m(pts)
        folium.CircleMarker(
            location=(lat, lng),
            radius=12,
            color="blue",
            fill=True,
            fill_opacity=0.8,
            weight=2,
            popup=f"Opción {i+1} · n={len(opt.employee_ids)}",
        ).add_to(m)
        folium.Circle(
            location=(lat, lng),
            radius=r_m,
            color="blue",
            fill=False,
            weight=2,
            dash_array="5,5",
        ).add_to(m)
        folium.Circle(
            location=(lat, lng),
            radius=radius_cluster_m,
            color="darkblue",
            fill=False,
            weight=1,
            dash_array="2,4",
        ).add_to(m)
    folium.Marker(
        location=[office_lat, office_lng],
        popup="Oficina",
        icon=folium.Icon(color="green", icon="building", prefix="fa"),
    ).add_to(m)
    legend_html = """
    <div style="position: fixed; bottom: 30px; left: 10px; z-index: 1000; background: white; padding: 10px; border: 2px solid grey; border-radius: 5px;">
    <p><b>Leyenda (generate_shuttle_candidates)</b></p>
    <p><span style="color:gray;">● Gris</span> = Empleados (todos asignados a una opción)</p>
    <p><span style="color:blue;">● Azul</span> = Centroide de opción shuttle</p>
    <p><span style="color:blue;">○ Círculo grueso</span> = Extensión del cluster</p>
    <p><span style="color:darkblue;">○ Círculo fino</span> = Radio de clustering (""" + f"{radius_cluster_m:.0f}" + """ m)</p>
    <p><span style="color:green;">■ Verde</span> = Oficina</p>
    </div>
    """
    m.get_root().html.add_child(Element(legend_html))
    m.save(str(out_path))
    if open_browser:
        webbrowser.open(f"file://{out_path.resolve()}")
    print(f"\nMapa guardado: {out_path}")


def _centroids_meters(options: list[ShuttleOption]) -> np.ndarray:
    """Centroides de opciones shuttle en metros (origen en oficina)."""
    cos_lat = np.cos(np.radians(DEFAULT_OFFICE_LAT))
    ys = np.array([opt.centroid_lat for opt in options])
    xs = np.array([opt.centroid_lng for opt in options])
    y_m = (ys - DEFAULT_OFFICE_LAT) * 111320.0
    x_m = (xs - DEFAULT_OFFICE_LNG) * 111320.0 * cos_lat
    return np.column_stack([y_m, x_m])


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluar generate_shuttle_candidates (rama actual V6)")
    parser.add_argument("--map", action="store_true", help="Generar mapa HTML y abrirlo")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV, help="CSV empleados")
    args = parser.parse_args()

    employees = load_employees(args.csv)
    n = len(employees)
    print(f"Empleados cargados: {n} desde {args.csv}")

    options = generate_shuttle_candidates(employees)
    n_clusters = len(options)
    sizes = [len(opt.employee_ids) for opt in options]

    # Cobertura: generate_shuttle_candidates agrupa a todos los empleados
    assigned_ids = {eid for opt in options for eid in opt.employee_ids}
    coverage_pct = (len(assigned_ids) / n * 100.0) if n else 0.0

    print("\n--- KPIs generate_shuttle_candidates ---")
    print(f"  Clusters:        {n_clusters}")
    print(f"  Cobertura:       {coverage_pct:.1f}%")
    print(
        f"  Tamaño medio:    {float(np.mean(sizes)):.1f} "
        f"(std {float(np.std(sizes)):.1f}, min {min(sizes)}, max {max(sizes)})"
    )

    # Solape entre centroides (usando mismo criterio que SHUTTLE_CLUSTER_RADIUS_KM)
    if n_clusters >= 2:
        Xc = _centroids_meters(options)
        # Radio efectivo de clustering en metros
        assign_radius_m = SHUTTLE_CLUSTER_RADIUS_KM * 1000.0
        overlap_stops = 0
        min_dist = float("inf")
        for i in range(n_clusters):
            for j in range(i + 1, n_clusters):
                d = float(np.linalg.norm(Xc[i] - Xc[j]))
                min_dist = min(min_dist, d)
                if d <= assign_radius_m:
                    overlap_stops += 1
                    break
        print(
            f"  Paradas con solape (otra parada a ≤{assign_radius_m:.0f}m): "
            f"{overlap_stops} de {n_clusters}"
        )
        print(f"  Dist. mínima entre paradas: {min_dist:.0f}m")
    else:
        print("  (Solo hay 0 o 1 cluster; solape no aplicable.)")

    if args.map:
        out_path = Path(__file__).resolve().parent / "generate_shuttle_map.html"
        _build_map(
            employees,
            options,
            DEFAULT_OFFICE_LAT,
            DEFAULT_OFFICE_LNG,
            out_path,
            open_browser=True,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

