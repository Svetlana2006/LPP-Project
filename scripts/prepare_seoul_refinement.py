"""Prepare provenance-preserving inputs and audits for Seoul scenario v2."""

from __future__ import annotations

import csv
import math
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
PROCESSED = DATA / "processed"
SCENARIO = DATA / "scenario"
REFINED = DATA / "scenario_refined"
REPORTS = DATA / "reports"
EXACT_QUALITY = "road_and_house_number_match_in_Seoul"
ALPHAS = (0.05, 0.10, 0.20, 0.30, 0.40)
CAPACITY_DISTRIBUTIONS = (
    "uniform",
    "linear_rank",
    "quadratic_rank",
    "concentrated_75_percent_first",
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"Refusing to write an empty CSV: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def percentile(sorted_values: list[float], quantile: float) -> float:
    index = (len(sorted_values) - 1) * quantile
    lower = int(index)
    upper = min(lower + 1, len(sorted_values) - 1)
    fraction = index - lower
    return sorted_values[lower] + (
        sorted_values[upper] - sorted_values[lower]
    ) * fraction


def distribution_row(label: str, values: list[float]) -> dict[str, object]:
    if not values:
        raise ValueError(f"No quantities found for {label}.")
    ordered = sorted(values)
    q1 = percentile(ordered, 0.25)
    q3 = percentile(ordered, 0.75)
    upper_fence = q3 + 1.5 * (q3 - q1)
    row: dict[str, object] = {
        "population": label,
        "record_count": len(ordered),
        "minimum_kg_month": min(ordered),
        "maximum_kg_month": max(ordered),
        "mean_kg_month": mean(ordered),
        "median_kg_month": median(ordered),
        "q1_kg_month": q1,
        "q3_kg_month": q3,
        "tukey_upper_fence_kg_month": upper_fence,
        "above_tukey_fence_count": sum(value > upper_fence for value in ordered),
    }
    for label_q, quantile in (
        ("p05", 0.05),
        ("p10", 0.10),
        ("p25", 0.25),
        ("p50", 0.50),
        ("p75", 0.75),
        ("p90", 0.90),
        ("p95", 0.95),
        ("p99", 0.99),
        ("p99_9", 0.999),
    ):
        row[f"{label_q}_kg_month"] = percentile(ordered, quantile)
    return row


def _quantity(row: dict[str, str]) -> float:
    value = float(row["raw_reported_discharge_quantity"])
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"Invalid source waste quantity for {row.get('observation_id')}.")
    return value


def prepare_sender_observations() -> list[dict[str, object]]:
    observations = read_csv(
        PROCESSED / "korea_seoul_restaurant_waste_observations.csv"
    )
    source_by_id = {row["observation_id"]: row for row in observations}
    sender_rows = read_csv(SCENARIO / "senders.csv")
    output = []
    for sender in sender_rows:
        source = source_by_id[sender["sender_id"]]
        output.append(
            {
                "sender_id": sender["sender_id"],
                "business_name_original_ko": source["business_name"],
                "address_original_ko": source["road_address"] or source["lot_address"],
                "administrative_locality_original_ko": source["administrative_locality"],
                "reported_expected_waste_kg_month": _quantity(source),
                "quantity_definition": (
                    "Government PROD_QTY expected food-waste discharge, kg/month; "
                    "not measured edible or donatable surplus."
                ),
                "source_reference_date": source["source_reference_date"],
                "source_id": source["source_id"],
                "source_url": source["source_url"],
                "snapshot_date": source["snapshot_date"],
            }
        )
    write_csv(REFINED / "sender_observations.csv", output)
    return output


def prepare_distribution_audit(
    sender_observations: list[dict[str, object]],
) -> None:
    nationwide = read_csv(PROCESSED / "korea_restaurant_waste_observations.csv")
    seoul_original = read_csv(
        PROCESSED / "korea_seoul_restaurant_waste_observations.csv"
    )
    populations = (
        (
            "nationwide restaurant-classified source records",
            [_quantity(row) for row in nationwide],
        ),
        (
            "Seoul restaurant source records before deduplication",
            [_quantity(row) for row in seoul_original],
        ),
        (
            "deduplicated Seoul scenario senders",
            [float(row["reported_expected_waste_kg_month"]) for row in sender_observations],
        ),
    )
    write_csv(
        REPORTS / "seoul_reported_waste_distribution.csv",
        [distribution_row(label, values) for label, values in populations],
    )
    review_rows = []
    review_populations = (
        (
            "nationwide restaurant-classified source records",
            [
                (
                    _quantity(row),
                    row["observation_id"],
                    row["business_name"],
                )
                for row in nationwide
            ],
        ),
        (
            "Seoul restaurant source records before deduplication",
            [
                (
                    _quantity(row),
                    row["observation_id"],
                    row["business_name"],
                )
                for row in seoul_original
            ],
        ),
        (
            "deduplicated Seoul scenario senders",
            [
                (
                    float(row["reported_expected_waste_kg_month"]),
                    str(row["sender_id"]),
                    str(row["business_name_original_ko"]),
                )
                for row in sender_observations
            ],
        ),
    )
    for population, population_values in review_populations:
        stats = distribution_row(
            population, [value for value, _, _ in population_values]
        )
        upper_fence = float(stats["tukey_upper_fence_kg_month"])
        for value, observation_id, business_name in sorted(
            population_values, key=lambda item: (-item[0], item[1])
        )[:50]:
            review_rows.append(
                {
                    "population": population,
                    "sender_or_observation_id": observation_id,
                    "reported_expected_waste_kg_month": value,
                    "business_name_original_ko": business_name,
                    "above_tukey_upper_fence": value > upper_fence,
                    "review_note": (
                        "Statistical screening flag only; not evidence that the source value is wrong."
                    ),
                }
            )
    write_csv(REPORTS / "seoul_large_reported_quantities_review.csv", review_rows)

    shares_rows = []
    receivers = read_csv(SCENARIO / "receivers.csv")
    ordered_ids = sorted(row["receiver_id"] for row in receivers)
    count = len(ordered_ids)
    for distribution in CAPACITY_DISTRIBUTIONS:
        if distribution == "uniform":
            weights = [1.0] * count
        elif distribution == "linear_rank":
            weights = [float(rank) for rank in range(1, count + 1)]
        elif distribution == "quadratic_rank":
            weights = [float(rank * rank) for rank in range(1, count + 1)]
        else:
            weights = [0.75] + [0.25 / (count - 1)] * (count - 1)
        total = sum(weights)
        for receiver_id, weight in zip(ordered_ids, weights):
            shares_rows.append(
                {
                    "capacity_distribution": distribution,
                    "receiver_id": receiver_id,
                    "receiver_capacity_share_qj": weight / total,
                    "evidence_type": "SCENARIO",
                    "assumption_note": (
                        "Illustrative share rule only; not an observed NGO capacity share."
                    ),
                }
            )
    write_csv(REFINED / "receiver_capacity_shares.csv", shares_rows)

    supply_rows = []
    for alpha in ALPHAS:
        for row in sender_observations:
            reported = float(row["reported_expected_waste_kg_month"])
            supply_rows.append(
                {
                    "sender_id": row["sender_id"],
                    "reported_expected_waste_kg_month": reported,
                    "eligible_fraction_alpha": alpha,
                    "scenario_supply_s_i_kg_month": reported * alpha,
                    "evidence_type": "SCENARIO",
                    "assumption_note": (
                        "Illustrative alpha only; eligible food quantities are not observed."
                    ),
                    "source_id": row["source_id"],
                }
            )
    write_csv(REFINED / "supply_fraction_scenarios.csv", supply_rows)


def _coordinate_groups(
    rows: list[dict[str, str]], latitude_field: str, longitude_field: str
) -> tuple[list[list[dict[str, str]]], int]:
    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    missing = 0
    for row in rows:
        latitude = row.get(latitude_field, "")
        longitude = row.get(longitude_field, "")
        if not latitude or not longitude:
            missing += 1
            continue
        groups[(latitude, longitude)].append(row)
    return [items for items in groups.values() if len(items) > 1], missing


def prepare_route_audit() -> None:
    geocoding = read_csv(PROCESSED / "seoul_osm_geocoding.csv")
    locations = read_csv(PROCESSED / "seoul_osm_routed_locations.csv")
    pairs = read_csv(SCENARIO / "eligibility_matrix.csv")
    quality_counts = Counter(row["match_quality"] for row in geocoding)
    node_quality_counts = Counter(row["geocoding_match_quality"] for row in locations)
    zero_pairs = [
        row for row in pairs
        if row.get("road_distance_km") and float(row["road_distance_km"]) == 0
    ]
    write_csv(
        REFINED / "zero_distance_pairs.csv",
        [
            {
                "sender_id": row["sender_id"],
                "receiver_id": row["receiver_id"],
                "road_distance_km": row["road_distance_km"],
                "source_id": row["source_id"],
                "review_note": "OSRM returned zero distance; verify coordinates and route result.",
            }
            for row in zero_pairs
        ],
    )

    geocoded_groups, missing_geocoded = _coordinate_groups(
        locations, "geocoded_latitude", "geocoded_longitude"
    )
    snapped_groups, missing_snapped = _coordinate_groups(
        locations, "osrm_snapped_latitude", "osrm_snapped_longitude"
    )
    sender_groups = [
        group for group in geocoded_groups
        if sum(row["node_type"] == "sender" for row in group) > 1
    ]
    receiver_groups = [
        group for group in geocoded_groups
        if sum(row["node_type"] == "receiver" for row in group) > 1
    ]
    mixed_groups = [
        group for group in geocoded_groups
        if any(row["node_type"] == "sender" for row in group)
        and any(row["node_type"] == "receiver" for row in group)
    ]
    snap_values = [
        float(row["osrm_snap_distance_m"])
        for row in locations if row.get("osrm_snap_distance_m")
    ]
    incomplete_fields = (
        "latitude",
        "longitude",
        "osm_type",
        "osm_id",
        "match_quality",
    )
    missing_geo_evidence = {
        field: sum(not row.get(field, "") for row in geocoding)
        for field in incomplete_fields
    }

    lines = [
        "# Seoul route-quality audit",
        "",
        "Route and coordinate results are estimates for scenario analysis, not verified",
        "addresses, donation eligibility, or dispatch routes. The original matrix is",
        "preserved in `data/scenario/eligibility_matrix.csv`.",
        "",
        "## Address-match quality",
        "",
        f"- Unique geocoded address queries: **{len(geocoding):,}**.",
        f"- Road-and-house-number matches: **{quality_counts[EXACT_QUALITY]:,}**.",
        f"- Non-road-and-house-number matches: **{len(geocoding) - quality_counts[EXACT_QUALITY]:,}** "
        f"(partial={quality_counts['partial_address_match_in_Seoul']}, "
        f"approximate Seoul={quality_counts['approximate_Seoul_match']}, "
        f"street-only={quality_counts['street_only_approximation']}).",
        f"- Scenario node rows (including repeated addresses): **{len(locations):,}**; "
        f"{len(locations) - node_quality_counts[EXACT_QUALITY]:,} have non-exact match labels.",
        f"- Node-level match counts: {dict(sorted(node_quality_counts.items()))}.",
        "- Missing geocoding metadata counts: "
        + ", ".join(
            f"{field}={count:,}" for field, count in missing_geo_evidence.items()
        )
        + ".",
        f"- Missing routed coordinate rows: geocoded={missing_geocoded}, snapped={missing_snapped}.",
        "",
        "## Routes and shared coordinates",
        "",
        f"- Zero-distance sender/receiver pairs: **{len(zero_pairs)}**; see "
        "`data/scenario_refined/zero_distance_pairs.csv` for IDs.",
        f"- Maximum OSRM snap offset: **{max(snap_values):.3f} m**.",
        f"- Repeated geocoded coordinate groups: **{len(geocoded_groups)}** "
        f"({sum(map(len, geocoded_groups))} node rows); groups with multiple senders: "
        f"**{len(sender_groups)}**; groups with multiple receivers: "
        f"**{len(receiver_groups)}**; sender/receiver shared-coordinate groups: "
        f"**{len(mixed_groups)}**.",
        f"- Repeated snapped-coordinate groups: **{len(snapped_groups)}** "
        f"({sum(map(len, snapped_groups))} node rows).",
        "- Shared coordinates are not automatically discarded: distinct businesses can "
        "share a building, mall, or geocoder point. The strict quality scenario excludes "
        "non-road-and-house-number geocodes but retains co-located nodes that meet that rule.",
        "",
        "## Strict geographic-quality scenario",
        "",
        "The strict scenario retains a sender/receiver only when the Photon match is "
        "`road_and_house_number_match_in_Seoul` and OSRM snap metadata exists. An edge "
        "must also satisfy the selected road-distance threshold (or be in the complete "
        "network benchmark). This is a conservative coordinate-quality filter, not "
        "operational donation eligibility. Food-category acceptance, donor acceptance, "
        "receiving hours, actual service areas, restaurant-specific pickup feasibility, "
        "and traffic remain unverified.",
        "",
        "OSRM uses pairwise driving-profile distances. They are not traffic-aware travel "
        "times and do not minimize complete vehicle-tour distance.",
        "",
    ]
    (ROOT / "docs" / "route_quality_audit.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def main() -> None:
    sender_observations = prepare_sender_observations()
    prepare_distribution_audit(sender_observations)
    prepare_route_audit()
    print(f"Prepared {len(sender_observations)} deduplicated Seoul observations.")
    print(f"Wrote refinement inputs and audits under {REFINED}, {REPORTS}, and docs/.")


if __name__ == "__main__":
    main()
