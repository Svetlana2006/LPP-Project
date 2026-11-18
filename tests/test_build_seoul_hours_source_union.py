from scripts.build_seoul_hours_source_union import build_union_rows


def test_union_combines_sources_without_copying_google_hours() -> None:
    rows = build_union_rows(
        [
            {"sender_id": "tourism", "business_name_original_ko": "식당 A", "address_original_ko": "주소 A"},
            {"sender_id": "google", "business_name_original_ko": "식당 B", "address_original_ko": "주소 B"},
            {"sender_id": "unknown", "business_name_original_ko": "식당 C", "address_original_ko": "주소 C"},
        ],
        [
            {
                "sender_id": "tourism",
                "source_match_status": "matched_exact_name_and_road_address",
                "operating_hours_raw": "11:00~22:00",
                "source_record_ids": "T-1",
                "source_record_url": "https://example.test/T-1",
                "source_dataset_updated": "2026-11-11",
            }
        ],
        [
            {
                "sender_id": "google",
                "day_of_week": "Monday",
                "closing_time_local": "22:00",
                "match_status": "matched_name_address",
                "checked_date": "2026-11-11",
            },
            {
                "sender_id": "google",
                "day_of_week": "Tuesday",
                "closing_time_local": "22:00",
                "match_status": "matched_name_address",
                "checked_date": "2026-11-11",
            },
            {
                "sender_id": "unknown",
                "day_of_week": "Monday",
                "closing_time_local": "23:00",
                "match_status": "address_mismatch",
                "checked_date": "2026-11-11",
            },
        ],
    )

    by_id = {row["sender_id"]: row for row in rows}
    assert by_id["tourism"]["source_hours_status"] == "seoul_tourism_hours_text"
    assert by_id["google"]["source_hours_status"] == "google_lookup_day_hours"
    assert by_id["google"]["google_matched_day_count"] == "2"
    assert by_id["google"]["google_source_file"] == "google_restaurant_closing_times.csv"
    assert "closing_time_local" not in by_id["google"]
    assert by_id["unknown"]["has_source_hours"] == "false"
    assert by_id["unknown"]["source_hours_status"] == "no_source_hours_found"


def test_union_deduplicates_source_names_and_accepts_only_strict_osm_matches() -> None:
    sender = {
        "sender_id": "S-1",
        "business_name_original_ko": "식당 A",
        "address_original_ko": "주소 A",
    }
    rows = build_union_rows(
        [sender],
        [
            {
                "sender_id": "S-1",
                "source_match_status": "matched_exact_name_and_road_address",
                "operating_hours_raw": "11:00~22:00",
            }
        ],
        [],
        [
            {
                "sender_id": "S-1",
                "source_match_status": "matched_exact_name_and_location",
                "osm_opening_hours": "Mo-Su 11:00-22:00",
                "osm_object_id": "42",
                "source_record_url": "https://www.openstreetmap.org/node/42",
                "source_snapshot_date": "2026-11-17",
            },
            {
                "sender_id": "S-1",
                "source_match_status": "candidate_requires_location_review",
                "osm_opening_hours": "Mo-Su 12:00-21:00",
                "osm_object_id": "43",
                "source_record_url": "https://www.openstreetmap.org/node/43",
                "source_snapshot_date": "2026-11-17",
            },
        ],
    )

    assert rows[0]["source_hours_status"] == "multiple_source_hours"
    assert rows[0]["source_count"] == "2"
    assert rows[0]["osm_object_ids"] == "42"
    assert rows[0]["osm_opening_hours_raw"] == "Mo-Su 11:00-22:00"
