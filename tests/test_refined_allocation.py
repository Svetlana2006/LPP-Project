import pytest

from food_allocation.baseline import greedy_allocate
from food_allocation.models import AllocationInstance, PairEligibility, Receiver, Sender
from food_allocation.scenario_engine import (
    ScenarioParameters,
    build_seoul_instance,
    capacity_shares,
    stable_scenario_id,
)
from food_allocation.solver import solve_lp, solve_two_stage_lp


DAY = "2026-11-01"


def sender(sender_id: str, supply: float) -> Sender:
    return Sender(sender_id, supply, DAY, DAY)


def receiver(receiver_id: str, capacity: float) -> Receiver:
    return Receiver(receiver_id, capacity, DAY, DAY)


def pair(sender_id: str, receiver_id: str, distance: float, eligible: bool = True):
    return PairEligibility(
        sender_id,
        receiver_id,
        eligible,
        distance if eligible else None,
        "synthetic scenario edge" if eligible else "",
    )


def test_complete_bipartite_network_allocates_minimum_total_supply_and_capacity():
    senders = (sender("A", 4), sender("B", 6))
    receivers = (receiver("X", 3), receiver("Y", 9))
    pairs = tuple(
        pair(s.sender_id, r.receiver_id, 1)
        for s in senders
        for r in receivers
    )
    result = solve_lp(AllocationInstance(senders, receivers, pairs))
    assert result.objective_kg == pytest.approx(10)


def test_restricted_eligibility_and_unequal_capacities_are_respected():
    instance = AllocationInstance(
        (sender("A", 8), sender("B", 7)),
        (receiver("X", 3), receiver("Y", 9)),
        (
            pair("A", "X", 1),
            pair("A", "Y", 2),
            pair("B", "X", 1),
            pair("B", "Y", 0, False),
        ),
    )
    result = solve_lp(instance)
    assert result.objective_kg == pytest.approx(11)
    assert ("B", "Y") not in result.allocations_kg


@pytest.mark.parametrize(
    "instance",
    [
        AllocationInstance(
            (sender("A", 8),),
            (receiver("X", 0),),
            (pair("A", "X", 1),),
        ),
        AllocationInstance(
            (sender("A", 0),),
            (receiver("X", 8),),
            (pair("A", "X", 1),),
        ),
        AllocationInstance(
            (sender("A", 8),),
            (receiver("X", 8),),
            (pair("A", "X", 0, False),),
        ),
    ],
)
def test_zero_capacity_supply_or_isolated_sender_allocates_nothing(instance):
    assert solve_lp(instance).objective_kg == pytest.approx(0)


def test_isolated_receiver_does_not_create_allocation():
    instance = AllocationInstance(
        (sender("A", 5),),
        (receiver("X", 5), receiver("Y", 9)),
        (pair("A", "X", 1), pair("A", "Y", 1, False)),
    )
    assert solve_lp(instance).objective_kg == pytest.approx(5)
    assert all(receiver_id == "X" for _, receiver_id in solve_lp(instance).allocations_kg)


def test_bottleneck_instance_demonstrates_greedy_order_sensitivity():
    instance = AllocationInstance(
        (sender("A", 10), sender("B", 10)),
        (receiver("X", 10), receiver("Y", 10)),
        (
            pair("A", "X", 1),
            pair("A", "Y", 2),
            pair("B", "X", 1),
            pair("B", "Y", 0, False),
        ),
    )
    lp = solve_lp(instance)
    sender_id_greedy = greedy_allocate(instance, "sender_id")
    fewest_first = greedy_allocate(instance, "fewest_eligible")
    largest_supply = greedy_allocate(instance, "largest_supply")
    assert lp.objective_kg == pytest.approx(20)
    assert sender_id_greedy.objective_kg == pytest.approx(10)
    assert fewest_first.objective_kg == pytest.approx(20)
    assert largest_supply.objective_kg == pytest.approx(10)
    assert lp.objective_kg >= sender_id_greedy.objective_kg


def test_two_stage_lp_preserves_maximum_kg_and_minimizes_kg_km():
    instance = AllocationInstance(
        (sender("A", 10),),
        (receiver("X", 10), receiver("Y", 10)),
        (pair("A", "X", 12), pair("A", "Y", 2)),
    )
    result = solve_two_stage_lp(instance)
    assert result.stage1_optimal_kg == pytest.approx(10)
    assert result.stage2.objective_kg == pytest.approx(10)
    assert result.stage2.allocations_kg == {("A", "Y"): pytest.approx(10)}
    assert result.stage2_total_kg_km == pytest.approx(20)
    assert result.stage2_average_km_per_kg == pytest.approx(2)


def test_two_stage_lp_distance_weighted_solution_is_not_vehicle_tour_distance():
    instance = AllocationInstance(
        (sender("A", 5), sender("B", 5)),
        (receiver("X", 5), receiver("Y", 5)),
        (
            pair("A", "X", 9),
            pair("A", "Y", 2),
            pair("B", "X", 1),
            pair("B", "Y", 8),
        ),
    )
    result = solve_two_stage_lp(instance)
    assert result.stage1.objective_kg == pytest.approx(10)
    assert result.stage2.objective_kg == pytest.approx(10)
    assert result.stage2_total_kg_km == pytest.approx(15)


def test_dynamic_dimensions_conserve_sender_and_receiver_limits():
    senders = tuple(sender(f"S{i}", float(i)) for i in range(1, 6))
    receivers = tuple(receiver(f"R{i}", float(i + 1)) for i in range(1, 4))
    pairs = tuple(
        pair(s.sender_id, r.receiver_id, 1)
        for s in senders
        for r in receivers
    )
    instance = AllocationInstance(senders, receivers, pairs)
    result = solve_two_stage_lp(instance)
    sender_totals = {item.sender_id: 0.0 for item in senders}
    receiver_totals = {item.receiver_id: 0.0 for item in receivers}
    for (sender_id, receiver_id), amount in result.stage2.allocations_kg.items():
        sender_totals[sender_id] += amount
        receiver_totals[receiver_id] += amount
    assert result.stage1.objective_kg == pytest.approx(9)
    assert all(sender_totals[s.sender_id] <= s.supply_kg + 1e-8 for s in senders)
    assert all(receiver_totals[r.receiver_id] <= r.capacity_kg + 1e-8 for r in receivers)


def test_allocation_never_uses_an_ineligible_pair():
    instance = AllocationInstance(
        (sender("A", 5), sender("B", 5)),
        (receiver("X", 5), receiver("Y", 5)),
        (
            pair("A", "X", 1),
            pair("A", "Y", 2, False),
            pair("B", "X", 1, False),
            pair("B", "Y", 2),
        ),
    )
    result = solve_two_stage_lp(instance)
    assert set(result.stage2.allocations_kg) <= {("A", "X"), ("B", "Y")}


def test_capacity_distribution_scenarios_are_normalized_and_deterministic():
    ids = ["R3", "R1", "R2"]
    uniform = capacity_shares(ids, "uniform")
    unequal = capacity_shares(ids, "linear_rank")
    concentrated = capacity_shares(ids, "concentrated_75_percent_first")
    assert sum(uniform.values()) == pytest.approx(1)
    assert sum(unequal.values()) == pytest.approx(1)
    assert sum(concentrated.values()) == pytest.approx(1)
    assert len(set(unequal.values())) == 3
    assert concentrated["R1"] == pytest.approx(0.75)
    assert capacity_shares(ids, "linear_rank") == unequal


def test_historical_provision_capacity_shares_normalize_and_keep_unmatched_sites_zero():
    shares = capacity_shares(
        ["KFB-0001", "KFB-0002", "KFB-0003"],
        "historical_2025_provision",
        {"KFB-0002": 25.0, "KFB-0003": 75.0},
    )
    assert shares == {
        "KFB-0001": 0.0,
        "KFB-0002": pytest.approx(0.25),
        "KFB-0003": pytest.approx(0.75),
    }


def test_historical_provision_capacity_requires_valid_positive_weights():
    with pytest.raises(ValueError, match="requires site-level historical quantities"):
        capacity_shares(["R1"], "historical_2025_provision")
    with pytest.raises(ValueError, match="positive value"):
        capacity_shares(["R1"], "historical_2025_provision", {})
    with pytest.raises(ValueError, match="finite and nonnegative"):
        capacity_shares(
            ["R1"], "historical_2025_provision", {"R1": float("nan")}
        )


def test_scenario_identifier_is_stable_and_parameter_sensitive():
    parameters = {
        "eligible_fraction_alpha": 0.1,
        "total_capacity_ratio_beta": 1.0,
    }
    first = stable_scenario_id(parameters, "sender_id")
    assert first == stable_scenario_id(parameters, "sender_id")
    assert first != stable_scenario_id(parameters, "fewest_eligible")


def test_seoul_scenario_parameters_change_supply_capacity_and_geographic_edges():
    from pathlib import Path

    data_directory = Path(__file__).resolve().parents[1] / "data" / "scenario_refined"
    five_km = build_seoul_instance(
        ScenarioParameters(0.05, 0.5, "uniform", 5.0),
        data_directory=data_directory,
    )
    ten_km = build_seoul_instance(
        ScenarioParameters(0.10, 1.0, "linear_rank", 10.0),
        data_directory=data_directory,
    )
    assert sum(sender.supply_kg for sender in five_km.senders) == pytest.approx(
        0.05 * sum(sender.supply_kg for sender in ten_km.senders) / 0.10
    )
    assert sum(receiver.capacity_kg for receiver in five_km.receivers) == pytest.approx(
        0.5 * sum(sender.supply_kg for sender in five_km.senders)
    )
    assert sum(
        pair.eligible for pair in five_km.pairs
    ) < sum(pair.eligible for pair in ten_km.pairs)
    assert len({receiver.capacity_kg for receiver in five_km.receivers}) == 1
    assert len({receiver.capacity_kg for receiver in ten_km.receivers}) > 1


def test_seoul_historical_provision_weighted_capacities_match_published_shares():
    from pathlib import Path

    from food_allocation.scenario_engine import _read_csv

    data_directory = Path(__file__).resolve().parents[1] / "data" / "scenario_refined"
    instance = build_seoul_instance(
        ScenarioParameters(
            0.10,
            1.0,
            "historical_2025_provision",
            15.0,
        ),
        data_directory=data_directory,
    )
    operations = {
        row["site_id"]: row
        for row in _read_csv(
            data_directory.parent
            / "processed"
            / "korea_foodbank_seoul_operations_2025.csv"
        )
    }
    historical_total = sum(
        float(row["provision_reported_quantity"])
        for row in operations.values()
        if row["operating_statistics_match_status"] == "EXACT_KOREAN_NAME"
    )
    receivers = {receiver.receiver_id: receiver for receiver in instance.receivers}
    supply_total = sum(sender.supply_kg for sender in instance.senders)
    assert len(receivers) == 32
    assert receivers["KFB-0001"].capacity_kg == pytest.approx(0)
    assert sum(receiver.capacity_kg for receiver in receivers.values()) == pytest.approx(
        supply_total
    )
    for receiver_id, row in operations.items():
        if row["operating_statistics_match_status"] == "EXACT_KOREAN_NAME":
            expected_share = (
                float(row["provision_reported_quantity"]) / historical_total
            )
            assert receivers[receiver_id].capacity_kg == pytest.approx(
                supply_total * expected_share
            )
