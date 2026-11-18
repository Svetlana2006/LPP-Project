"""Deterministic nearest-eligible-receiver greedy baseline."""

from food_allocation.models import AllocationInstance, AllocationResult


def greedy_allocate(
    instance: AllocationInstance, sender_order: str = "sender_id"
) -> AllocationResult:
    """Allocate to nearest available eligible receivers using an explicit sender order."""

    valid_orders = {
        "sender_id",
        "reverse_sender_id",
        "fewest_eligible",
        "largest_supply",
        "pickup_deadline",
    }
    if sender_order not in valid_orders:
        raise ValueError(f"sender_order must be one of {sorted(valid_orders)}.")

    eligible_by_sender: dict[str, list[tuple[str, float]]] = {
        sender.sender_id: [] for sender in instance.senders
    }
    for pair in instance.pairs:
        if pair.eligible:
            if pair.road_distance_km is None:
                raise ValueError(
                    f"Eligible pair {pair.sender_id!r}->{pair.receiver_id!r} has no road distance."
                )
            eligible_by_sender[pair.sender_id].append(
                (pair.receiver_id, pair.road_distance_km)
            )

    if sender_order == "sender_id":
        ordered_senders = sorted(instance.senders, key=lambda sender: sender.sender_id)
    elif sender_order == "reverse_sender_id":
        ordered_senders = sorted(
            instance.senders,
            key=lambda sender: sender.sender_id,
            reverse=True,
        )
    elif sender_order == "fewest_eligible":
        ordered_senders = sorted(
            instance.senders,
            key=lambda sender: (
                len(eligible_by_sender[sender.sender_id]),
                sender.sender_id,
            ),
        )
    elif sender_order == "largest_supply":
        ordered_senders = sorted(
            instance.senders,
            key=lambda sender: (-sender.supply_kg, sender.sender_id),
        )
    else:
        missing_deadlines = [
            sender.sender_id for sender in instance.senders if not sender.pickup_deadline
        ]
        if missing_deadlines:
            raise ValueError(
                "pickup_deadline order requires a deadline for every sender; missing for "
                + ", ".join(sorted(missing_deadlines))
            )
        ordered_senders = sorted(
            instance.senders,
            key=lambda sender: (sender.pickup_deadline or "", sender.sender_id),
        )

    remaining_capacity = {
        receiver.receiver_id: receiver.capacity_kg for receiver in instance.receivers
    }
    allocations: dict[tuple[str, str], float] = {}
    for sender in ordered_senders:
        remaining_supply = sender.supply_kg
        ranked_receivers = sorted(
            eligible_by_sender[sender.sender_id],
            key=lambda item: (item[1], item[0]),
        )
        for receiver_id, _ in ranked_receivers:
            amount = min(remaining_supply, remaining_capacity[receiver_id])
            if amount > 0:
                allocations[(sender.sender_id, receiver_id)] = amount
                remaining_supply -= amount
                remaining_capacity[receiver_id] -= amount
            if remaining_supply <= 0:
                break

    return AllocationResult(
        allocations,
        sum(allocations.values()),
        "feasible",
        f"greedy:{sender_order}",
    )
