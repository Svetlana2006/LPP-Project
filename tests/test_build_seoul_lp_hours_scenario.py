from scripts.build_seoul_lp_hours_scenario import build_schedule_rows


def test_daily_schedule_uses_matched_close_and_marks_other_hours_as_assumptions() -> None:
    rows = build_schedule_rows(
        [
            {"sender_id": "known", "business_name_original_ko": "식당 A"},
            {"sender_id": "unknown", "business_name_original_ko": "식당 B"},
        ],
        [
            {
                "sender_id": "known",
                "day_of_week": "Monday",
                "closing_time_local": "22:00",
                "source_platform": "Google Maps",
                "match_status": "matched_name_address",
                "checked_date": "2026-11-11",
            },
            {
                "sender_id": "known",
                "day_of_week": "Tuesday",
                "closing_time_local": "23:00",
                "source_platform": "Google Maps",
                "match_status": "matched_name_address",
                "checked_date": "2026-11-11",
            },
            {
                "sender_id": "not-matched",
                "day_of_week": "Monday",
                "closing_time_local": "20:00",
                "source_platform": "Google Maps",
                "match_status": "address_mismatch",
                "checked_date": "2026-11-11",
            },
        ],
        [
            {
                "sender_id": "known",
                "source_names": "Google Search/Maps lookup",
            },
            {
                "sender_id": "unknown",
                "source_names": "OpenStreetMap",
            },
        ],
    )
    by_key = {(row["sender_id"], row["day_of_week"]): row for row in rows}

    assert len(rows) == 2 * 7
    assert by_key[("known", "Monday")]["closing_time_local"] == "22:00"
    assert by_key[("known", "Monday")]["schedule_evidence_type"] == "SOURCE_LOOKUP"
    assert by_key[("known", "Monday")]["effective_travel_window_minutes"] == "60.0"
    assert by_key[("known", "Tuesday")]["effective_travel_window_minutes"] == "0.0"
    assert by_key[("known", "Wednesday")]["closing_time_local"] == "21:00"
    assert (
        by_key[("known", "Wednesday")]["effective_travel_window_minutes"]
        == "120.0"
    )
    assert (
        by_key[("known", "Wednesday")]["schedule_evidence_type"]
        == "USER_SCENARIO_ASSUMPTION"
    )
    assert (
        by_key[("unknown", "Monday")][
            "listed_hours_source_not_used_for_daily_close"
        ]
        == "OpenStreetMap"
    )
    assert by_key[("unknown", "Monday")]["ngo_latest_arrival_local"] == "23:00"
