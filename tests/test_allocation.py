import pytest

from food_allocation.baseline import greedy_allocate
from food_allocation.evaluation import calculate_metrics
from food_allocation.models import (
    AllocationInstance,
    PairEligibility,
    Receiver,
    Sender,
)
from food_allocation.solver import solve_lp
from food_allocation.validation import DataValidationError, load_instance


def make_instance() -> AllocationInstance:
    return AllocationInstance(
        senders=(
            Sender("A", 5, "2026-01-01", "2026-01-01"),
            Sender("B", 5, "2026-01-01", "2026-01-01"),
        ),
        receivers=(
            Receiver("X", 5, "2026-01-01", "2026-01-01"),
            Receiver("Y", 5, "2026-01-01", "2026-01-01"),
        ),
        pairs=(
            PairEligibility("A", "X", True, 1.0, "Documented compatible pickup"),
            PairEligibility("A", "Y", True, 2.0, "Documented compatible pickup"),
            PairEligibility("B", "X", True, 1.0, "Documented compatible pickup"),
            PairEligibility("B", "Y", False, None),
        ),
    )


def test_lp_finds_hand_calculated_optimum_and_beats_greedy_when_it_should():
    instance = make_instance()
    greedy = greedy_allocate(instance, "sender_id")
    optimum = solve_lp(instance)

    assert greedy.objective_kg == pytest.approx(5)
    assert optimum.objective_kg == pytest.approx(10)
    assert optimum.objective_kg >= greedy.objective_kg
    assert optimum.allocations_kg[("B", "X")] == pytest.approx(5)
    assert optimum.allocations_kg[("A", "Y")] == pytest.approx(5)


def test_fewest_eligible_first_is_a_supported_greedy_order():
    result = greedy_allocate(make_instance(), "fewest_eligible")
    assert result.objective_kg == pytest.approx(10)


def test_lp_and_greedy_can_tie():
    instance = AllocationInstance(
        senders=(
            Sender("A", 5, "2026-01-01", "2026-01-01"),
            Sender("B", 5, "2026-01-01", "2026-01-01"),
        ),
        receivers=(
            Receiver("X", 5, "2026-01-01", "2026-01-01"),
            Receiver("Y", 5, "2026-01-01", "2026-01-01"),
        ),
        pairs=(
            PairEligibility("A", "X", True, 1, "Compatible"),
            PairEligibility("A", "Y", False, None),
            PairEligibility("B", "X", True, 1, "Compatible"),
            PairEligibility("B", "Y", True, 2, "Compatible"),
        ),
    )

    greedy = greedy_allocate(instance)
    optimum = solve_lp(instance)
    assert greedy.objective_kg == pytest.approx(10)
    assert optimum.objective_kg == pytest.approx(greedy.objective_kg)


def test_five_by_three_fully_connected_case_uses_dynamic_dimensions():
    senders = tuple(
        Sender(f"S{index}", index, "2026-01-01", "2026-01-01")
        for index in range(1, 6)
    )
    receivers = tuple(
        Receiver(f"R{index}", index + 1, "2026-01-01", "2026-01-01")
        for index in range(1, 4)
    )
    pairs = tuple(
        PairEligibility(sender.sender_id, receiver.receiver_id, True, 1.0, "Compatible")
        for sender in senders
        for receiver in receivers
    )
    result = solve_lp(AllocationInstance(senders, receivers, pairs))

    assert result.objective_kg == pytest.approx(9)
    assert len(result.allocations_kg) >= 3


def test_dynamic_dimensions_and_isolated_nodes():
    instance = AllocationInstance(
        senders=(
            Sender("S1", 3, "2026-01-01", "2026-01-01"),
            Sender("S2", 4, "2026-01-01", "2026-01-01"),
            Sender("S3", 9, "2026-01-01", "2026-01-01"),
        ),
        receivers=(
            Receiver("R1", 2, "2026-01-01", "2026-01-01"),
            Receiver("R2", 4, "2026-01-01", "2026-01-01"),
        ),
        pairs=tuple(
            PairEligibility(sender, receiver, eligible, 1 if eligible else None, "Compatible" if eligible else "")
            for sender, receiver, eligible in (
                ("S1", "R1", True),
                ("S1", "R2", False),
                ("S2", "R1", True),
                ("S2", "R2", True),
                ("S3", "R1", False),
                ("S3", "R2", False),
            )
        ),
    )

    result = solve_lp(instance)
    assert result.objective_kg == pytest.approx(6)
    assert len(result.allocations_kg) == 2
    assert all(sender_id != "S3" for sender_id, _ in result.allocations_kg)


def test_zero_receiver_capacity_and_no_eligible_edges():
    instance = AllocationInstance(
        senders=(Sender("S", 8, "2026-01-01", "2026-01-01"),),
        receivers=(Receiver("R", 0, "2026-01-01", "2026-01-01"),),
        pairs=(PairEligibility("S", "R", False, None),),
    )
    assert solve_lp(instance).objective_kg == pytest.approx(0)
    assert greedy_allocate(instance).objective_kg == pytest.approx(0)


def test_solution_conserves_supply_capacity_and_eligibility():
    instance = make_instance()
    result = solve_lp(instance)
    by_sender = {sender.sender_id: 0.0 for sender in instance.senders}
    by_receiver = {receiver.receiver_id: 0.0 for receiver in instance.receivers}
    eligible = {
        (pair.sender_id, pair.receiver_id)
        for pair in instance.pairs
        if pair.eligible
    }
    for pair, amount in result.allocations_kg.items():
        assert pair in eligible
        assert amount >= 0
        by_sender[pair[0]] += amount
        by_receiver[pair[1]] += amount
    assert by_sender["A"] <= 5
    assert by_sender["B"] <= 5
    assert by_receiver["X"] <= 5
    assert by_receiver["Y"] <= 5


def test_metrics_handle_zero_supply_ratio():
    instance = AllocationInstance(
        senders=(Sender("S", 0, "2026-01-01", "2026-01-01"),),
        receivers=(Receiver("R", 1, "2026-01-01", "2026-01-01"),),
        pairs=(PairEligibility("S", "R", False, None),),
    )
    metrics = calculate_metrics(instance, solve_lp(instance))
    assert metrics["allocated_supply_percent"] is None
    assert metrics["average_distance_per_allocated_kg"] is None


def test_upload_requires_complete_explicit_eligibility_matrix():
    senders = """sender_id,eligible_surplus_kg,quantity_unit,period_start,period_end,evidence_type,surplus_evidence,source_id
S,2,kg,2026-01-01,2026-01-01,OBSERVED,scale log,source-1
"""
    receivers = """receiver_id,effective_receiving_capacity_kg,capacity_unit,period_start,period_end,evidence_type,capacity_evidence,source_id
R1,2,kg,2026-01-01,2026-01-01,OBSERVED,confirmed capacity,source-2
R2,2,kg,2026-01-01,2026-01-01,OBSERVED,confirmed capacity,source-2
"""
    pairs = """sender_id,receiver_id,eligible,road_distance_km,eligibility_evidence,source_id
S,R1,true,1,documented,source-3
"""
    with pytest.raises(DataValidationError, match="every possible pair"):
        load_instance(senders, receivers, pairs)


def test_valid_upload_preserves_provenance_and_runs_both_methods():
    senders = """sender_id,eligible_surplus_kg,quantity_unit,period_start,period_end,evidence_type,surplus_evidence,source_id
A,5,kg,2026-01-01,2026-01-01,SCENARIO,synthetic unit test,scenario-1
B,5,kg,2026-01-01,2026-01-01,SCENARIO,synthetic unit test,scenario-1
"""
    receivers = """receiver_id,effective_receiving_capacity_kg,capacity_unit,period_start,period_end,evidence_type,capacity_evidence,source_id
X,5,kg,2026-01-01,2026-01-01,SCENARIO,synthetic unit test,scenario-2
Y,5,kg,2026-01-01,2026-01-01,SCENARIO,synthetic unit test,scenario-2
"""
    pairs = """sender_id,receiver_id,eligible,road_distance_km,eligibility_evidence,source_id
A,X,true,1,synthetic compatible pair,scenario-3
A,Y,true,2,synthetic compatible pair,scenario-3
B,X,true,1,synthetic compatible pair,scenario-3
B,Y,false,,,scenario-3
"""
    instance = load_instance(senders, receivers, pairs)

    assert instance.senders[0].source_id == "scenario-1"
    assert instance.senders[0].evidence_type == "SCENARIO"
    assert greedy_allocate(instance).objective_kg == pytest.approx(5)
    assert solve_lp(instance).objective_kg == pytest.approx(10)


def test_lp_runs_without_route_distances_but_greedy_requires_them():
    senders = """sender_id,eligible_surplus_kg,quantity_unit,period_start,period_end,evidence_type,surplus_evidence,source_id
A,5,kg,2026-01-01,2026-01-31,SCENARIO,scenario supply,scenario-1
"""
    receivers = """receiver_id,effective_receiving_capacity_kg,capacity_unit,period_start,period_end,evidence_type,capacity_evidence,source_id
X,5,kg,2026-01-01,2026-01-31,SCENARIO,scenario capacity,scenario-2
"""
    pairs = """sender_id,receiver_id,eligible,road_distance_km,eligibility_evidence,source_id
A,X,true,,scenario eligibility,scenario-3
"""
    instance = load_instance(senders, receivers, pairs)

    assert solve_lp(instance).objective_kg == pytest.approx(5)
    assert calculate_metrics(instance, solve_lp(instance))[
        "average_distance_per_allocated_kg"
    ] is None
    with pytest.raises(ValueError, match="has no road distance"):
        greedy_allocate(instance)


def test_upload_rejects_waste_values_marked_as_unknown_units():
    senders = """sender_id,eligible_surplus_kg,quantity_unit,period_start,period_end,evidence_type,surplus_evidence,source_id
S,12,tonnes,2026-01-01,2026-01-01,OBSERVED,scale log,source-1
"""
    receivers = """receiver_id,effective_receiving_capacity_kg,capacity_unit,period_start,period_end,evidence_type,capacity_evidence,source_id
R,12,kg,2026-01-01,2026-01-01,OBSERVED,confirmed capacity,source-2
"""
    pairs = """sender_id,receiver_id,eligible,road_distance_km,eligibility_evidence,source_id
S,R,true,2,documented,source-3
"""
    with pytest.raises(DataValidationError, match="quantity_unit must be kg"):
        load_instance(senders, receivers, pairs)


def test_deadline_order_requires_deadline_for_every_sender():
    with pytest.raises(ValueError, match="pickup_deadline"):
        greedy_allocate(make_instance(), "pickup_deadline")
