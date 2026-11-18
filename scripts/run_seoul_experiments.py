"""Run the deterministic Seoul scenario grid and save comparable LP/greedy metrics."""

from __future__ import annotations

import csv
import argparse
import itertools
import json
import time
from pathlib import Path

from food_allocation.baseline import greedy_allocate
from food_allocation.evaluation import calculate_metrics
from food_allocation.scenario_engine import (
    ALPHA_VALUES,
    BETA_VALUES,
    CAPACITY_DISTRIBUTIONS,
    DISTANCE_THRESHOLDS_KM,
    GREEDY_ORDERS,
    SCENARIO_SEED,
    ScenarioParameters,
    build_seoul_instance,
    stable_scenario_id,
)
from food_allocation.solver import solve_two_stage_lp


ROOT = Path(__file__).resolve().parents[1]
REFINED = ROOT / "data" / "scenario_refined"


def _write_rows(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"No experiment rows generated for {path}.")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def run_experiments(
    *,
    alpha_values: tuple[float, ...] = ALPHA_VALUES,
    beta_values: tuple[float, ...] = BETA_VALUES,
    distributions: tuple[str, ...] = CAPACITY_DISTRIBUTIONS,
    thresholds_km: tuple[float | None, ...] = DISTANCE_THRESHOLDS_KM,
    strict_quality_values: tuple[bool, ...] = (False, True),
    greedy_orders: tuple[str, ...] = GREEDY_ORDERS,
    batch_index: int = 0,
    batch_count: int = 1,
) -> list[dict[str, object]]:
    """Run one LP per scale-invariant network/capacity configuration.

    All sender supplies and beta-derived receiver capacities scale linearly with
    alpha. Therefore a solve at alpha=1 can be multiplied by each tested alpha
    without changing the feasible allocation proportions or distance ordering.
    """
    rows: list[dict[str, object]] = []
    base_configurations = itertools.product(
        beta_values,
        distributions,
        thresholds_km,
        strict_quality_values,
    )
    configurations = list(base_configurations)
    if batch_count < 1 or not 0 <= batch_index < batch_count:
        raise ValueError("batch_count must be positive and batch_index in range.")
    configurations = configurations[batch_index::batch_count]
    started = time.monotonic()
    for number, (beta, distribution, threshold, strict_quality) in enumerate(
        configurations, start=1
    ):
        base_parameters = ScenarioParameters(
            eligible_fraction_alpha=1.0,
            total_capacity_ratio_beta=beta,
            capacity_distribution=distribution,
            maximum_road_distance_km=threshold,
            strict_geographic_quality=strict_quality,
        )
        base_instance = build_seoul_instance(
            base_parameters,
            data_directory=REFINED,
        )
        lexicographic = solve_two_stage_lp(base_instance)
        greedy_results = {
            order: greedy_allocate(base_instance, order)
            for order in greedy_orders
        }
        lp_stage1_metrics = calculate_metrics(base_instance, lexicographic.stage1)
        lp_stage2_metrics = calculate_metrics(base_instance, lexicographic.stage2)
        greedy_metrics = {
            order: calculate_metrics(base_instance, result)
            for order, result in greedy_results.items()
        }
        total_supply_at_alpha_1 = sum(
            sender.supply_kg for sender in base_instance.senders
        )
        total_capacity_at_alpha_1 = sum(
            receiver.capacity_kg for receiver in base_instance.receivers
        )
        for alpha in alpha_values:
            parameters: dict[str, object] = {
                "eligible_fraction_alpha": alpha,
                "total_capacity_ratio_beta": beta,
                "capacity_distribution": distribution,
                "maximum_road_distance_km": (
                    "complete_network" if threshold is None else threshold
                ),
                "geographic_quality": (
                    "strict_exact_address" if strict_quality else "all_geocoded"
                ),
                "sender_processing_order": None,
                "seed": SCENARIO_SEED,
            }
            for order in greedy_orders:
                configured_parameters = {
                    **parameters,
                    "sender_processing_order": order,
                }
                lp_allocated = float(lp_stage1_metrics["total_allocated_kg"]) * alpha
                greedy_allocated = (
                    float(greedy_metrics[order]["total_allocated_kg"]) * alpha
                )
                stage2_kg_km = lexicographic.stage2_total_kg_km * alpha
                greedy_kg_km = (
                    float(greedy_metrics[order]["allocated_distance_kg_km"] or 0.0)
                    * alpha
                )
                total_supply = total_supply_at_alpha_1 * alpha
                total_capacity = total_capacity_at_alpha_1 * alpha
                rows.append(
                    {
                        "scenario_id": stable_scenario_id(configured_parameters, order),
                        "parameters_json": json.dumps(
                            configured_parameters, sort_keys=True, separators=(",", ":")
                        ),
                        "eligible_fraction_alpha": alpha,
                        "total_capacity_ratio_beta": beta,
                        "capacity_distribution": distribution,
                        "maximum_road_distance_km": (
                            "" if threshold is None else threshold
                        ),
                        "geographic_network": (
                            "complete" if threshold is None else "distance_threshold"
                        ),
                        "strict_geographic_quality": strict_quality,
                        "sender_processing_order": order,
                        "random_seed": SCENARIO_SEED,
                        "result_evidence_type": "HYPOTHETICAL_SCENARIO",
                        "total_scenario_supply_kg": total_supply,
                        "total_receiver_capacity_kg": total_capacity,
                        "lp_stage1_optimal_kg": lp_allocated,
                        "lp_stage2_allocated_kg": (
                            float(lp_stage2_metrics["total_allocated_kg"]) * alpha
                        ),
                        "lp_minus_greedy_kg": lp_allocated - greedy_allocated,
                        "lp_stage2_total_kg_km": stage2_kg_km,
                        "lp_average_km_per_allocated_kg": (
                            lexicographic.stage2_average_km_per_kg
                        ),
                        "greedy_allocated_kg": greedy_allocated,
                        "greedy_total_kg_km": greedy_kg_km,
                        "greedy_average_km_per_allocated_kg": (
                            greedy_kg_km / greedy_allocated
                            if greedy_allocated > 0 else ""
                        ),
                        "lp_unallocated_supply_kg": total_supply - lp_allocated,
                        "greedy_unallocated_supply_kg": total_supply - greedy_allocated,
                        "lp_remaining_receiver_capacity_kg": (
                            total_capacity - lp_allocated
                        ),
                        "greedy_remaining_receiver_capacity_kg": (
                            total_capacity - greedy_allocated
                        ),
                        "solver_configuration_id": (
                            f"beta={beta:g}|{distribution}|"
                            f"{threshold if threshold is not None else 'complete'}|"
                            f"strict={strict_quality}"
                        ),
                    }
                )
        elapsed = time.monotonic() - started
        print(
            f"Completed base configuration {number}/{len(configurations)} "
            f"({elapsed:.1f}s elapsed).",
            flush=True,
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-index", type=int, default=0)
    parser.add_argument("--batch-count", type=int, default=1)
    args = parser.parse_args()
    results = run_experiments(
        batch_index=args.batch_index,
        batch_count=args.batch_count,
    )
    output = (
        REFINED / "scenario_experiment_results.csv"
        if args.batch_count == 1
        else REFINED
        / f"scenario_experiment_results.part-{args.batch_index + 1}-of-{args.batch_count}.csv"
    )
    _write_rows(output, results)
    print(f"Wrote {len(results)} scenario/order rows to {output}.")


if __name__ == "__main__":
    main()
