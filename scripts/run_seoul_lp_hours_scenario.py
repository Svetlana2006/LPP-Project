"""Run LP and greedy comparisons using daily closes and the 23:00 NGO cutoff."""

from __future__ import annotations

import csv
import sys
from collections import Counter
from datetime import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from food_allocation.baseline import greedy_allocate
from food_allocation.deadline_scenario import apply_pairwise_pickup_windows
from food_allocation.evaluation import calculate_metrics
from food_allocation.scenario_engine import ScenarioParameters, build_seoul_instance
from food_allocation.solver import solve_two_stage_lp

DATA_DIRECTORY = ROOT / "data/scenario_refined"
SCHEDULE_FILE = DATA_DIRECTORY / "seoul_lp_daily_hours_scenario.csv"
OUTPUT_FILE = DATA_DIRECTORY / "seoul_lp_hours_scenario_results.csv"
REPORT_FILE = ROOT / "docs/seoul_lp_hours_scenario.md"
ALPHA = 0.10
BETA = 1.0
AVERAGE_SPEEDS_KMH = (15.0, 20.0, 25.0)
GREEDY_ORDERS = ("sender_id", "fewest_eligible", "largest_supply")
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
NGO_CLOSING_TIME = time(23, 0)


def _read_schedule(path: Path) -> dict[str, dict[str, dict[str, str]]]:
    grouped: dict[str, dict[str, dict[str, str]]] = {
        day: {} for day in WEEKDAYS
    }
    with path.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            day = row["day_of_week"]
            sender_id = row["sender_id"]
            if day not in grouped:
                raise ValueError(f"Unexpected weekday in schedule: {day!r}.")
            if sender_id in grouped[day]:
                raise ValueError(f"Duplicate schedule for {sender_id!r} on {day}.")
            grouped[day][sender_id] = row
    return grouped


def run_scenario(
    schedule_by_day: dict[str, dict[str, dict[str, str]]],
) -> list[dict[str, object]]:
    base = build_seoul_instance(
        ScenarioParameters(
            eligible_fraction_alpha=ALPHA,
            total_capacity_ratio_beta=BETA,
            capacity_distribution="uniform",
            maximum_road_distance_km=None,
        ),
        data_directory=DATA_DIRECTORY,
    )
    sender_ids = {sender.sender_id for sender in base.senders}
    rows: list[dict[str, object]] = []

    for day in WEEKDAYS:
        daily_schedule = schedule_by_day[day]
        if set(daily_schedule) != sender_ids:
            missing = sender_ids - set(daily_schedule)
            extra = set(daily_schedule) - sender_ids
            raise ValueError(
                f"{day} must have exactly one schedule per sender; "
                f"missing={len(missing)}, extra={len(extra)}."
            )
        closing_times = {
            sender_id: time.fromisoformat(record["closing_time_local"])
            for sender_id, record in daily_schedule.items()
        }
        source_count = sum(
            record["schedule_evidence_type"] == "SOURCE_LOOKUP"
            for record in daily_schedule.values()
        )
        assumption_count = len(daily_schedule) - source_count

        for speed in AVERAGE_SPEEDS_KMH:
            instance = apply_pairwise_pickup_windows(
                base,
                closing_times,
                average_speed_kmh=speed,
                receiver_closing_time=NGO_CLOSING_TIME,
            )
            lp_result = solve_two_stage_lp(instance)
            lp_metrics = calculate_metrics(instance, lp_result.stage1)
            for order in GREEDY_ORDERS:
                greedy_result = greedy_allocate(instance, order)
                greedy_metrics = calculate_metrics(instance, greedy_result)
                delta = lp_result.stage1_optimal_kg - greedy_result.objective_kg
                if delta < -1e-6:
                    raise AssertionError(
                        "Optimal LP allocated less than a feasible greedy result "
                        f"on identical constraints ({day}, {speed:g} km/h, {order})."
                    )
                rows.append(
                    {
                        "scenario_id": (
                            f"seoul-lp-hours-{day.lower()}-{speed:g}-{order}"
                        ),
                        "collection_day": day,
                        "schedule_source_policy": (
                            "matched Google daily close when available; otherwise "
                            "user-assumed 21:00"
                        ),
                        "ngo_latest_arrival_local": NGO_CLOSING_TIME.strftime("%H:%M"),
                        "sender_count": len(base.senders),
                        "source_lookup_sender_day_count": source_count,
                        "assumed_sender_day_count": assumption_count,
                        "eligible_fraction_alpha": ALPHA,
                        "total_capacity_ratio_beta": BETA,
                        "assumed_average_speed_kmh": speed,
                        "sender_processing_order": order,
                        "ngo_cutoff_feasible_pair_count": sum(
                            pair.eligible for pair in instance.pairs
                        ),
                        "lp_max_allocated_kg": lp_result.stage1_optimal_kg,
                        "greedy_allocated_kg": greedy_result.objective_kg,
                        "lp_minus_greedy_kg": delta,
                        "lp_stage2_total_kg_km": lp_result.stage2_total_kg_km,
                        "greedy_total_kg_km": greedy_metrics[
                            "allocated_distance_kg_km"
                        ],
                        "lp_unallocated_scenario_supply_kg": (
                            float(lp_metrics["eligible_supply_kg"])
                            - lp_result.stage1_optimal_kg
                        ),
                        "greedy_unallocated_scenario_supply_kg": (
                            float(greedy_metrics["eligible_supply_kg"])
                            - greedy_result.objective_kg
                        ),
                        "evidence_type": "HYPOTHETICAL_HOURS_AND_CAPACITY_SCENARIO",
                    }
                )
    return rows


def _write_results(rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError("No LP scenario results were generated.")
    with OUTPUT_FILE.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _write_report(rows: list[dict[str, object]]) -> None:
    deltas = [float(row["lp_minus_greedy_kg"]) for row in rows]
    wins = sum(delta > 1e-6 for delta in deltas)
    ties = sum(abs(delta) <= 1e-6 for delta in deltas)
    greedy_wins = sum(delta < -1e-6 for delta in deltas)
    day_counts: Counter[str] = Counter(
        str(row["collection_day"]) for row in rows
    )
    REPORT_FILE.write_text(
        f"""# Seoul LP hours and NGO cutoff scenario

## Assumptions and hours evidence

This is a hypothetical scenario, not a verified operating plan. Each sender's
collection window starts at its selected closing time and lasts at most two
hours. If a location-matched Google Search/Maps closing-time record exists for
that sender and weekday, that listed time is used. **Every other sender-day is
assigned the user-requested assumed 21:00 close.** The daily inputs, including
evidence labels and the assumption text, are in
[`data/scenario_refined/seoul_lp_daily_hours_scenario.csv`](../data/scenario_refined/seoul_lp_daily_hours_scenario.csv).
The 29 Seoul tourism and six OSM hours texts remain preserved in the source
union, but are not parsed into weekday closing times by this scenario. They
therefore do not silently become verified LP inputs.

All receivers are assumed able to accept delivery up to **23:00**, as
requested. Their actual opening times and actual receiving capacity are not
known. For each sender, pairwise travel is allowed only if estimated direct
travel fits both the restaurant's close-plus-two-hour window and the remaining
time to 23:00. This cutoff can shorten the allowed interval; it does not model
receiver opening time, service time, or a multi-stop tour.

## Other scenario inputs

- {rows[0]['sender_count']} sender records, seven weekdays.
- Illustrative eligible fraction alpha={ALPHA:.0%}; government quantities are
  reported expected food-waste discharge, not edible or donatable surplus.
- Hypothetical total receiver capacity ratio beta={BETA:g}; no additional NGO
  receiving capacity was measured.
- Direct travel time is OSRM pairwise road distance divided by assumed average
  speed ({', '.join(map(str, AVERAGE_SPEEDS_KMH))} km/h); it is not live ETA.

## Results

Ran {len(rows)} comparisons (weekday × speed × greedy order). LP allocated
strictly more than greedy in {wins}, tied in {ties}, and greedy allocated more
in {greedy_wins}. LP Stage 1 is optimal and greedy is feasible on the same
instance, so LP cannot allocate less; ties are expected and strict improvement
is data-dependent. These results belong only to this assumption-driven
scenario and do not establish that the real system will perform similarly.

Daily comparison counts: {', '.join(f'{day}={day_counts[day]}' for day in WEEKDAYS)}.

Detailed output:
[`data/scenario_refined/seoul_lp_hours_scenario_results.csv`](../data/scenario_refined/seoul_lp_hours_scenario_results.csv)
""",
        encoding="utf-8",
    )


def main() -> None:
    schedule = _read_schedule(SCHEDULE_FILE)
    rows = run_scenario(schedule)
    _write_results(rows)
    _write_report(rows)
    print(f"Wrote {len(rows)} LP/greedy comparisons to {OUTPUT_FILE}.")
    print(f"Wrote the scenario report to {REPORT_FILE}.")
    print(
        f"Compared all {len(schedule[WEEKDAYS[0]])} senders across "
        f"{len(WEEKDAYS)} weekdays."
    )


if __name__ == "__main__":
    main()
