"""Reproducible, assumption-labeled Seoul supply and capacity scenarios."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path

from food_allocation.models import (
    AllocationInstance,
    PairEligibility,
    Receiver,
    Sender,
)


ALPHA_VALUES = (0.05, 0.10, 0.20, 0.30, 0.40)
BETA_VALUES = (0.50, 1.00, 1.50)
DISTANCE_THRESHOLDS_KM: tuple[float | None, ...] = (5, 10, 15, 20, 25, None)
CAPACITY_DISTRIBUTIONS = (
    "uniform",
    "linear_rank",
    "quadratic_rank",
    "concentrated_75_percent_first",
)
GREEDY_ORDERS = ("sender_id", "fewest_eligible", "largest_supply")
SCENARIO_SEED = 0
EXACT_GEOCODING_QUALITY = "road_and_house_number_match_in_Seoul"


@dataclass(frozen=True)
class ScenarioParameters:
    eligible_fraction_alpha: float
    total_capacity_ratio_beta: float
    capacity_distribution: str
    maximum_road_distance_km: float | None
    strict_geographic_quality: bool = False


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def capacity_shares(
    receiver_ids: list[str],
    distribution: str,
    historical_provision_quantities: dict[str, float] | None = None,
) -> dict[str, float]:
    """Return a deterministic nonnegative q_j vector that sums to one."""
    if not receiver_ids:
        raise ValueError("At least one receiver is required.")
    ordered_ids = sorted(receiver_ids)
    count = len(ordered_ids)
    if distribution == "uniform":
        weights = [1.0] * count
    elif distribution == "linear_rank":
        weights = [float(rank) for rank in range(1, count + 1)]
    elif distribution == "quadratic_rank":
        weights = [float(rank * rank) for rank in range(1, count + 1)]
    elif distribution == "concentrated_75_percent_first":
        if count == 1:
            weights = [1.0]
        else:
            weights = [0.75] + [0.25 / (count - 1)] * (count - 1)
    elif distribution == "historical_2025_provision":
        if historical_provision_quantities is None:
            raise ValueError(
                "historical_2025_provision requires site-level historical quantities."
            )
        unknown_ids = set(historical_provision_quantities) - set(ordered_ids)
        if unknown_ids:
            raise ValueError(
                "Historical provision quantities contain unknown receiver IDs: "
                + ", ".join(sorted(unknown_ids))
            )
        weights = [
            float(historical_provision_quantities.get(receiver_id, 0.0))
            for receiver_id in ordered_ids
        ]
        if any(not math.isfinite(weight) or weight < 0 for weight in weights):
            raise ValueError(
                "Historical provision quantities must be finite and nonnegative."
            )
    else:
        raise ValueError(
            f"Unknown capacity distribution {distribution!r}; "
            f"choose from {(*CAPACITY_DISTRIBUTIONS, 'historical_2025_provision')}."
        )
    total = sum(weights)
    if total <= 0:
        raise ValueError("Capacity distribution weights must sum to a positive value.")
    return {receiver_id: weight / total for receiver_id, weight in zip(ordered_ids, weights)}


def build_seoul_instance(
    parameters: ScenarioParameters,
    *,
    data_directory: Path,
) -> AllocationInstance:
    """Build a scenario; distance edges are geographic proxies, not donation eligibility."""
    alpha = parameters.eligible_fraction_alpha
    beta = parameters.total_capacity_ratio_beta
    if not 0 <= alpha <= 1:
        raise ValueError("eligible_fraction_alpha must be between zero and one.")
    if beta < 0:
        raise ValueError("total_capacity_ratio_beta cannot be negative.")
    if (
        parameters.maximum_road_distance_km is not None
        and parameters.maximum_road_distance_km < 0
    ):
        raise ValueError("maximum_road_distance_km cannot be negative.")

    observation_rows = _read_csv(data_directory / "sender_observations.csv")
    receiver_rows = _read_csv(data_directory.parent / "scenario" / "receivers.csv")
    location_rows = _read_csv(
        data_directory.parent / "processed" / "seoul_osm_routed_locations.csv"
    )
    route_rows = _read_csv(data_directory.parent / "scenario" / "eligibility_matrix.csv")
    locations = {row["node_id"]: row for row in location_rows}
    if not observation_rows or not receiver_rows or not route_rows:
        raise ValueError("Refined sender, receiver, and route inputs must be nonempty.")

    reported_waste = {
        row["sender_id"]: float(row["reported_expected_waste_kg_month"])
        for row in observation_rows
    }
    total_scenario_supply = sum(reported_waste.values()) * alpha
    receiver_ids = [row["receiver_id"] for row in receiver_rows]
    historical_provision_quantities: dict[str, float] | None = None
    if parameters.capacity_distribution == "historical_2025_provision":
        operation_rows = _read_csv(
            data_directory.parent
            / "processed"
            / "korea_foodbank_seoul_operations_2025.csv"
        )
        historical_provision_quantities = {
            row["site_id"]: float(row["provision_reported_quantity"])
            for row in operation_rows
            if row["operating_statistics_match_status"] == "EXACT_KOREAN_NAME"
            and row["provision_reported_quantity"] != ""
        }
    shares = capacity_shares(
        receiver_ids,
        parameters.capacity_distribution,
        historical_provision_quantities,
    )
    senders = tuple(
        Sender(
            sender_id=row["sender_id"],
            supply_kg=reported_waste[row["sender_id"]] * alpha,
            period_start="2026-11-01",
            period_end="2026-11-30",
            latitude=float(locations[row["sender_id"]]["geocoded_latitude"]),
            longitude=float(locations[row["sender_id"]]["geocoded_longitude"]),
            evidence_type="SCENARIO",
            evidence=(
                "Scenario supply = reported expected waste (kg/month) times "
                f"illustrative eligible fraction alpha={alpha:g}; actual edible "
                "and unserved quantities were not observed."
            ),
            source_id=row["source_id"],
        )
        for row in observation_rows
    )
    receivers = tuple(
        Receiver(
            receiver_id=row["receiver_id"],
            capacity_kg=beta * total_scenario_supply * shares[row["receiver_id"]],
            period_start="2026-11-01",
            period_end="2026-11-30",
            latitude=float(locations[row["receiver_id"]]["geocoded_latitude"]),
            longitude=float(locations[row["receiver_id"]]["geocoded_longitude"]),
            evidence_type="SCENARIO",
            evidence=(
                "Hypothetical site capacity from beta * total scenario supply * q_j; "
                f"beta={beta:g}, q distribution={parameters.capacity_distribution}. "
                + (
                    "q_j is normalized from each site's 2025 reported provision "
                    "quantity (unit unstated); sites without a separate 2025 row "
                    "receive zero modeled share. Historical throughput is not "
                    "capacity, and total capacity is hypothetical."
                    if parameters.capacity_distribution
                    == "historical_2025_provision"
                    else "No actual additional NGO receiving capacity was observed."
                )
            ),
            source_id=row["source_id"],
        )
        for row in receiver_rows
    )

    pairs = []
    for row in route_rows:
        distance = float(row["road_distance_km"])
        geographically_close = (
            parameters.maximum_road_distance_km is None
            or distance <= parameters.maximum_road_distance_km
        )
        quality_supported = True
        if parameters.strict_geographic_quality:
            quality_supported = all(
                locations[node_id]["geocoding_match_quality"]
                == EXACT_GEOCODING_QUALITY
                and locations[node_id]["osrm_snap_distance_m"] != ""
                for node_id in (row["sender_id"], row["receiver_id"])
            )
        eligible = geographically_close and quality_supported
        pairs.append(
            PairEligibility(
                sender_id=row["sender_id"],
                receiver_id=row["receiver_id"],
                eligible=eligible,
                road_distance_km=distance,
                evidence=(
                    "SCENARIO geographic_eligibility: "
                    + (
                        f"OSRM driving distance <= "
                        f"{parameters.maximum_road_distance_km:g} km"
                        if parameters.maximum_road_distance_km is not None
                        else "complete route network benchmark"
                    )
                    + (
                        "; both endpoints have road-and-house-number Photon "
                        "matches and OSRM snap metadata"
                        if parameters.strict_geographic_quality
                        else ""
                    )
                    + "; not verified food, donor, service-area, schedule, or "
                    "operational pickup eligibility."
                ),
                source_id="SCENARIO-GEOGRAPHIC-ELIGIBILITY",
            )
        )
    return AllocationInstance(senders, receivers, tuple(pairs))


def stable_scenario_id(parameters: dict[str, object], greedy_order: str) -> str:
    canonical = json.dumps(
        {"parameters": parameters, "greedy_order": greedy_order, "seed": SCENARIO_SEED},
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    return f"seoul-{digest}"


def scale_allocation(result, factor: float):
    """Scale a solution when alpha scales both supply and beta-based capacities."""
    from food_allocation.models import AllocationResult

    return AllocationResult(
        {key: value * factor for key, value in result.allocations_kg.items()},
        result.objective_kg * factor,
        result.status,
        result.method,
    )
