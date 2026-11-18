"""Pairwise pickup-window scenarios using sourced, restaurant-specific hours."""

from __future__ import annotations

import csv
from dataclasses import replace
from datetime import date, datetime, time, timedelta
from pathlib import Path

from food_allocation.models import AllocationInstance, PairEligibility


PICKUP_GRACE_HOURS = 2


def load_google_closing_times(
    hours_path: str | Path, day_of_week: str
) -> tuple[dict[str, time], dict[str, dict[str, str]]]:
    """Load location-matched closing times and their provenance for one weekday."""
    closing_times: dict[str, time] = {}
    provenance: dict[str, dict[str, str]] = {}
    with open(hours_path, encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            if row["day_of_week"] != day_of_week or not row["closing_time_local"]:
                continue
            if row["match_status"] != "matched_name_address":
                continue
            sender_id = row["sender_id"]
            if sender_id in closing_times:
                raise ValueError(
                    f"Multiple closing-time records for {sender_id!r} on {day_of_week}."
                )
            try:
                closing_times[sender_id] = time.fromisoformat(
                    row["closing_time_local"]
                )
            except ValueError as exc:
                raise ValueError(
                    f"Invalid closing time for {sender_id!r}: "
                    f"{row['closing_time_local']!r}."
                ) from exc
            provenance[sender_id] = row
    return closing_times, provenance


def collection_window_labels(closing_time: time) -> tuple[str, str]:
    """Return each restaurant's close-to-close-plus-two-hour window labels."""
    starts = datetime.combine(date(2000, 1, 1), closing_time)
    deadline = starts + timedelta(hours=PICKUP_GRACE_HOURS)
    start_label = starts.strftime("%H:%M")
    deadline_label = deadline.strftime("%H:%M")
    if deadline.date() > starts.date():
        deadline_label += " next day"
    return start_label, deadline_label


def apply_pairwise_pickup_windows(
    instance: AllocationInstance,
    closing_times: dict[str, time],
    *,
    average_speed_kmh: float,
    receiver_closing_time: time | None = None,
) -> AllocationInstance:
    """Allow a pair only when estimated travel fits its pickup and receiver windows.

    The collection window opens at each sender's own closing time. The
    pairwise drive estimate is road distance divided by assumed average speed;
    this     does not schedule multiple pickups or model intervening stops. If
    receiver_closing_time is provided, delivery must also arrive by that
    clock time on the modeled day, shortening the sender's two-hour window
    when necessary.
    """
    if average_speed_kmh <= 0:
        raise ValueError("average_speed_kmh must be positive.")
    sender_ids = {sender.sender_id for sender in instance.senders}
    if set(closing_times) != sender_ids:
        raise ValueError("A sourced closing time is required for every sender.")

    deadlines: dict[str, datetime] = {}
    window_starts: dict[str, datetime] = {}
    maximum_travel_hours: dict[str, float] = {}
    reference_date = datetime(2000, 1, 1).date()
    for sender_id, close_time in closing_times.items():
        if not isinstance(close_time, time):
            raise ValueError(f"Closing time for {sender_id!r} must be a time.")
        start = datetime.combine(reference_date, close_time)
        pickup_deadline = start + timedelta(hours=PICKUP_GRACE_HOURS)
        deadline = pickup_deadline
        if receiver_closing_time is not None:
            receiver_deadline = datetime.combine(
                reference_date, receiver_closing_time
            )
            deadline = (
                start
                if receiver_deadline < start
                else min(pickup_deadline, receiver_deadline)
            )
        window_starts[sender_id] = start
        deadlines[sender_id] = deadline
        maximum_travel_hours[sender_id] = max(
            0.0, (deadline - start).total_seconds() / 3600
        )

    filtered_pairs: list[PairEligibility] = []
    for pair in instance.pairs:
        distance = pair.road_distance_km
        if distance is None and pair.eligible:
            raise ValueError(
                f"Eligible pair {pair.sender_id!r}->{pair.receiver_id!r} has no route distance."
            )
        travel_hours = distance / average_speed_kmh if distance is not None else None
        deadline_feasible = (
            travel_hours is not None and travel_hours <= PICKUP_GRACE_HOURS
        )
        start = window_starts[pair.sender_id]
        deadline = deadlines[pair.sender_id]
        effective_deadline_feasible = (
            travel_hours is not None
            and travel_hours <= maximum_travel_hours[pair.sender_id]
        )
        eligible = pair.eligible and effective_deadline_feasible
        filtered_pairs.append(
            replace(
                pair,
                eligible=eligible,
                evidence=(
                    pair.evidence
                    + f" Restaurant-specific collection window: "
                    f"{start.strftime('%H:%M')} to "
                    f"{deadline.strftime('%H:%M')} "
                    f"({'next day' if deadline.date() > start.date() else 'same day'}); "
                    + (
                        f"estimated direct drive={travel_hours * 60:.1f} minutes "
                        if travel_hours is not None
                        else "estimated direct drive unavailable; "
                    )
                    + f"at assumed {average_speed_kmh:g} km/h; "
                    + (
                        f"two-hour pickup-window feasibility={deadline_feasible}; "
                        f"effective travel window="
                        f"{maximum_travel_hours[pair.sender_id] * 60:.1f} minutes; "
                        if receiver_closing_time is not None
                        else f"two-hour window feasibility={deadline_feasible}."
                    )
                    + (
                        f"NGO latest arrival="
                        f"{receiver_closing_time.strftime('%H:%M')}."
                        if receiver_closing_time is not None
                        else ""
                    )
                ),
                source_id="SCENARIO-SOURCED-PICKUP-WINDOW",
            )
        )
    return replace(instance, pairs=tuple(filtered_pairs))
