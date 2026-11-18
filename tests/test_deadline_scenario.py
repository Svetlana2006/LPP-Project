from dataclasses import replace
from datetime import time

import pytest

from food_allocation.deadline_scenario import (
    apply_pairwise_pickup_windows,
    collection_window_labels,
    load_google_closing_times,
)
from food_allocation.models import (
    AllocationInstance,
    PairEligibility,
    Receiver,
    Sender,
)


def _instance() -> AllocationInstance:
    return AllocationInstance(
        senders=(
            Sender("early", 10, "2026-11-01", "2026-11-30"),
            Sender("late", 10, "2026-11-01", "2026-11-30"),
        ),
        receivers=(
            Receiver("ngo", 20, "2026-11-01", "2026-11-30"),
        ),
        pairs=(
            PairEligibility("early", "ngo", True, 30),
            PairEligibility("late", "ngo", True, 60),
        ),
    )


def test_each_sender_uses_its_own_sourced_close_and_two_hour_window() -> None:
    result = apply_pairwise_pickup_windows(
        _instance(),
        {"early": time(20, 0), "late": time(23, 0)},
        average_speed_kmh=20,
    )
    eligible = {pair.sender_id: pair.eligible for pair in result.pairs}
    assert eligible == {"early": True, "late": False}
    assert "20:00 to 22:00" in result.pairs[0].evidence
    assert "23:00 to 01:00 (next day)" in result.pairs[1].evidence


def test_direct_drive_exactly_two_hours_is_feasible() -> None:
    instance = replace(
        _instance(),
        pairs=(PairEligibility("early", "ngo", True, 40),),
        senders=_instance().senders[:1],
    )
    result = apply_pairwise_pickup_windows(
        instance, {"early": time(20, 0)}, average_speed_kmh=20
    )
    assert result.pairs[0].eligible


def test_ngo_cutoff_shortens_window_for_later_restaurant_close() -> None:
    instance = replace(
        _instance(),
        senders=_instance().senders[:1],
        pairs=(
            PairEligibility("early", "ngo", True, 20),
            PairEligibility("early", "ngo", True, 20.1),
        ),
    )
    result = apply_pairwise_pickup_windows(
        instance,
        {"early": time(22, 0)},
        average_speed_kmh=20,
        receiver_closing_time=time(23, 0),
    )
    assert [pair.eligible for pair in result.pairs] == [True, False]
    assert "effective travel window=60.0 minutes" in result.pairs[0].evidence
    assert "NGO latest arrival=23:00" in result.pairs[0].evidence


def test_no_delivery_window_remains_when_restaurant_closes_at_ngo_cutoff() -> None:
    instance = replace(
        _instance(),
        senders=_instance().senders[:1],
        pairs=(PairEligibility("early", "ngo", True, 0.1),),
    )
    result = apply_pairwise_pickup_windows(
        instance,
        {"early": time(23, 0)},
        average_speed_kmh=20,
        receiver_closing_time=time(23, 0),
    )
    assert not result.pairs[0].eligible
    assert "effective travel window=0.0 minutes" in result.pairs[0].evidence


def test_missing_distance_does_not_create_a_eligible_pair() -> None:
    instance = replace(
        _instance(),
        pairs=(PairEligibility("early", "ngo", False, None),),
        senders=_instance().senders[:1],
    )
    result = apply_pairwise_pickup_windows(
        instance, {"early": time(20, 0)}, average_speed_kmh=20
    )
    assert not result.pairs[0].eligible


def test_missing_sender_hours_and_invalid_speed_are_rejected() -> None:
    with pytest.raises(ValueError, match="positive"):
        apply_pairwise_pickup_windows(
            _instance(),
            {"early": time(20, 0), "late": time(23, 0)},
            average_speed_kmh=0,
        )
    with pytest.raises(ValueError, match="every sender"):
        apply_pairwise_pickup_windows(
            _instance(), {"early": time(20, 0)}, average_speed_kmh=20
        )


def test_window_labels_include_midnight_rollover() -> None:
    assert collection_window_labels(time(22, 0)) == ("22:00", "00:00 next day")
    assert collection_window_labels(time(19, 0)) == ("19:00", "21:00")


def test_hours_loader_uses_only_location_matched_records(tmp_path) -> None:
    path = tmp_path / "hours.csv"
    path.write_text(
        "sender_id,day_of_week,closing_time_local,source_platform,"
        "google_search_query,match_status,checked_date,notes\n"
        "known,Wednesday,22:00,Google Maps,query,matched_name_address,2026-11-11,note\n"
        "alias,Wednesday,21:00,Google Search,query,same_location_alias,2026-11-11,note\n"
        "unknown,Wednesday,23:00,Google Search,query,address_mismatch,2026-11-11,note\n"
        "other_day,Thursday,21:00,Google Maps,query,matched_name_address,2026-11-11,note\n",
        encoding="utf-8",
    )
    times, provenance = load_google_closing_times(path, "Wednesday")
    assert times == {"known": time(22, 0)}
    assert set(provenance) == set(times)


def test_hours_loader_rejects_duplicate_day_entries(tmp_path) -> None:
    path = tmp_path / "hours.csv"
    path.write_text(
        "sender_id,day_of_week,closing_time_local,source_platform,"
        "google_search_query,match_status,checked_date,notes\n"
        "known,Wednesday,22:00,Google Maps,query,matched_name_address,2026-11-11,note\n"
        "known,Wednesday,21:00,Google Search,query,matched_name_address,2026-11-11,note\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Multiple closing-time records"):
        load_google_closing_times(path, "Wednesday")
