from scripts.build_seoul_complete_hours_scenario import (
    WEEKDAYS,
    build_rows,
    closing_candidate,
)


def test_extracts_last_service_interval_and_skips_last_order() -> None:
    assert closing_candidate("11:30~14:00, 17:00~22:00 (라스트오더 21:00)") == "22:00"


def test_overnight_template_preserves_midnight_close() -> None:
    assert closing_candidate("월~금 16:00~01:00") == "01:00"


def test_complete_week_for_every_sender_is_deterministic_and_labeled() -> None:
    senders = [
        {
            "sender_id": "S-1",
            "business_name_original_ko": "식당 A",
            "address_original_ko": "주소 A",
        },
        {
            "sender_id": "S-2",
            "business_name_original_ko": "식당 B",
            "address_original_ko": "주소 B",
        },
    ]
    source = [
        {
            "언어": "ko",
            "고유번호": "T-1",
            "상호명": "공식 식당",
            "운영시간": "11:00~21:00",
            "콘텐츠URL": "https://example.test/1",
        },
        {
            "언어": "ko",
            "고유번호": "T-2",
            "상호명": "다른 식당",
            "운영시간": "10:00~23:00",
            "콘텐츠URL": "https://example.test/2",
        },
    ]
    rows1 = build_rows(senders, source, [], seed=17)
    rows2 = build_rows(senders, source, [], seed=17)
    assert rows1 == rows2
    assert len(rows1) == len(senders) * 7
    for sender in senders:
        sender_rows = [row for row in rows1 if row["sender_id"] == sender["sender_id"]]
        assert [row["weekday"] for row in sender_rows] == list(WEEKDAYS)
        assert all(
            row["hours_evidence_status"]
            == "imputed_official_listing_template_not_sender_hours"
            for row in sender_rows
        )
        assert all(row["scenario_closing_time_local"] for row in sender_rows)


def test_exact_match_keeps_observed_hours_but_labels_repeated_close_as_scenario() -> None:
    sender = {
        "sender_id": "S-1",
        "business_name_original_ko": "식당 A",
        "address_original_ko": "주소 A",
    }
    source = [
        {
            "언어": "ko",
            "고유번호": "T-1",
            "상호명": "식당 A",
            "운영시간": "월~금 11:00~22:00",
            "콘텐츠URL": "https://example.test/1",
        }
    ]
    matches = [
        {
            "sender_id": "S-1",
            "source_match_status": "matched_exact_name_and_road_address",
            "source_record_ids": "T-1",
        }
    ]
    rows = build_rows([sender], source, matches)
    assert len(rows) == 7
    assert {row["scenario_closing_time_local"] for row in rows} == {"22:00"}
    assert {row["observed_hours_raw"] for row in rows} == {"월~금 11:00~22:00"}
    assert all(
        row["hours_evidence_status"]
        == "exact_match_schedule_text_close_candidate_repeated_all_days"
        for row in rows
    )
