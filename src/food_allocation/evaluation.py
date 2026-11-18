"""Comparable metrics for feasible allocations."""

from food_allocation.models import AllocationInstance, AllocationResult


def calculate_metrics(
    instance: AllocationInstance, result: AllocationResult
) -> dict[str, float | int | None]:
    sender_supply = {sender.sender_id: sender.supply_kg for sender in instance.senders}
    receiver_capacity = {
        receiver.receiver_id: receiver.capacity_kg for receiver in instance.receivers
    }
    distances = {
        (pair.sender_id, pair.receiver_id): pair.road_distance_km
        for pair in instance.pairs
        if pair.eligible
    }
    sender_allocated = {sender_id: 0.0 for sender_id in sender_supply}
    receiver_allocated = {receiver_id: 0.0 for receiver_id in receiver_capacity}
    total_distance_kg = 0.0
    has_missing_distance = False
    for (sender_id, receiver_id), amount in result.allocations_kg.items():
        sender_allocated[sender_id] += amount
        receiver_allocated[receiver_id] += amount
        distance = distances[(sender_id, receiver_id)]
        if distance is not None:
            total_distance_kg += amount * distance
        else:
            has_missing_distance = True

    allocated = result.objective_kg
    total_supply = sum(sender_supply.values())
    total_capacity = sum(receiver_capacity.values())
    return {
        "total_allocated_kg": allocated,
        "eligible_supply_kg": total_supply,
        "allocated_supply_percent": (
            100.0 * allocated / total_supply if total_supply > 0 else None
        ),
        "unallocated_surplus_kg": total_supply - allocated,
        "receiving_capacity_kg": total_capacity,
        "remaining_receiver_capacity_kg": total_capacity - allocated,
        "senders_served": sum(value > 1e-9 for value in sender_allocated.values()),
        "receivers_served": sum(value > 1e-9 for value in receiver_allocated.values()),
        "allocated_distance_kg_km": (
            None if has_missing_distance else total_distance_kg
        ),
        "average_distance_per_allocated_kg": (
            None
            if has_missing_distance
            else (total_distance_kg / allocated if allocated > 0 else None)
        ),
    }
