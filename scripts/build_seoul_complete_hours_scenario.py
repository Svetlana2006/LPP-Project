"""Build a complete, explicitly imputed weekly-hours scenario for Seoul senders."""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SENDER_FILE = ROOT / "data/scenario_refined/sender_observations.csv"
SOURCE_FILE = ROOT / "data/raw/seoul_tourism_food_OA-21054_2026-11-11.csv"
MATCH_FILE = ROOT / "data/scenario_refined/seoul_restaurant_hours_coverage.csv"
OUTPUT_FILE = ROOT / "data/scenario_refined/seoul_restaurant_hours_complete_scenario.csv"
SOURCE_URL = "https://data.seoul.go.kr/dataList/OA-21054/S/1/datasetView.do"
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
TIME = r"(\d{1,2})\s*[:：]\s*(\d{2})"
TIME_RANGE = re.compile(rf"({TIME})\s*[-~～至]\s*({TIME})")
LAST_ORDER = re.compile(r"\([^)]*(?:라스트\s*오더|last\s*order)[^)]*\)", re.IGNORECASE)

OUTPUT_FIELDS = [
    "sender_id",
    "business_name_original_ko",
    "address_original_ko",
    "weekday",
    "scenario_closing_time_local",
    "hours_evidence_status",
    "observed_hours_raw",
    "source_match_status",
    "template_source_record_id",
    "template_source_name",
    "template_source_hours_raw",
    "template_source_url",
    "source_dataset_url",
    "lookup_seed",
    "assumption",
]


def _read_csv(path: Path, encoding: str) -> list[dict[str, str]]:
    with path.open(encoding=encoding, errors="replace", newline="") as file:
        return list(csv.DictReader(file))


def closing_candidate(schedule: str) -> str | None:
    """Return a template closing candidate, not a parsed verified daily close."""
    text = LAST_ORDER.sub("", schedule or "")
    ranges = list(TIME_RANGE.finditer(text))
    if ranges:
        match = ranges[-1]
        hour, minute = int(match.group(5)), int(match.group(6))
    else:
        times = list(re.finditer(TIME, text))
        if not times:
            return None
        hour, minute = int(times[-1].group(1)), int(times[-1].group(2))
    if hour > 24 or minute > 59:
        return None
    return f"{hour % 24:02d}:{minute:02d}"


def _stable_index(sender_id: str, seed: int, size: int) -> int:
    digest = hashlib.sha256(f"{seed}:{sender_id}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % size


def build_rows(
    senders: list[dict[str, str]],
    source_records: list[dict[str, str]],
    matched_records: list[dict[str, str]],
    seed: int = 0,
) -> list[dict[str, str]]:
    templates = sorted(
        (
            {
                "record_id": record.get("고유번호", ""),
                "name": record.get("상호명", ""),
                "hours": record.get("운영시간", "").strip(),
                "url": record.get("콘텐츠URL", ""),
                "close": closing_candidate(record.get("운영시간", "")),
            }
            for record in source_records
            if record.get("언어") == "ko"
        ),
        key=lambda item: item["record_id"],
    )
    templates = [template for template in templates if template["close"]]
    if not templates:
        raise ValueError("The official Seoul source has no usable time templates.")

    match_by_sender = {row["sender_id"]: row for row in matched_records}
    source_by_id = {row.get("고유번호", ""): row for row in source_records}
    output: list[dict[str, str]] = []
    for sender in senders:
        matched = match_by_sender.get(sender["sender_id"], {})
        source_ids = matched.get("source_record_ids", "").split("|")
        observed = source_by_id.get(source_ids[0], {}) if source_ids else {}
        observed_schedule = observed.get("운영시간", "").strip()
        observed_close = closing_candidate(observed_schedule)
        if observed_close:
            template = {
                "record_id": observed.get("고유번호", ""),
                "name": observed.get("상호명", ""),
                "hours": observed_schedule,
                "url": observed.get("콘텐츠URL", ""),
                "close": observed_close,
            }
            evidence = "exact_match_schedule_text_close_candidate_repeated_all_days"
        else:
            template = templates[_stable_index(sender["sender_id"], seed, len(templates))]
            evidence = "imputed_official_listing_template_not_sender_hours"

        for weekday in WEEKDAYS:
            output.append(
                {
                    "sender_id": sender["sender_id"],
                    "business_name_original_ko": sender["business_name_original_ko"],
                    "address_original_ko": sender["address_original_ko"],
                    "weekday": weekday,
                    "scenario_closing_time_local": template["close"],
                    "hours_evidence_status": evidence,
                    "observed_hours_raw": observed_schedule,
                    "source_match_status": matched.get(
                        "source_match_status", "no_exact_source_match"
                    ),
                    "template_source_record_id": template["record_id"],
                    "template_source_name": template["name"],
                    "template_source_hours_raw": template["hours"],
                    "template_source_url": template["url"],
                    "source_dataset_url": SOURCE_URL,
                    "lookup_seed": str(seed),
                    "assumption": (
                        "Scenario-only closing-time candidate copied from a Seoul "
                        "tourist-food listing; repeated for all seven weekdays. "
                        "It is not verified for this sender."
                        if evidence.startswith("imputed_")
                        else (
                            "Source listing matched by exact normalized Korean "
                            "name and road number; one extracted close candidate "
                            "is repeated for all weekdays and is not day-specific "
                            "verification."
                        )
                    ),
                }
            )
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--senders", type=Path, default=SENDER_FILE)
    parser.add_argument("--source", type=Path, default=SOURCE_FILE)
    parser.add_argument("--matches", type=Path, default=MATCH_FILE)
    parser.add_argument("--output", type=Path, default=OUTPUT_FILE)
    args = parser.parse_args()

    rows = build_rows(
        _read_csv(args.senders, "utf-8-sig"),
        _read_csv(args.source, "cp949"),
        _read_csv(args.matches, "utf-8-sig"),
        args.seed,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    verified = len(
        {
            row["sender_id"]
            for row in rows
            if row["hours_evidence_status"].startswith("exact_match_")
        }
    )
    print(
        f"Wrote {len(rows)} weekday rows for {len(rows) // 7} senders; "
        f"{verified} exact-matched schedules, {len(rows) // 7 - verified} "
        "imputed scenario schedules."
    )


if __name__ == "__main__":
    main()
