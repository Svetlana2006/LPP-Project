"""Prepare seven-day, explicit-assumption closing and NGO cutoff records for Seoul LP."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, time, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIRECTORY = ROOT / "data/scenario_refined"
SENDER_FILE = DATA_DIRECTORY / "sender_observations.csv"
GOOGLE_FILE = DATA_DIRECTORY / "google_restaurant_closing_times.csv"
UNION_FILE = DATA_DIRECTORY / "seoul_restaurant_hours_source_union.csv"
OUTPUT_FILE = DATA_DIRECTORY / "seoul_lp_daily_hours_scenario.csv"
DEFAULT_SENDER_CLOSE = time(21, 0)
NGO_LATEST_ARRIVAL = time(23, 0)
PICKUP_GRACE = timedelta(hours=2)
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
OUTPUT_FIELDS = [
    "sender_id",
    "business_name_original_ko",
    "day_of_week",
    "closing_time_local",
    "collection_window_end_local",
    "ngo_latest_arrival_local",
    "effective_latest_arrival_local",
    "effective_travel_window_minutes",
    "schedule_evidence_type",
    "schedule_source",
    "schedule_source_checked_date",
    "listed_hours_source_not_used_for_daily_close",
    "hours_scenario_assumption",
]
REFERENCE_DATE = datetime(2000, 1, 1).date()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _clock_label(value: datetime) -> str:
    label = value.strftime("%H:%M")
    if value.date() > REFERENCE_DATE:
        label += " next day"
    return label


def build_schedule_rows(
    senders: list[dict[str, str]],
    google_rows: list[dict[str, str]],
    source_union_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Use matched daily Google closes; label every other daily close as assumed."""
    sender_ids = {row["sender_id"] for row in senders}
    union_by_sender = {row["sender_id"]: row for row in source_union_rows}
    google_by_day_and_sender: dict[tuple[str, str], dict[str, str]] = {}
    for row in google_rows:
        key = (row["day_of_week"], row["sender_id"])
        if (
            row.get("match_status") != "matched_name_address"
            or not row.get("closing_time_local", "").strip()
            or row["sender_id"] not in sender_ids
        ):
            continue
        if key in google_by_day_and_sender:
            raise ValueError(f"Duplicate matched Google close for {key!r}.")
        try:
            time.fromisoformat(row["closing_time_local"])
        except ValueError as exc:
            raise ValueError(
                f"Invalid Google closing time for {row['sender_id']!r}: "
                f"{row['closing_time_local']!r}."
            ) from exc
        google_by_day_and_sender[key] = row

    output: list[dict[str, str]] = []
    for sender in senders:
        sender_id = sender["sender_id"]
        listed_sources = union_by_sender.get(sender_id, {}).get("source_names", "")
        for day in WEEKDAYS:
            source_row = google_by_day_and_sender.get((day, sender_id))
            if source_row is not None:
                close_time = time.fromisoformat(source_row["closing_time_local"])
                evidence_type = "SOURCE_LOOKUP"
                source_name = source_row.get("source_platform", "")
                checked_date = source_row.get("checked_date", "")
                assumption = ""
            else:
                close_time = DEFAULT_SENDER_CLOSE
                evidence_type = "USER_SCENARIO_ASSUMPTION"
                source_name = ""
                checked_date = ""
                assumption = (
                    "No location-matched closing time for this sender and day; "
                    "use 21:00 solely as the user's requested scenario close."
                )

            start = datetime.combine(REFERENCE_DATE, close_time)
            collection_end = start + PICKUP_GRACE
            receiver_close = datetime.combine(REFERENCE_DATE, NGO_LATEST_ARRIVAL)
            effective_end = min(collection_end, receiver_close)
            available_minutes = max(
                0.0, (effective_end - start).total_seconds() / 60
            )
            output.append(
                {
                    "sender_id": sender_id,
                    "business_name_original_ko": sender[
                        "business_name_original_ko"
                    ],
                    "day_of_week": day,
                    "closing_time_local": close_time.strftime("%H:%M"),
                    "collection_window_end_local": _clock_label(collection_end),
                    "ngo_latest_arrival_local": NGO_LATEST_ARRIVAL.strftime("%H:%M"),
                    "effective_latest_arrival_local": _clock_label(effective_end),
                    "effective_travel_window_minutes": f"{available_minutes:.1f}",
                    "schedule_evidence_type": evidence_type,
                    "schedule_source": source_name,
                    "schedule_source_checked_date": checked_date,
                    "listed_hours_source_not_used_for_daily_close": (
                        listed_sources if evidence_type != "SOURCE_LOOKUP" else ""
                    ),
                    "hours_scenario_assumption": assumption,
                }
            )
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--senders", type=Path, default=SENDER_FILE)
    parser.add_argument("--google", type=Path, default=GOOGLE_FILE)
    parser.add_argument("--source-union", type=Path, default=UNION_FILE)
    parser.add_argument("--output", type=Path, default=OUTPUT_FILE)
    args = parser.parse_args()

    rows = build_schedule_rows(
        _read_csv(args.senders),
        _read_csv(args.google),
        _read_csv(args.source_union),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    sourced = sum(row["schedule_evidence_type"] == "SOURCE_LOOKUP" for row in rows)
    assumed = len(rows) - sourced
    print(
        f"Wrote {len(rows)} sender-day schedule rows: {sourced} source lookup "
        f"rows and {assumed} user-assumption rows."
    )


if __name__ == "__main__":
    main()
