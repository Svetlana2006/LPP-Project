"""Validate, combine, and clean the four deterministic experiment result parts."""

from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REFINED = ROOT / "data" / "scenario_refined"
PART_COUNT = 4
EXPECTED_ROWS = 2160


def main() -> None:
    parts = [
        REFINED / f"scenario_experiment_results.part-{index}-of-{PART_COUNT}.csv"
        for index in range(1, PART_COUNT + 1)
    ]
    missing = [path.name for path in parts if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Experiment result parts are missing: {missing}")

    all_rows: list[dict[str, str]] = []
    fieldnames: list[str] | None = None
    for path in parts:
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames is None:
                raise ValueError(f"{path.name} has no header.")
            if fieldnames is None:
                fieldnames = reader.fieldnames
            elif reader.fieldnames != fieldnames:
                raise ValueError(f"Column mismatch in {path.name}.")
            all_rows.extend(reader)
    scenario_ids = [row["scenario_id"] for row in all_rows]
    if len(all_rows) != EXPECTED_ROWS:
        raise ValueError(
            f"Expected {EXPECTED_ROWS} experiment rows, found {len(all_rows)}."
        )
    if len(set(scenario_ids)) != len(scenario_ids):
        raise ValueError("Duplicate scenario IDs found; refusing to merge.")

    target = REFINED / "scenario_experiment_results.csv"
    with target.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)
    for path in parts:
        path.unlink()
    print(f"Merged and validated {len(all_rows)} rows into {target}.")
    print("Removed the four temporary batch files.")


if __name__ == "__main__":
    main()
