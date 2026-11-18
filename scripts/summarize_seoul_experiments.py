"""Write a concise, reproducible interpretation of the saved Seoul experiment grid."""

from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "data" / "scenario_refined" / "scenario_experiment_results.csv"
REPORT = ROOT / "docs" / "scenario_comparison_results.md"


def _read_rows() -> list[dict[str, str]]:
    with RESULTS.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _select(
    rows: list[dict[str, str]],
    *,
    alpha: float,
    beta: float,
    distribution: str,
    threshold: str,
    strict: bool,
    order: str | None = None,
) -> list[dict[str, str]]:
    return [
        row for row in rows
        if float(row["eligible_fraction_alpha"]) == alpha
        and float(row["total_capacity_ratio_beta"]) == beta
        and row["capacity_distribution"] == distribution
        and row["maximum_road_distance_km"] == threshold
        and row["strict_geographic_quality"].casefold() == str(strict).casefold()
        and (order is None or row["sender_processing_order"] == order)
    ]


def _kg(value: str) -> str:
    return f"{float(value):,.2f}"


def main() -> None:
    rows = _read_rows()
    if len(rows) != 2160:
        raise ValueError(f"Expected 2,160 scenario rows; found {len(rows)}.")
    differences = [float(row["lp_minus_greedy_kg"]) for row in rows]
    violations = sum(value < -1e-6 for value in differences)
    ties = sum(abs(value) <= 1e-6 for value in differences)
    improvements = len(rows) - ties - violations

    sample_settings = [
        ("5 km", "5"),
        ("15 km", "15"),
        ("Complete network", ""),
    ]
    sample_lines = []
    for label, threshold in sample_settings:
        selected = _select(
            rows,
            alpha=0.10,
            beta=1.0,
            distribution="uniform",
            threshold=threshold,
            strict=False,
        )
        for row in sorted(selected, key=lambda item: item["sender_processing_order"]):
            sample_lines.append(
                "| "
                + " | ".join(
                    (
                        label,
                        row["sender_processing_order"],
                        _kg(row["lp_stage1_optimal_kg"]),
                        _kg(row["greedy_allocated_kg"]),
                        _kg(row["lp_minus_greedy_kg"]),
                        _kg(row["lp_stage2_total_kg_km"]),
                        _kg(row["greedy_total_kg_km"]),
                    )
                )
                + " |"
            )

    full = _select(
        rows,
        alpha=0.10,
        beta=1.0,
        distribution="uniform",
        threshold="",
        strict=False,
        order="sender_id",
    )
    strict_full = _select(
        rows,
        alpha=0.10,
        beta=1.0,
        distribution="uniform",
        threshold="",
        strict=True,
        order="sender_id",
    )
    if len(full) != 1 or len(strict_full) != 1:
        raise ValueError("Could not locate the full-network strict-quality comparison rows.")
    full_row, strict_row = full[0], strict_full[0]
    report = [
        "# Seoul LP and greedy scenario comparison",
        "",
        "This report summarizes the deterministic experiment output in "
        "`data/scenario_refined/scenario_experiment_results.csv`. Every row is a "
        "**hypothetical scenario result**, not a confirmed donation or delivery.",
        "",
        "## Experiment coverage",
        "",
        "- Rows: **2,160** (5 alpha values × 3 beta values × 4 capacity-share "
        "patterns × 6 geographic networks × 2 coordinate-quality modes × 3 greedy orders).",
        "- Alpha values are illustrative (5%, 10%, 20%, 30%, 40%); beta values are "
        "0.50, 1.00, 1.50; thresholds are 5, 10, 15, 20, 25 km plus complete network.",
        f"- Across comparison rows, LP strictly allocated more kg than greedy in "
        f"**{improvements:,}**, tied within 1e-6 kg in **{ties:,}**, and was below "
        f"greedy in **{violations:,}**.",
        "- A negative difference would indicate a model or feasibility defect; zero "
        "violations are expected because Stage 1 is the LP optimum and greedy is "
        "feasible on identical inputs.",
        "- Stage 2 minimizes pairwise kg-km subject to the Stage 1 allocation optimum. "
        "It does not minimize full vehicle-tour distance.",
        "",
        "## Representative comparisons",
        "",
        "The table below uses alpha=10%, beta=1.0, uniform hypothetical receiver "
        "shares, and the non-strict coordinate setting. It compares the named "
        "geographic network and fixed greedy order.",
        "",
        "| Network | Greedy order | LP Stage 1 kg | Greedy kg | LP − greedy kg | LP Stage 2 kg-km | Greedy kg-km |",
        "|---|---|---:|---:|---:|---:|---:|",
        *sample_lines,
        "",
        "## Strict coordinate-quality sensitivity",
        "",
        "For alpha=10%, beta=1.0, uniform shares, complete route network, and "
        "sender-ID greedy order:",
        "",
        "| Geographic quality setting | LP maximum kg | Greedy kg | LP − greedy kg | LP Stage 2 kg-km | Greedy kg-km |",
        "|---|---:|---:|---:|---:|---:|",
        "| All geocoded nodes | "
        + " | ".join(
            _kg(full_row[key])
            for key in (
                "lp_stage1_optimal_kg",
                "greedy_allocated_kg",
                "lp_minus_greedy_kg",
                "lp_stage2_total_kg_km",
                "greedy_total_kg_km",
            )
        )
        + " |",
        "| Strict road-and-house-number matches | "
        + " | ".join(
            _kg(strict_row[key])
            for key in (
                "lp_stage1_optimal_kg",
                "greedy_allocated_kg",
                "lp_minus_greedy_kg",
                "lp_stage2_total_kg_km",
                "greedy_total_kg_km",
            )
        )
        + " |",
        "",
        "The strict filter changes the geographic network by excluding uncertain "
        "geocodes; it does not establish operational donation eligibility. Co-located "
        "businesses with qualifying address evidence remain represented.",
        "",
        "## Interpretation",
        "",
        "LP and greedy use identical supply, capacity, geographic edges, and route "
        "distances for each comparison. The LP can tie or strictly improve total "
        "allocated scenario kilograms depending on constraints and greedy order. "
        "No superiority claim is made for actual Seoul redistribution. Capacity-share "
        "patterns and distance thresholds are assumptions, not NGO capacities or "
        "verified service areas.",
        "",
    ]
    REPORT.write_text("\n".join(report), encoding="utf-8")
    print(f"Wrote {REPORT} from {len(rows)} scenario comparison rows.")
    print(f"Strict improvements={improvements}; ties={ties}; violations={violations}.")


if __name__ == "__main__":
    main()
