"""Build a provenance-preserving hours coverage table from Seoul Open Data."""

from __future__ import annotations

import argparse
import csv
import re
import unicodedata
from pathlib import Path
from typing import TextIO

ROOT = Path(__file__).resolve().parents[1]
SENDER_FILE = ROOT / "data/scenario_refined/sender_observations.csv"
SOURCE_FILE = ROOT / "data/raw/seoul_tourism_food_OA-21054_2026-11-11.csv"
OUTPUT_FILE = ROOT / "data/scenario_refined/seoul_restaurant_hours_coverage.csv"
SOURCE_URL = "https://data.seoul.go.kr/dataList/OA-21054/S/1/datasetView.do"
SOURCE_UPDATED = "2026-11-11"
SOURCE_LICENSE = "Korea Open Government License Type 1 (attribution)"

OUTPUT_FIELDS = [
    "sender_id",
    "business_name_original_ko",
    "address_original_ko",
    "source_match_status",
    "operating_hours_raw",
    "source_candidate_hours_raw",
    "source_record_ids",
    "source_business_name_ko",
    "source_road_address",
    "source_record_url",
    "source_dataset_id",
    "source_dataset_updated",
    "source_license",
]

ROAD_ADDRESS = re.compile(
    r"([가-힣0-9]+(?:대로|로|길)(?:\s*\d+(?:길|로))?(?:의\d+)?)\s*"
    r"(\d+(?:-\d+)?)"
)


def normalize(value: str) -> str:
    """Remove spacing and punctuation for conservative name/address matching."""
    normalized = unicodedata.normalize("NFKC", value or "").casefold()
    return "".join(character for character in normalized if character.isalnum())


def road_address_key(value: str) -> str:
    match = ROAD_ADDRESS.search(unicodedata.normalize("NFKC", value or ""))
    return normalize("".join(match.groups())) if match else ""


def _read_csv(path: Path, encoding: str) -> list[dict[str, str]]:
    with path.open(encoding=encoding, errors="replace", newline="") as file:
        return list(csv.DictReader(file))


def build_coverage_rows(
    senders: list[dict[str, str]], source_records: list[dict[str, str]]
) -> list[dict[str, str]]:
    """Match only Korean listings with both an exact normalized name and road key."""
    listings: dict[tuple[str, str], list[dict[str, str]]] = {}
    for record in source_records:
        if record.get("언어") != "ko":
            continue
        if any(
            "\ufffd" in record.get(field, "")
            for field in ("고유번호", "상호명", "신주소", "운영시간", "콘텐츠URL")
        ):
            raise ValueError("Undecodable text found in a Korean source listing.")
        key = (
            normalize(record.get("상호명", "")),
            road_address_key(record.get("신주소", "")),
        )
        if key[0] and key[1]:
            listings.setdefault(key, []).append(record)

    result: list[dict[str, str]] = []
    for sender in senders:
        key = (
            normalize(sender.get("business_name_original_ko", "")),
            road_address_key(sender.get("address_original_ko", "")),
        )
        matches = listings.get(key, []) if key[0] and key[1] else []
        record: dict[str, str] = {
            "sender_id": sender["sender_id"],
            "business_name_original_ko": sender["business_name_original_ko"],
            "address_original_ko": sender["address_original_ko"],
            "source_match_status": "no_exact_source_match",
            "operating_hours_raw": "",
            "source_candidate_hours_raw": "",
            "source_record_ids": "",
            "source_business_name_ko": "",
            "source_road_address": "",
            "source_record_url": "",
            "source_dataset_id": "",
            "source_dataset_updated": "",
            "source_license": "",
        }

        if matches:
            hours = [item.get("운영시간", "").strip() for item in matches]
            canonical_hours = {re.sub(r"\s+", "", value) for value in hours}
            record.update(
                source_record_ids="|".join(item.get("고유번호", "") for item in matches),
                source_business_name_ko=matches[0].get("상호명", ""),
                source_road_address=matches[0].get("신주소", ""),
                source_record_url=matches[0].get("콘텐츠URL", ""),
                source_dataset_id="OA-21054",
                source_dataset_updated=SOURCE_UPDATED,
                source_license=SOURCE_LICENSE,
            )
            if len(canonical_hours) > 1:
                record["source_match_status"] = "ambiguous_conflicting_source_rows"
                record["source_candidate_hours_raw"] = " || ".join(hours)
            elif hours and hours[0]:
                record["source_match_status"] = (
                    "matched_duplicate_rows_schedule_agrees"
                    if len(matches) > 1
                    else "matched_exact_name_and_road_address"
                )
                record["operating_hours_raw"] = hours[0]
            else:
                record["source_match_status"] = "matched_listing_without_hours"

        result.append(record)
    return result


def write_rows(rows: list[dict[str, str]], output: TextIO) -> None:
    writer = csv.DictWriter(output, fieldnames=OUTPUT_FIELDS, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--senders", type=Path, default=SENDER_FILE)
    parser.add_argument("--source", type=Path, default=SOURCE_FILE)
    parser.add_argument("--output", type=Path, default=OUTPUT_FILE)
    args = parser.parse_args()

    senders = _read_csv(args.senders, "utf-8-sig")
    source_records = _read_csv(args.source, "cp949")
    rows = build_coverage_rows(senders, source_records)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as output:
        write_rows(rows, output)

    matched = sum(
        row["source_match_status"]
        in {
            "matched_exact_name_and_road_address",
            "matched_duplicate_rows_schedule_agrees",
        }
        for row in rows
    )
    ambiguous = sum(
        row["source_match_status"] == "ambiguous_conflicting_source_rows"
        for row in rows
    )
    print(
        f"Wrote {len(rows)} sender rows; {matched} have a usable exact-match "
        f"source schedule; {ambiguous} have conflicting source records."
    )


if __name__ == "__main__":
    main()
