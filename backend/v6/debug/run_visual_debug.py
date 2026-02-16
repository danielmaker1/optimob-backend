"""
V6 visual debug runner. Synthetic employees, run_network_design, visualize, save, open.
No FastAPI. Debug-only. Does not modify engine. Uses real V6 domain (generate_shuttle_candidates).
"""

import random
import webbrowser
from pathlib import Path

from backend.v6.debug.visualize_network import visualize_network
from backend.v6.domain.models import (
    Employee,
    NetworkDesign,
    ShuttleRoute,
    ShuttleStop,
)
from backend.v6.domain.option import generate_shuttle_candidates

BUS_CAPACITY = 50


def run_network_design(employees: list[Employee], week_id: str = "debug") -> NetworkDesign:
    """Build NetworkDesign from real V6 shuttle candidates. No mock."""
    candidates = generate_shuttle_candidates(employees)
    stops = []
    routes = []
    for opt in candidates:
        stops.append(
            ShuttleStop(
                stop_id=opt.option_id,
                lat=opt.centroid_lat,
                lng=opt.centroid_lng,
                employee_ids=list(opt.employee_ids),
            )
        )
        routes.append(
            ShuttleRoute(
                route_id=opt.option_id,
                stop_ids=[opt.option_id],
                employee_ids=list(opt.employee_ids),
                capacity=BUS_CAPACITY,
            )
        )
    return NetworkDesign(
        week_id=week_id,
        stops=stops,
        routes=routes,
        baseline_cost_per_seat=0.0,
    )

OFFICE_LAT = 40.42
OFFICE_LNG = -3.70
RADIUS_KM = 15.0
NUM_EMPLOYEES = 80
SEED = 42


def _generate_synthetic_employees(
    office_lat: float,
    office_lng: float,
    n: int,
    radius_km: float,
    seed: int,
) -> list[Employee]:
    """Simple random points around office (no OSM). One degree ~ 111 km at mid-lat."""
    rng = random.Random(seed)
    employees = []
    deg_per_km = 1.0 / 111.0
    for i in range(n):
        dx = (rng.random() * 2 - 1) * radius_km * deg_per_km
        dy = (rng.random() * 2 - 1) * radius_km * deg_per_km
        lat = office_lat + dx
        lng = office_lng + dy
        employees.append(
            Employee(
                employee_id=f"emp_{i+1}",
                home_lat=lat,
                home_lng=lng,
                willing_driver=rng.random() < 0.3,
            )
        )
    return employees


def main() -> None:
    employees = _generate_synthetic_employees(
        OFFICE_LAT, OFFICE_LNG, NUM_EMPLOYEES, RADIUS_KM, SEED
    )
    network_design = run_network_design(employees, week_id="debug")
    m = visualize_network(network_design, employees)
    out_path = Path(__file__).resolve().parent / "debug_map.html"
    m.save(str(out_path))
    webbrowser.open(f"file://{out_path}")


if __name__ == "__main__":
    main()
