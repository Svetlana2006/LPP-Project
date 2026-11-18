"""Compare LP and greedy on the location-matched Google-hours subset."""

from __future__ import annotations

import csv
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from food_allocation.baseline import greedy_allocate
from food_allocation.deadline_scenario import (
    apply_pairwise_pickup_windows,
    load_google_closing_times,
)
from food_allocation.evaluation import calculate_metrics
from food_allocation.scenario_engine import ScenarioParameters, build_seoul_instance
from food_allocation.solver import solve_two_stage_lp


DATA_DIRECTORY = ROOT / "data" / "scenario_refined"
HOURS_FILE = DATA_DIRECTORY / "google_restaurant_closing_times.csv"
OUTPUT = DATA_DIRECTORY / "google_closing_time_experiment_results.csv"
REPORT = ROOT / "docs" / "google_closing_time_experiment.md"
ALPHA = 0.10
BETA = 1.0
AVERAGE_SPEEDS_KMH = (15.0, 20.0, 25.0)
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
GREEDY_ORDERS = ("sender_id", "fewest_eligible", "largest_supply")


def main() -> None:
    base = build_seoul_instance(
        ScenarioParameters(
            eligible_fraction_alpha=ALPHA,
            total_capacity_ratio_beta=BETA,
            capacity_distribution="uniform",
            maximum_road_distance_km=None,
        ),
        data_directory=DATA_DIRECTORY,
    )
    source_sender_ids = {sender.sender_id for sender in base.senders}
    rows: list[dict[str, object]] = []
    coverage: dict[str, int] = {}

    for day in WEEKDAYS:
        closing_times, _ = load_google_closing_times(HOURS_FILE, day)
        closing_times = {
            sender_id: close_time
            for sender_id, close_time in closing_times.items()
            if sender_id in source_sender_ids
        }
        coverage[day] = len(closing_times)
        if not closing_times:
            continue

        covered_ids = set(closing_times)
        senders = tuple(
            sender for sender in base.senders if sender.sender_id in covered_ids
        )
        covered_supply = sum(sender.supply_kg for sender in senders)
        full_supply = sum(sender.supply_kg for sender in base.senders)
        capacity_scale = covered_supply / full_supply if full_supply else 0.0
        subset = replace(
            base,
            senders=senders,
            receivers=tuple(
                replace(receiver, capacity_kg=receiver.capacity_kg * capacity_scale)
                for receiver in base.receivers
            ),
            pairs=tuple(pair for pair in base.pairs if pair.sender_id in covered_ids),
        )

        for speed in AVERAGE_SPEEDS_KMH:
            instance = apply_pairwise_pickup_windows(
                subset, closing_times, average_speed_kmh=speed
            )
            lp_result = solve_two_stage_lp(instance)
            for order in GREEDY_ORDERS:
                greedy_result = greedy_allocate(instance, order)
                lp_metrics = calculate_metrics(instance, lp_result.stage1)
                greedy_metrics = calculate_metrics(instance, greedy_result)
                rows.append(
                    {
                        "scenario_id": f"seoul-google-hours-{day.lower()}-{speed:g}-{order}",
                        "collection_day": day,
                        "hours_source": "Google Search/Maps location-matched subset",
                        "matched_sender_count": len(covered_ids),
                        "source_sender_count": len(source_sender_ids),
                        "eligible_fraction_alpha": ALPHA,
                        "total_capacity_ratio_beta": BETA,
                        "assumed_average_speed_kmh": speed,
                        "sender_processing_order": order,
                        "deadline_feasible_pair_count": sum(
                            pair.eligible for pair in instance.pairs
                        ),
                        "lp_max_allocated_kg": lp_result.stage1_optimal_kg,
                        "greedy_allocated_kg": greedy_result.objective_kg,
                        "lp_minus_greedy_kg": (
                            lp_result.stage1_optimal_kg - greedy_result.objective_kg
                        ),
                        "lp_stage2_total_kg_km": lp_result.stage2_total_kg_km,
                        "greedy_total_kg_km": greedy_metrics["allocated_distance_kg_km"],
                        "lp_unallocated_supply_kg": (
                            float(lp_metrics["eligible_supply_kg"])
                            - lp_result.stage1_optimal_kg
                        ),
                        "greedy_unallocated_supply_kg": (
                            float(greedy_metrics["eligible_supply_kg"])
                            - greedy_result.objective_kg
                        ),
                        "evidence_type": "PARTIAL_PUBLIC_HOURS_SCENARIO",
                    }
                )

    if not rows:
        raise ValueError("No location-matched Google closing-time records were found.")
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    REPORT.write_text(
        _report_text(coverage, rows),
        encoding="utf-8",
    )
    print(f"Wrote {len(rows)} LP/greedy comparisons to {OUTPUT}.")
    print(f"Wrote the coverage and limitations report to {REPORT}.")


def _report_text(coverage: dict[str, int], rows: list[dict[str, object]]) -> str:
    deltas = [float(row["lp_minus_greedy_kg"]) for row in rows]
    lp_wins = sum(delta > 1e-6 for delta in deltas)
    ties = sum(abs(delta) <= 1e-6 for delta in deltas)
    greedy_wins = sum(delta < -1e-6 for delta in deltas)
    return f"""# Google closing-time subset experiment

## What this represents

Google Search/Maps closing-time observations were used only where the result matched
the restaurant's listed name/location. For each restaurant, the collection window
starts at its own closing time and ends two hours later (midnight rollovers included).
The restaurant hours file is
[`data/scenario_refined/google_restaurant_closing_times.csv`](../data/scenario_refined/google_restaurant_closing_times.csv).

Hours coverage by day in the current lookup subset:

{chr(10).join(f"- {day}: {count} matched sender records" for day, count in coverage.items())}

The Seoul source contains {rows[0]['source_sender_count']} sender records; only the
small subset with matched hours is evaluated on each day. (Hours are not available for
most restaurants.) Reported monthly food-waste quantities are not edible-food estimates.
The experiment uses illustrative alpha={ALPHA:.0%} and beta={BETA:g}; neither is measured
operational data.

## Travel-time proxy and model scope

Direct travel time is approximated as existing OSRM road distance divided by an assumed
average speed ({', '.join(map(str, AVERAGE_SPEEDS_KMH))} km/h sensitivity). This is not a
Google Maps ETA. Each NGO-to-restaurant pair is checked independently; cumulative
restaurant-to-restaurant travel, multi-stop ordering, loading time, actual traffic, and
confirmed pickup arrangements are not modeled.

The LP and greedy methods receive the same supply, scaled receiver capacities, distances,
and window-feasible edges. Ties are valid; no strict LP advantage is guaranteed.

Across these {len(rows)} partial-data comparisons, LP allocated more in {lp_wins},
they tied in {ties}, and greedy allocated more in {greedy_wins}. These counts apply
only to the stated hours subset and scenario settings.

## Comparison output

See [`data/scenario_refined/google_closing_time_experiment_results.csv`](../data/scenario_refined/google_closing_time_experiment_results.csv)
for each weekday, assumed speed, and greedy order. These are partial, assumption-driven
scenario results, not validated delivery outcomes.
"""


if __name__ == "__main__":
    main()
