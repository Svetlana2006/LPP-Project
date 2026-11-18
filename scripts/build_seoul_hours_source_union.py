"""Build a one-row-per-sender index of usable hours evidence from current sources."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SENDER_FILE = ROOT / "data/scenario_refined/sender_observations.csv"
TOURISM_FILE = ROOT / "data/scenario_refined/seoul_restaurant_hours_coverage.csv"
GOOGLE_FILE = ROOT / "data/scenario_refined/google_restaurant_closing_times.csv"
OSM_FILE = ROOT / "data/scenario_refined/seoul_osm_restaurant_hours.csv"
OUTPUT_FILE = ROOT / "data/scenario_refined/seoul_restaurant_hours_source_union.csv"
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
TOURISM_MATCHES = {
    "matched_exact_name_and_road_address",
    "matched_duplicate_rows_schedule_agrees",
}
OSM_MATCH = "matched_exact_name_and_location"
GOOGLE_MATCH = "matched_name_address"
OUTPUT_FIELDS = [
    "sender_id",
    "business_name_original_ko",
    "address_original_ko",
    "has_source_hours",
    "source_hours_status",
    "source_names",
    "source_count",
    "seoul_tourism_match_status",
    "seoul_tourism_record_ids",
    "seoul_tourism_hours_raw",
    "seoul_tourism_source_url",
    "seoul_tourism_snapshot_date",
    "osm_match_status",
    "osm_object_ids",
    "osm_opening_hours_raw",
    "osm_source_record_urls",
    "osm_snapshot_date",
    "google_matched_day_count",
    "google_matched_days",
    "google_checked_dates",
    "google_source_file",
]


def _read_csv(path: Path, *, optional: bool = False) -> list[dict[str, str]]:
    if optional and not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def build_union_rows(
    senders: list[dict[str, str]],
    tourism_rows: list[dict[str, str]],
    google_rows: list[dict[str, str]],
    osm_rows: list[dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    tourism_by_sender = {row["sender_id"]: row for row in tourism_rows}
    google_by_sender: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in google_rows:
        if (
            row.get("match_status") == GOOGLE_MATCH
            and row.get("closing_time_local", "").strip()
        ):
            google_by_sender[row["sender_id"]].append(row)

    osm_by_sender: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in osm_rows or []:
        if (
            row.get("source_match_status") == OSM_MATCH
            and row.get("osm_opening_hours", "").strip()
        ):
            osm_by_sender[row["sender_id"]].append(row)

    output: list[dict[str, str]] = []
    for sender in senders:
        sender_id = sender["sender_id"]
        tourism = tourism_by_sender.get(sender_id, {})
        tourism_is_match = (
            tourism.get("source_match_status") in TOURISM_MATCHES
            and bool(tourism.get("operating_hours_raw", "").strip())
        )
        google = google_by_sender.get(sender_id, [])
        osm = osm_by_sender.get(sender_id, [])

        sources = []
        if tourism_is_match:
            sources.append("Seoul Open Data OA-21054")
        if osm:
            sources.append("OpenStreetMap")
        if google:
            sources.append("Google Search/Maps lookup (separate source file)")

        if not sources:
            status = "no_source_hours_found"
        elif len(sources) > 1:
            status = "multiple_source_hours"
        else:
            status = {
                "Seoul Open Data OA-21054": "seoul_tourism_hours_text",
                "OpenStreetMap": "osm_opening_hours_tag",
                "Google Search/Maps lookup (separate source file)": (
                    "google_lookup_day_hours"
                ),
            }[sources[0]]

        osm_statuses = sorted({row["source_match_status"] for row in (
            osm_rows or []
        ) if row.get("sender_id") == sender_id})
        row = {
            "sender_id": sender_id,
            "business_name_original_ko": sender["business_name_original_ko"],
            "address_original_ko": sender["address_original_ko"],
            "has_source_hours": "true" if sources else "false",
            "source_hours_status": status,
            "source_names": " | ".join(sources),
            "source_count": str(len(sources)),
            "seoul_tourism_match_status": tourism.get(
                "source_match_status", "not_in_source_ledger"
            ),
            "seoul_tourism_record_ids": tourism.get("source_record_ids", ""),
            "seoul_tourism_hours_raw": (
                tourism.get("operating_hours_raw", "") if tourism_is_match else ""
            ),
            "seoul_tourism_source_url": (
                tourism.get("source_record_url", "") if tourism_is_match else ""
            ),
            "seoul_tourism_snapshot_date": (
                tourism.get("source_dataset_updated", "") if tourism_is_match else ""
            ),
            "osm_match_status": " | ".join(osm_statuses) or "not_searched",
            "osm_object_ids": "|".join(row["osm_object_id"] for row in osm),
            "osm_opening_hours_raw": " || ".join(
                sorted({row["osm_opening_hours"] for row in osm})
            ),
            "osm_source_record_urls": "|".join(row["source_record_url"] for row in osm),
            "osm_snapshot_date": (
                "|".join(sorted({row["source_snapshot_date"] for row in osm}))
                if osm
                else ""
            ),
            "google_matched_day_count": str(
                len({row.get("day_of_week", "") for row in google})
            ),
            "google_matched_days": "|".join(
                day
                for day in WEEKDAYS
                if day in {row.get("day_of_week", "") for row in google}
            ),
            "google_checked_dates": "|".join(
                sorted({row.get("checked_date", "") for row in google})
            ),
            "google_source_file": (
                "google_restaurant_closing_times.csv" if google else ""
            ),
        }
        output.append(row)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--senders", type=Path, default=SENDER_FILE)
    parser.add_argument("--tourism", type=Path, default=TOURISM_FILE)
    parser.add_argument("--google", type=Path, default=GOOGLE_FILE)
    parser.add_argument("--osm", type=Path, default=OSM_FILE)
    parser.add_argument("--output", type=Path, default=OUTPUT_FILE)
    args = parser.parse_args()

    rows = build_union_rows(
        _read_csv(args.senders),
        _read_csv(args.tourism),
        _read_csv(args.google),
        _read_csv(args.osm, optional=True),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    covered = sum(row["has_source_hours"] == "true" for row in rows)
    print(f"Wrote {len(rows)} sender rows; {covered} have source-listed hours.")


if __name__ == "__main__":
    main()
