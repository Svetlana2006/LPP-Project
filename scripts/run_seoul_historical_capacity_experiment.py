"""Compare the LP and greedy baseline using throughput-weighted scenario capacity."""

from __future__ import annotations

import csv
from pathlib import Path

from food_allocation.baseline import greedy_allocate
from food_allocation.evaluation import calculate_metrics
from food_allocation.models import AllocationInstance, AllocationResult
from food_allocation.scenario_engine import ScenarioParameters, build_seoul_instance
from food_allocation.solver import solve_two_stage_lp


ROOT = Path(__file__).resolve().parents[1]
REFINED = ROOT / "data" / "scenario_refined"
ALPHA = 0.10
BETA = 1.00
DISTANCE_THRESHOLDS_KM: tuple[float | None, ...] = (5, 10, 15, 20, 25, None)
GREEDY_ORDERS = ("sender_id", "fewest_eligible", "largest_supply")
REFERENCE_DISTANCE_KM = 15
TOLERANCE_KG = 1e-6


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"No rows generated for {path}.")
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _capacity_rows(instance: AllocationInstance) -> list[dict[str, object]]:
    operations = {
        row["site_id"]: row
        for row in _read_csv(
            ROOT / "data" / "processed" / "korea_foodbank_seoul_operations_2025.csv"
        )
    }
    total_capacity = sum(receiver.capacity_kg for receiver in instance.receivers)
    total_historical_provision = sum(
        float(row["provision_reported_quantity"])
        for row in operations.values()
        if row["operating_statistics_match_status"] == "EXACT_KOREAN_NAME"
        and row["provision_reported_quantity"]
    )
    rows = []
    for receiver in instance.receivers:
        operation = operations[receiver.receiver_id]
        quantity = (
            float(operation["provision_reported_quantity"])
            if operation["operating_statistics_match_status"] == "EXACT_KOREAN_NAME"
            and operation["provision_reported_quantity"]
            else 0.0
        )
        rows.append(
            {
                "receiver_id": receiver.receiver_id,
                "organization_name_ko": operation["organization_name_ko"],
                "historical_2025_provision_quantity": (
                    quantity if quantity > 0 else ""
                ),
                "historical_quantity_unit": (
                    operation["provision_quantity_unit"]
                    if quantity > 0
                    else "NO_SEPARATE_SEOUL_ROW"
                ),
                "historical_provision_share": (
                    quantity / total_historical_provision
                    if total_historical_provision > 0 and quantity > 0
                    else 0.0
                ),
                "scenario_capacity_kg": receiver.capacity_kg,
                "scenario_capacity_share": (
                    receiver.capacity_kg / total_capacity if total_capacity else 0.0
                ),
                "capacity_evidence_type": receiver.evidence_type,
                "capacity_note": receiver.evidence,
                "source_url": operation["source_url"],
            }
        )
    return rows


def _allocation_rows(
    instance: AllocationInstance, methods: dict[str, AllocationResult]
) -> list[dict[str, object]]:
    distances = {
        (pair.sender_id, pair.receiver_id): pair.road_distance_km
        for pair in instance.pairs
        if pair.eligible
    }
    rows = []
    for method, result in methods.items():
        for (sender_id, receiver_id), quantity in sorted(result.allocations_kg.items()):
            distance = distances[(sender_id, receiver_id)]
            rows.append(
                {
                    "sender_id": sender_id,
                    "receiver_id": receiver_id,
                    "method": method,
                    "allocated_kg": quantity,
                    "road_distance_km": distance,
                    "allocated_kg_km": quantity * float(distance or 0.0),
                    "eligibility_scenario": (
                        f"OSRM road distance <= {REFERENCE_DISTANCE_KM} km"
                    ),
                    "eligible_fraction_alpha": ALPHA,
                    "total_capacity_ratio_beta": BETA,
                    "capacity_distribution": "historical_2025_provision",
                    "evidence_type": "HYPOTHETICAL_SCENARIO",
                }
            )
    return rows


def run_experiment() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    result_rows: list[dict[str, object]] = []
    reference_allocations: list[dict[str, object]] = []
    capacity_exported = False

    for threshold in DISTANCE_THRESHOLDS_KM:
        instance = build_seoul_instance(
            ScenarioParameters(
                eligible_fraction_alpha=ALPHA,
                total_capacity_ratio_beta=BETA,
                capacity_distribution="historical_2025_provision",
                maximum_road_distance_km=threshold,
            ),
            data_directory=REFINED,
        )
        if not capacity_exported:
            _write_csv(REFINED / "historical_provision_weighted_capacities.csv",
                       _capacity_rows(instance))
            capacity_exported = True

        lp = solve_two_stage_lp(instance)
        greedy_results = {
            order: greedy_allocate(instance, order) for order in GREEDY_ORDERS
        }
        lp_stage2_metrics = calculate_metrics(instance, lp.stage2)
        for order, greedy in greedy_results.items():
            greedy_metrics = calculate_metrics(instance, greedy)
            gap = lp.stage1_optimal_kg - greedy.objective_kg
            result_rows.append(
                {
                    "scenario_id": (
                        f"historical-provision-alpha-{ALPHA:g}-beta-{BETA:g}-"
                        f"{threshold if threshold is not None else 'complete'}km-{order}"
                    ),
                    "evidence_type": "HYPOTHETICAL_SCENARIO",
                    "eligible_fraction_alpha": ALPHA,
                    "total_capacity_ratio_beta": BETA,
                    "capacity_distribution": "historical_2025_provision",
                    "maximum_road_distance_km": (
                        "" if threshold is None else threshold
                    ),
                    "geographic_network": (
                        "complete" if threshold is None else "distance_threshold"
                    ),
                    "sender_processing_order": order,
                    "total_scenario_supply_kg": sum(
                        sender.supply_kg for sender in instance.senders
                    ),
                    "total_receiver_capacity_kg": sum(
                        receiver.capacity_kg for receiver in instance.receivers
                    ),
                    "lp_stage1_optimal_kg": lp.stage1_optimal_kg,
                    "lp_stage2_allocated_kg": lp.stage2.objective_kg,
                    "greedy_allocated_kg": greedy.objective_kg,
                    "lp_minus_greedy_kg": gap,
                    "lp_strictly_more_kg": gap > TOLERANCE_KG,
                    "lp_no_worse_in_kg": gap >= -TOLERANCE_KG,
                    "lp_stage2_total_kg_km": lp.stage2_total_kg_km,
                    "lp_stage2_average_km_per_allocated_kg": (
                        lp.stage2_average_km_per_kg
                    ),
                    "greedy_total_kg_km": greedy_metrics["allocated_distance_kg_km"],
                    "greedy_average_km_per_allocated_kg": (
                        greedy_metrics["average_distance_per_allocated_kg"]
                    ),
                    "lp_unallocated_supply_kg": (
                        sum(sender.supply_kg for sender in instance.senders)
                        - lp.stage1_optimal_kg
                    ),
                    "greedy_unallocated_supply_kg": (
                        sum(sender.supply_kg for sender in instance.senders)
                        - greedy.objective_kg
                    ),
                    "distance_and_supply_note": (
                        "Reported waste times alpha is scenario supply; distance "
                        "threshold is assumed geographic eligibility, not verified "
                        "donation acceptance or pickup feasibility."
                    ),
                }
            )
            if threshold == REFERENCE_DISTANCE_KM:
                reference_allocations.extend(
                    _allocation_rows(
                        instance,
                        {
                            "lp_stage2_min_kg_km": lp.stage2,
                            f"greedy_{order}": greedy,
                        },
                    )
                )

    _write_csv(
        REFINED / "historical_provision_weighted_lp_greedy_results.csv",
        result_rows,
    )
    _write_csv(
        REFINED / "historical_provision_weighted_15km_allocations.csv",
        reference_allocations,
    )
    return result_rows, reference_allocations


if __name__ == "__main__":
    results, allocations = run_experiment()
    strict = sum(bool(row["lp_strictly_more_kg"]) for row in results)
    no_worse = sum(bool(row["lp_no_worse_in_kg"]) for row in results)
    print(f"Compared {len(results)} matched LP/greedy cases.")
    print(f"LP strictly allocated more kg in {strict}/{len(results)} cases.")
    print(f"LP was no worse in kg in {no_worse}/{len(results)} cases.")
    print(f"Saved {len(allocations)} detailed 15 km assignment rows.")
