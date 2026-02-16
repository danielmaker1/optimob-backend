from backend.v6.domain.objective_function import compute_cost_per_seat, compute_coverage
from backend.v6.domain.constraints import TriggerPolicy

cost = compute_cost_per_seat(10000, 200)
coverage = compute_coverage(250, 200)

policy = TriggerPolicy(
    min_occupancy_threshold=0.7,
    cost_increase_threshold=0.12,
    coverage_threshold=0.85,
    consecutive_days_required=5,
)

print("Cost per seat:", cost)
print("Coverage:", coverage)
