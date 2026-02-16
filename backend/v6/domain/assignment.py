"""
V6 assignment. Greedy deterministic. No solver.
"""

from backend.v6.domain.models import AssignmentResult, CarpoolOption, ShuttleOption


def solve_assignment(
    shuttle_options: list[tuple[ShuttleOption, float]],
    carpool_options: list[tuple[CarpoolOption, float]],
    all_employee_ids: list[str],
) -> AssignmentResult:
    """
    1. Sort shuttle options by score descending.
    2. Greedily select shuttles that do not overlap employees.
    3. Mark assigned employees.
    4. From remaining, greedily select best carpool options (no overlap).
    5. Return AssignmentResult.
    """
    selected_shuttles: list[ShuttleOption] = []
    selected_carpools: list[CarpoolOption] = []
    assigned: set[str] = set()

    sorted_shuttles = sorted(shuttle_options, key=lambda x: -x[1])
    for opt, _ in sorted_shuttles:
        if any(eid in assigned for eid in opt.employee_ids):
            continue
        selected_shuttles.append(opt)
        for eid in opt.employee_ids:
            assigned.add(eid)

    sorted_carpools = sorted(carpool_options, key=lambda x: -x[1])
    for opt, _ in sorted_carpools:
        driver_and_pax = {opt.driver_id} | set(opt.passenger_ids)
        if any(eid in assigned for eid in driver_and_pax):
            continue
        selected_carpools.append(opt)
        for eid in driver_and_pax:
            assigned.add(eid)

    unassigned = sorted(set(all_employee_ids) - assigned)

    return AssignmentResult(
        selected_shuttles=selected_shuttles,
        selected_carpools=selected_carpools,
        unassigned_employee_ids=unassigned,
    )
