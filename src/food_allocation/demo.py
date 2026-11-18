"""Build and run allocations for the interactive, synthetic grid demonstration."""

from __future__ import annotations

import math
from collections.abc import Mapping

from food_allocation.baseline import greedy_allocate
from food_allocation.models import (
    AllocationInstance,
    PairEligibility,
    Receiver,
    Sender,
)
from food_allocation.solver import solve_two_stage_lp


GRID_MAX = 10.0
MAX_GRID_DISTANCE_KM = 100.0
MAX_NODES_PER_KIND = 100
DEMO_EVIDENCE = (
    "User-entered demonstration input; synthetic grid distance, not a road route."
)


def _number(value: object, field: str, *, minimum: float = 0.0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a number.")
    parsed = float(value)
    if not math.isfinite(parsed) or parsed < minimum:
        raise ValueError(f"{field} must be finite and at least {minimum:g}.")
    return parsed


def _nodes(
    payload: Mapping[str, object], key: str, amount_key: str, amount_label: str
) -> list[dict[str, object]]:
    raw_nodes = payload.get(key)
    if not isinstance(raw_nodes, list) or not raw_nodes:
        raise ValueError(f"Add at least one {key[:-1]}.")
    if len(raw_nodes) > MAX_NODES_PER_KIND:
        raise ValueError(f"A maximum of {MAX_NODES_PER_KIND} {key} is supported.")

    nodes: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    for index, raw_node in enumerate(raw_nodes, start=1):
        if not isinstance(raw_node, Mapping):
            raise ValueError(f"{key} item {index} must be an object.")
        node_id = raw_node.get("id")
        name = raw_node.get("name")
        if not isinstance(node_id, str) or not node_id.strip():
            raise ValueError(f"{key} item {index} needs an ID.")
        if node_id in seen_ids:
            raise ValueError(f"{key} contains a duplicate ID.")
        seen_ids.add(node_id)
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"{key} item {index} needs a name.")

        x = _number(raw_node.get("x"), f"{name} X coordinate")
        y = _number(raw_node.get("y"), f"{name} Y coordinate")
        if x > GRID_MAX or y > GRID_MAX:
            raise ValueError(f"{name} coordinates must be between 0 and {GRID_MAX:g}.")

        nodes.append(
            {
                "id": node_id,
                "name": name.strip(),
                "amount": _number(raw_node.get(amount_key), f"{name} {amount_label}"),
                "x": x,
                "y": y,
            }
        )
    return nodes


def _serialize_allocations(
    instance: AllocationInstance, allocations: dict[tuple[str, str], float]
) -> list[dict[str, object]]:
    senders = {sender.sender_id: sender for sender in instance.senders}
    receivers = {receiver.receiver_id: receiver for receiver in instance.receivers}
    pairs = {
        (pair.sender_id, pair.receiver_id): pair for pair in instance.pairs
    }
    return [
        {
            "senderId": sender_id,
            "senderName": senders[sender_id].evidence,
            "receiverId": receiver_id,
            "receiverName": receivers[receiver_id].evidence,
            "amountKg": amount,
            "distanceKm": pairs[(sender_id, receiver_id)].road_distance_km,
        }
        for (sender_id, receiver_id), amount in sorted(allocations.items())
    ]


def run_demo(payload: Mapping[str, object]) -> dict[str, object]:
    """Run the existing two-stage LP and optionally its sender-ID greedy baseline."""
    mode = payload.get("mode", "lp")
    if mode not in ("lp", "compare"):
        raise ValueError("mode must be 'lp' or 'compare'.")
    maximum_distance_km = _number(
        payload.get("maxDistanceKm"), "Maximum grid distance"
    )
    if maximum_distance_km > MAX_GRID_DISTANCE_KM:
        raise ValueError(
            f"Maximum grid distance cannot exceed {MAX_GRID_DISTANCE_KM:g}."
        )

    senders_input = _nodes(payload, "senders", "supplyKg", "supply")
    receivers_input = _nodes(payload, "receivers", "capacityKg", "capacity")

    senders = tuple(
        Sender(
            sender_id=str(node["id"]),
            supply_kg=float(node["amount"]),
            period_start="demo",
            period_end="demo",
            latitude=float(node["y"]),
            longitude=float(node["x"]),
            evidence=str(node["name"]),
            source_id="interactive_grid_demo",
        )
        for node in senders_input
    )
    receivers = tuple(
        Receiver(
            receiver_id=str(node["id"]),
            capacity_kg=float(node["amount"]),
            period_start="demo",
            period_end="demo",
            latitude=float(node["y"]),
            longitude=float(node["x"]),
            evidence=str(node["name"]),
            source_id="interactive_grid_demo",
        )
        for node in receivers_input
    )
    pairs_list: list[PairEligibility] = []
    for sender in senders:
        for receiver in receivers:
            grid_distance_km = math.hypot(
                sender.longitude - receiver.longitude,
                sender.latitude - receiver.latitude,
            )
            eligible = grid_distance_km <= maximum_distance_km
            pairs_list.append(
                PairEligibility(
                    sender_id=sender.sender_id,
                    receiver_id=receiver.receiver_id,
                    eligible=eligible,
                    road_distance_km=grid_distance_km if eligible else None,
                    evidence=DEMO_EVIDENCE,
                    source_id="interactive_grid_demo",
                )
            )
    pairs = tuple(pairs_list)
    pair_distances = {
        (pair.sender_id, pair.receiver_id): pair.road_distance_km for pair in pairs
    }
    instance = AllocationInstance(senders, receivers, pairs)
    result = solve_two_stage_lp(instance)
    response: dict[str, object] = {
        "lp": {
            "allocatedKg": result.stage2.objective_kg,
            "stage1OptimalKg": result.stage1_optimal_kg,
            "kgKm": result.stage2_total_kg_km,
            "allocations": _serialize_allocations(
                instance, result.stage2.allocations_kg
            ),
        },
        "notes": [
            "All entered supply and capacity values are demonstration inputs.",
            "Grid distances are Euclidean proxies, not road routes or travel times.",
            "Pairs beyond the selected maximum grid distance are scenario-ineligible.",
            "The LP maximizes allocated kg, then minimizes grid-distance kg-km.",
        ],
        "maxDistanceKm": maximum_distance_km,
    }

    if mode == "compare":
        greedy = greedy_allocate(instance, "sender_id")
        response["greedy"] = {
            "allocatedKg": greedy.objective_kg,
            "kgKm": sum(
                amount * float(pair_distances[key] or 0.0)
                for key, amount in greedy.allocations_kg.items()
            ),
            "allocations": _serialize_allocations(instance, greedy.allocations_kg),
        }
        response["differenceKg"] = (
            result.stage1_optimal_kg - greedy.objective_kg
        )
        response["greedyOrder"] = "sender_id"
    return response
