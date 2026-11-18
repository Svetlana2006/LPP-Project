"""CSV ingestion and strict validation for model inputs."""

import csv
import io
import math
from datetime import date
from typing import Iterable

from food_allocation.models import (
    AllocationInstance,
    PairEligibility,
    Receiver,
    Sender,
)


class DataValidationError(ValueError):
    """Raised when an uploaded dataset cannot safely define a model instance."""


def _read_csv(content: bytes | str, label: str) -> list[dict[str, str]]:
    try:
        text = content.decode("utf-8-sig") if isinstance(content, bytes) else content
        reader = csv.DictReader(io.StringIO(text))
        if reader.fieldnames is None:
            raise DataValidationError(f"{label} is empty or has no header row.")
        return [
            {key: (value or "").strip() for key, value in row.items() if key is not None}
            for row in reader
        ]
    except UnicodeDecodeError as exc:
        raise DataValidationError(f"{label} must be UTF-8 encoded.") from exc
    except csv.Error as exc:
        raise DataValidationError(f"{label} is not valid CSV: {exc}") from exc


def _require_columns(
    rows: list[dict[str, str]], required: Iterable[str], label: str
) -> None:
    if not rows:
        raise DataValidationError(f"{label} must contain at least one data row.")
    available = set(rows[0])
    missing = sorted(set(required) - available)
    if missing:
        raise DataValidationError(f"{label} is missing required columns: {', '.join(missing)}.")


def _number(value: str, field: str, row_number: int, *, required: bool = True) -> float | None:
    if not value and not required:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise DataValidationError(f"Row {row_number}: {field} must be numeric.") from exc
    if not math.isfinite(number):
        raise DataValidationError(f"Row {row_number}: {field} must be finite.")
    return number


def _period(start: str, end: str, label: str, row_number: int) -> tuple[str, str]:
    try:
        start_date = date.fromisoformat(start)
        end_date = date.fromisoformat(end)
    except ValueError as exc:
        raise DataValidationError(
            f"{label} row {row_number}: period_start and period_end must be ISO dates (YYYY-MM-DD)."
        ) from exc
    if start_date.isoformat() != start or end_date.isoformat() != end:
        raise DataValidationError(
            f"{label} row {row_number}: dates must use the exact YYYY-MM-DD format."
        )
    if start_date > end_date:
        raise DataValidationError(f"{label} row {row_number}: period_start must not follow period_end.")
    return start_date.isoformat(), end_date.isoformat()


def _coordinates(
    row: dict[str, str], label: str, row_number: int
) -> tuple[float | None, float | None]:
    latitude_text = row.get("latitude", "")
    longitude_text = row.get("longitude", "")
    if bool(latitude_text) != bool(longitude_text):
        raise DataValidationError(
            f"{label} row {row_number}: latitude and longitude must both be provided or both be blank."
        )
    if not latitude_text:
        return None, None
    latitude = _number(latitude_text, "latitude", row_number)
    longitude = _number(longitude_text, "longitude", row_number)
    assert latitude is not None and longitude is not None
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise DataValidationError(f"{label} row {row_number}: coordinates are out of range.")
    return latitude, longitude


def load_instance(
    senders_csv: bytes | str,
    receivers_csv: bytes | str,
    eligibility_csv: bytes | str,
) -> AllocationInstance:
    """Read three documented CSVs and reject incomplete or incompatible inputs."""

    sender_rows = _read_csv(senders_csv, "senders.csv")
    receiver_rows = _read_csv(receivers_csv, "receivers.csv")
    pair_rows = _read_csv(eligibility_csv, "eligibility_matrix.csv")
    _require_columns(
        sender_rows,
        (
            "sender_id",
            "eligible_surplus_kg",
            "quantity_unit",
            "period_start",
            "period_end",
            "evidence_type",
            "surplus_evidence",
            "source_id",
        ),
        "senders.csv",
    )
    _require_columns(
        receiver_rows,
        (
            "receiver_id",
            "effective_receiving_capacity_kg",
            "capacity_unit",
            "period_start",
            "period_end",
            "evidence_type",
            "capacity_evidence",
            "source_id",
        ),
        "receivers.csv",
    )
    _require_columns(
        pair_rows,
        ("sender_id", "receiver_id", "eligible", "road_distance_km", "source_id"),
        "eligibility_matrix.csv",
    )

    senders: list[Sender] = []
    sender_ids: set[str] = set()
    common_period: tuple[str, str] | None = None
    for row_number, row in enumerate(sender_rows, start=2):
        sender_id = row["sender_id"]
        if not sender_id:
            raise DataValidationError(f"senders.csv row {row_number}: sender_id cannot be blank.")
        if sender_id in sender_ids:
            raise DataValidationError(f"senders.csv row {row_number}: duplicate sender_id {sender_id!r}.")
        sender_ids.add(sender_id)
        if row["quantity_unit"].casefold() != "kg":
            raise DataValidationError(
                f"senders.csv row {row_number}: quantity_unit must be kg; convert values explicitly first."
            )
        supply = _number(row["eligible_surplus_kg"], "eligible_surplus_kg", row_number)
        assert supply is not None
        if supply < 0:
            raise DataValidationError(f"senders.csv row {row_number}: eligible surplus cannot be negative.")
        evidence_type = row["evidence_type"].upper()
        if evidence_type not in {"OBSERVED", "DERIVED", "PROXY", "SCENARIO"}:
            raise DataValidationError(
                f"senders.csv row {row_number}: evidence_type must be OBSERVED, DERIVED, PROXY, or SCENARIO."
            )
        if not row["surplus_evidence"] or not row["source_id"]:
            raise DataValidationError(
                f"senders.csv row {row_number}: surplus_evidence and source_id are required."
            )
        period = _period(row["period_start"], row["period_end"], "senders.csv", row_number)
        if common_period is not None and period != common_period:
            raise DataValidationError("All senders must use the same collection period.")
        common_period = period
        latitude, longitude = _coordinates(row, "senders.csv", row_number)
        deadline = row.get("pickup_deadline", "") or None
        if deadline:
            try:
                parsed_deadline = date.fromisoformat(deadline)
            except ValueError as exc:
                raise DataValidationError(
                    f"senders.csv row {row_number}: pickup_deadline must be an ISO date (YYYY-MM-DD)."
                ) from exc
            if parsed_deadline.isoformat() != deadline:
                raise DataValidationError(
                    f"senders.csv row {row_number}: pickup_deadline must use YYYY-MM-DD."
                )
        senders.append(
            Sender(
                sender_id=sender_id,
                supply_kg=supply,
                period_start=period[0],
                period_end=period[1],
                pickup_deadline=deadline,
                latitude=latitude,
                longitude=longitude,
                evidence_type=evidence_type,
                evidence=row["surplus_evidence"],
                source_id=row["source_id"],
            )
        )

    receivers: list[Receiver] = []
    receiver_ids: set[str] = set()
    for row_number, row in enumerate(receiver_rows, start=2):
        receiver_id = row["receiver_id"]
        if not receiver_id:
            raise DataValidationError(f"receivers.csv row {row_number}: receiver_id cannot be blank.")
        if receiver_id in receiver_ids:
            raise DataValidationError(
                f"receivers.csv row {row_number}: duplicate receiver_id {receiver_id!r}."
            )
        receiver_ids.add(receiver_id)
        if row["capacity_unit"].casefold() != "kg":
            raise DataValidationError(
                f"receivers.csv row {row_number}: capacity_unit must be kg; convert values explicitly first."
            )
        capacity = _number(
            row["effective_receiving_capacity_kg"],
            "effective_receiving_capacity_kg",
            row_number,
        )
        assert capacity is not None
        if capacity < 0:
            raise DataValidationError(f"receivers.csv row {row_number}: capacity cannot be negative.")
        evidence_type = row["evidence_type"].upper()
        if evidence_type not in {"OBSERVED", "DERIVED", "PROXY", "SCENARIO"}:
            raise DataValidationError(
                f"receivers.csv row {row_number}: evidence_type must be OBSERVED, DERIVED, PROXY, or SCENARIO."
            )
        if not row["capacity_evidence"] or not row["source_id"]:
            raise DataValidationError(
                f"receivers.csv row {row_number}: capacity_evidence and source_id are required."
            )
        period = _period(row["period_start"], row["period_end"], "receivers.csv", row_number)
        if common_period is not None and period != common_period:
            raise DataValidationError("All receivers must use the same collection period as the senders.")
        common_period = period
        latitude, longitude = _coordinates(row, "receivers.csv", row_number)
        receivers.append(
            Receiver(
                receiver_id=receiver_id,
                capacity_kg=capacity,
                period_start=period[0],
                period_end=period[1],
                latitude=latitude,
                longitude=longitude,
                evidence_type=evidence_type,
                evidence=row["capacity_evidence"],
                source_id=row["source_id"],
            )
        )

    pairs: list[PairEligibility] = []
    seen_pairs: set[tuple[str, str]] = set()
    for row_number, row in enumerate(pair_rows, start=2):
        sender_id = row["sender_id"]
        receiver_id = row["receiver_id"]
        pair = (sender_id, receiver_id)
        if sender_id not in sender_ids or receiver_id not in receiver_ids:
            raise DataValidationError(
                f"eligibility_matrix.csv row {row_number}: pair references an unknown sender or receiver."
            )
        if pair in seen_pairs:
            raise DataValidationError(f"eligibility_matrix.csv row {row_number}: duplicate pair {pair!r}.")
        seen_pairs.add(pair)
        eligible_text = row["eligible"].casefold()
        if eligible_text not in {"true", "false", "1", "0"}:
            raise DataValidationError(
                f"eligibility_matrix.csv row {row_number}: eligible must be true/false or 1/0."
            )
        eligible = eligible_text in {"true", "1"}
        evidence = row.get("eligibility_evidence", "")
        source_id = row["source_id"]
        if not source_id:
            raise DataValidationError(
                f"eligibility_matrix.csv row {row_number}: source_id is required."
            )
        distance = _number(
            row["road_distance_km"],
            "road_distance_km",
            row_number,
            required=False,
        )
        if eligible:
            if not evidence:
                raise DataValidationError(
                    f"eligibility_matrix.csv row {row_number}: eligible pairs require eligibility_evidence."
                )
            if distance is not None and distance < 0:
                raise DataValidationError(
                    f"eligibility_matrix.csv row {row_number}: road distance cannot be negative."
                )
        elif distance is not None and distance < 0:
            raise DataValidationError(
                f"eligibility_matrix.csv row {row_number}: road distance cannot be negative."
            )
        pairs.append(
            PairEligibility(sender_id, receiver_id, eligible, distance, evidence, source_id)
        )

    expected_pairs = {
        (sender_id, receiver_id) for sender_id in sender_ids for receiver_id in receiver_ids
    }
    if seen_pairs != expected_pairs:
        missing_count = len(expected_pairs - seen_pairs)
        raise DataValidationError(
            f"eligibility_matrix.csv must contain one explicit row for every possible pair; "
            f"{missing_count} pair(s) are missing."
        )

    return AllocationInstance(tuple(senders), tuple(receivers), tuple(pairs))
