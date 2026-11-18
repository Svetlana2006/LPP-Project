from scripts.import_seoul_osm_hours import classify_match, road_address_parts


def test_road_address_parser_keeps_numeric_suffixes_in_road_names() -> None:
    assert road_address_parts("서울특별시 중랑구 동일로 156길 7") == (
        "동일로156길",
        "7",
    )
    assert road_address_parts("서울특별시 강남구 영동대로85길 13") == (
        "영동대로85길",
        "13",
    )


def test_osm_match_requires_exact_name_context_and_no_address_conflict() -> None:
    target = {
        "address_original_ko": "서울특별시 중랑구 동일로 156길 7",
        "quality": "partial_address_match_in_Seoul",
    }
    matching_feature = {
        "street": "동일로156길",
        "house_number": "7",
    }
    conflicting_feature = {
        "street": "동일로156길",
        "house_number": "9",
    }

    assert (
        classify_match(
            target,
            matching_feature,
            2.3,
            feature_target_count=1,
            conflicting_hours=False,
        )
        == "matched_exact_name_and_location"
    )
    assert (
        classify_match(
            target,
            conflicting_feature,
            2.3,
            feature_target_count=1,
            conflicting_hours=False,
        )
        == "candidate_address_conflict"
    )
