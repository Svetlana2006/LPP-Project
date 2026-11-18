import pytest

from food_allocation.demo import run_demo


def sample_payload(mode="compare"):
    return {
        "mode": mode,
        "maxDistanceKm": 10,
        "senders": [
            {"id": "s1", "name": "Restaurant 1", "supplyKg": 8, "x": 1, "y": 1},
            {"id": "s2", "name": "Restaurant 2", "supplyKg": 5, "x": 8, "y": 8},
        ],
        "receivers": [
            {"id": "r1", "name": "NGO 1", "capacityKg": 4, "x": 2, "y": 1},
            {"id": "r2", "name": "NGO 2", "capacityKg": 9, "x": 9, "y": 8},
        ],
    }


def test_demo_runs_existing_lp_and_returns_named_allocations():
    result = run_demo(sample_payload("lp"))
    assert result["lp"]["allocatedKg"] == pytest.approx(9)
    assert result["lp"]["stage1OptimalKg"] == pytest.approx(9)
    assert result["lp"]["allocations"]
    assert "greedy" not in result
    assert all(row["senderName"] and row["receiverName"] for row in result["lp"]["allocations"])


def test_demo_comparison_uses_same_input_and_reports_nonnegative_lp_difference():
    result = run_demo(sample_payload())
    assert result["lp"]["allocatedKg"] >= result["greedy"]["allocatedKg"]
    assert result["differenceKg"] == pytest.approx(
        result["lp"]["allocatedKg"] - result["greedy"]["allocatedKg"]
    )
    assert result["greedyOrder"] == "sender_id"


def test_demo_distance_limit_can_make_greedy_order_allocate_less():
    payload = {
        "mode": "compare",
        "maxDistanceKm": 4.5,
        "senders": [
            {"id": "s-01", "name": "Restaurant A", "supplyKg": 10, "x": 3, "y": 5},
            {"id": "s-02", "name": "Restaurant B", "supplyKg": 10, "x": 1, "y": 5},
        ],
        "receivers": [
            {"id": "r-01", "name": "NGO X", "capacityKg": 10, "x": 2, "y": 5},
            {"id": "r-02", "name": "NGO Y", "capacityKg": 10, "x": 7, "y": 5},
        ],
    }
    result = run_demo(payload)
    assert result["lp"]["allocatedKg"] == pytest.approx(20)
    assert result["greedy"]["allocatedKg"] == pytest.approx(10)


def test_seven_restaurant_three_ngo_showcase_has_non_collinear_points():
    payload = {
        "mode": "compare",
        "maxDistanceKm": 4,
        "senders": [
            {"id": "s-01", "name": "Northstar Kitchen", "supplyKg": 10, "x": 3, "y": 7},
            {"id": "s-02", "name": "Olive & Grain", "supplyKg": 10, "x": 2, "y": 7},
            {"id": "s-03", "name": "Eastside Kitchen", "supplyKg": 5, "x": 0, "y": 0},
            {"id": "s-04", "name": "Market Café", "supplyKg": 5, "x": 2, "y": 1},
            {"id": "s-05", "name": "Green Table", "supplyKg": 5, "x": 4, "y": 0},
            {"id": "s-06", "name": "Corner Bakery", "supplyKg": 5, "x": 6, "y": 1},
            {"id": "s-07", "name": "River Deli", "supplyKg": 5, "x": 8, "y": 2},
        ],
        "receivers": [
            {"id": "r-01", "name": "Harbor Food Bank", "capacityKg": 10, "x": 4, "y": 7},
            {"id": "r-02", "name": "Community Pantry", "capacityKg": 10, "x": 6, "y": 9},
            {"id": "r-03", "name": "Neighborhood Hub", "capacityKg": 5, "x": 9, "y": 5},
        ],
    }
    result = run_demo(payload)
    assert result["lp"]["allocatedKg"] == pytest.approx(25)
    assert result["greedy"]["allocatedKg"] == pytest.approx(15)
    assert result["differenceKg"] == pytest.approx(10)
    assert len(payload["senders"]) == 7
    assert len(payload["receivers"]) == 3


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda data: data.update({"senders": []}), "at least one sender"),
        (lambda data: data["senders"][0].update({"supplyKg": -1}), "finite and at least 0"),
        (lambda data: data["receivers"][0].update({"x": 11}), "between 0 and 10"),
        (lambda data: data["senders"][1].update({"id": "s1"}), "duplicate ID"),
        (lambda data: data.update({"mode": "unknown"}), "mode must be"),
        (lambda data: data.update({"maxDistanceKm": 101}), "cannot exceed 100"),
    ],
)
def test_demo_rejects_invalid_user_inputs(mutate, message):
    payload = sample_payload()
    mutate(payload)
    with pytest.raises(ValueError, match=message):
        run_demo(payload)
