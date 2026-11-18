from scripts.build_seoul_hours_coverage import build_coverage_rows, road_address_key


def sender(name: str, address: str) -> dict[str, str]:
    return {
        "sender_id": "S-1",
        "business_name_original_ko": name,
        "address_original_ko": address,
    }


def listing(
    name: str, address: str, hours: str, record_id: str = "T-1", language: str = "ko"
) -> dict[str, str]:
    return {
        "언어": language,
        "상호명": name,
        "신주소": address,
        "운영시간": hours,
        "고유번호": record_id,
        "콘텐츠URL": "https://example.test/restaurant",
    }


def test_road_key_ignores_postcode_parentheses_and_spacing() -> None:
    assert road_address_key("서울특별시 강남구 언주로148길 14, 청호불교문화원") == (
        road_address_key("06057 서울 강남구 언주로148길 14 (논현동)")
    )


def test_road_key_handles_numbers_inside_road_name() -> None:
    assert road_address_key("서울특별시 중랑구 동일로 156길 7") == (
        road_address_key("서울 중랑구 동일로156길7")
    )


def test_requires_exact_name_and_road_address_match() -> None:
    rows = build_coverage_rows(
        [sender("고기집 A", "서울특별시 강남구 언주로148길 14")],
        [listing("고기집 B", "06057 서울 강남구 언주로148길 14", "11:00~22:00")],
    )
    assert rows[0]["source_match_status"] == "no_exact_source_match"
    assert rows[0]["operating_hours_raw"] == ""


def test_ignores_non_korean_language_duplicate() -> None:
    rows = build_coverage_rows(
        [sender("고기집 A", "서울특별시 강남구 언주로148길 14")],
        [
            listing(
                "고기집 A",
                "06057 서울 강남구 언주로148길 14",
                "11:00~22:00",
                language="en",
            )
        ],
    )
    assert rows[0]["source_match_status"] == "no_exact_source_match"


def test_consistent_duplicate_source_rows_preserve_both_ids() -> None:
    rows = build_coverage_rows(
        [sender("고기집 A", "서울특별시 강남구 언주로148길 14")],
        [
            listing("고기집 A", "06057 서울 강남구 언주로148길 14", "11:00~22:00", "T-1"),
            listing("고기집 A", "06057 서울 강남구 언주로148길 14", "11:00 ~ 22:00", "T-2"),
        ],
    )
    assert rows[0]["source_match_status"] == "matched_duplicate_rows_schedule_agrees"
    assert rows[0]["source_record_ids"] == "T-1|T-2"


def test_conflicting_duplicate_hours_are_not_selected() -> None:
    rows = build_coverage_rows(
        [sender("고기집 A", "서울특별시 강남구 언주로148길 14")],
        [
            listing("고기집 A", "06057 서울 강남구 언주로148길 14", "11:00~22:00", "T-1"),
            listing("고기집 A", "06057 서울 강남구 언주로148길 14", "11:00~21:00", "T-2"),
        ],
    )
    assert rows[0]["source_match_status"] == "ambiguous_conflicting_source_rows"
    assert rows[0]["operating_hours_raw"] == ""
    assert "11:00~22:00" in rows[0]["source_candidate_hours_raw"]
    assert "11:00~21:00" in rows[0]["source_candidate_hours_raw"]
