"""
Evaluación Carpool 6A+6B en V6.

Carga censo, ejecuta Block 4 → carpool_set → 6A (prep) → 6B (match).
Imprime KPIs: MPs, matches, conductores con pax, pax asignados, no asignados.

El CSV congelado no tiene willing_driver; por defecto se asigna un % como conductores (seed fija).
Uso (desde raíz):
  python -m backend.v6.debug.evaluate_carpool_6a_6b_v6
  python -m backend.v6.debug.evaluate_carpool_6a_6b_v6 --pct-drivers 0.4
"""

import argparse
import csv
from pathlib import Path

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
from backend.v6.domain.models import Employee

DATA_CSV = Path(__file__).resolve().parent.parent / "data" / "v4_employees_frozen.csv"


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
    matches, driver_routes, unmatched = run_carpool_match(
        census, DEFAULT_OFFICE_LAT, DEFAULT_OFFICE_LNG, adapter, config
    )

    print("\n--- KPIs Carpool 6B ---")
    print(f"  Matches (driver, pax, MP): {len(matches)}")
    print(f"  Conductores con ≥1 pax:   {len(driver_routes)}")
    print(f"  Pax asignados:            {len(matches)}")
    print(f"  Pax no asignados:         {len(unmatched)}")
    if driver_routes:
        n_pax_list = [r.n_pax for r in driver_routes]
        print(f"  Pax por conductor (min/max/med): {min(n_pax_list)} / {max(n_pax_list)} / {sum(n_pax_list)/len(n_pax_list):.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
