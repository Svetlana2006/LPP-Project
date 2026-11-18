"""Continuous linear-programming allocation and lexicographic distance optimization."""

from scipy.optimize import linprog
from scipy.sparse import coo_matrix, csr_matrix

from food_allocation.models import (
    AllocationInstance,
    AllocationResult,
    TwoStageAllocationResult,
)


FEASIBILITY_TOLERANCE = 1e-8


def _build_constraints(instance: AllocationInstance) -> tuple[csr_matrix, list[float]]:
    senders = instance.senders
    receivers = instance.receivers
    variable_count = len(senders) * len(receivers)
    rows: list[int] = []
    columns: list[int] = []
    for sender_index in range(len(senders)):
        for receiver_index in range(len(receivers)):
            variable_index = sender_index * len(receivers) + receiver_index
            rows.extend((sender_index, len(senders) + receiver_index))
            columns.extend((variable_index, variable_index))

    constraints = coo_matrix(
        ([1.0] * len(rows), (rows, columns)),
        shape=(len(senders) + len(receivers), variable_count),
    ).tocsr()
    limits = [sender.supply_kg for sender in senders] + [
        receiver.capacity_kg for receiver in receivers
    ]
    return constraints, limits


def _bounds(instance: AllocationInstance) -> list[tuple[float, float]]:
    pair_map = {
        (pair.sender_id, pair.receiver_id): pair
        for pair in instance.pairs
    }
    bounds = []
    for sender in instance.senders:
        for receiver in instance.receivers:
            pair = pair_map[(sender.sender_id, receiver.receiver_id)]
            upper_bound = (
                min(sender.supply_kg, receiver.capacity_kg)
                if pair.eligible
                else 0.0
            )
            bounds.append((0.0, upper_bound))
    return bounds


def _allocation_result(
    instance: AllocationInstance, values: list[float], method: str
) -> AllocationResult:
    allocations: dict[tuple[str, str], float] = {}
    receiver_count = len(instance.receivers)
    for sender_index, sender in enumerate(instance.senders):
        for receiver_index, receiver in enumerate(instance.receivers):
            quantity = float(values[sender_index * receiver_count + receiver_index])
            if quantity > 1e-9:
                allocations[(sender.sender_id, receiver.receiver_id)] = quantity
    return AllocationResult(
        allocations,
        sum(allocations.values()),
        "optimal",
        method,
    )


def _solver_options() -> dict[str, float]:
    return {
        "primal_feasibility_tolerance": FEASIBILITY_TOLERANCE,
        "dual_feasibility_tolerance": FEASIBILITY_TOLERANCE,
    }


def solve_lp(instance: AllocationInstance) -> AllocationResult:
    """Maximize allocated kg with supply, capacity, eligibility, and nonnegativity bounds."""

    variable_count = len(instance.senders) * len(instance.receivers)
    if variable_count == 0:
        return AllocationResult({}, 0.0, "optimal", "lp_stage1")

    constraints, limits = _build_constraints(instance)
    result = linprog(
        c=[-1.0] * variable_count,
        A_ub=constraints,
        b_ub=limits,
        bounds=_bounds(instance),
        method="highs",
        options=_solver_options(),
    )
    if not result.success or result.x is None:
        raise RuntimeError(f"LP Stage 1 did not reach an optimum: {result.message}")
    return _allocation_result(instance, result.x, "lp_stage1_max_kg")


def solve_two_stage_lp(instance: AllocationInstance) -> TwoStageAllocationResult:
    """Maximize kilograms, then minimize kg-km without losing the Stage 1 optimum."""

    stage1 = solve_lp(instance)
    variable_count = len(instance.senders) * len(instance.receivers)
    if variable_count == 0 or stage1.objective_kg <= FEASIBILITY_TOLERANCE:
        empty_stage2 = AllocationResult({}, 0.0, "optimal", "lp_stage2_min_kg_km")
        return TwoStageAllocationResult(
            stage1, empty_stage2, stage1.objective_kg, 0.0, None
        )

    pair_map = {
        (pair.sender_id, pair.receiver_id): pair
        for pair in instance.pairs
    }
    distance_objective: list[float] = []
    for sender in instance.senders:
        for receiver in instance.receivers:
            pair = pair_map[(sender.sender_id, receiver.receiver_id)]
            if pair.eligible and pair.road_distance_km is None:
                raise ValueError(
                    "Stage 2 requires a road distance for every eligible pair; "
                    f"missing for {sender.sender_id!r}->{receiver.receiver_id!r}."
                )
            distance_objective.append(
                float(pair.road_distance_km or 0.0) if pair.eligible else 0.0
            )

    constraints, limits = _build_constraints(instance)
    total_allocated = coo_matrix(
        ([1.0] * variable_count, ([0] * variable_count, list(range(variable_count)))),
        shape=(1, variable_count),
    ).tocsr()
    result = linprog(
        c=distance_objective,
        A_ub=constraints,
        b_ub=limits,
        A_eq=total_allocated,
        b_eq=[stage1.objective_kg],
        bounds=_bounds(instance),
        method="highs",
        options=_solver_options(),
    )
    if not result.success or result.x is None:
        raise RuntimeError(
            "LP Stage 2 did not preserve the Stage 1 optimum: "
            f"{result.message}"
        )

    stage2 = _allocation_result(instance, result.x, "lp_stage2_min_kg_km")
    total_kg_km = sum(
        amount * float(pair_map[key].road_distance_km or 0.0)
        for key, amount in stage2.allocations_kg.items()
    )
    return TwoStageAllocationResult(
        stage1=stage1,
        stage2=stage2,
        stage1_optimal_kg=stage1.objective_kg,
        stage2_total_kg_km=total_kg_km,
        stage2_average_km_per_kg=(
            total_kg_km / stage2.objective_kg if stage2.objective_kg > 0 else None
        ),
    )
