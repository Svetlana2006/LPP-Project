# Complete Seoul hours scenario (not verified restaurant hours)

`data/scenario_refined/seoul_restaurant_hours_complete_scenario.csv` has one
row per sender per weekday (12,565 rows total). It is designed to let the LP
run across all 1,795 senders, but it does **not** claim all restaurants'
operating hours are known.

- Exact matched source text is retained for 29 senders. One closing-time
  candidate is extracted and repeated across weekdays; even these values are
  not verified day by day.
- The other 1,766 senders receive a reproducible scenario closing-time
  template sampled from the Seoul Open Data tourist-food schedules. These
  templates are not the sender restaurants' hours.
- Every row identifies its evidence status, template source record, raw
  schedule, portal URL, seed, and assumption. `scenario_closing_time_local`
  must not be presented as confirmed operating data.
-   This file is retained only as an explicitly imputed sensitivity-test artifact.
  It must not be used or described as a database of actual restaurant hours.
  The Streamlit LP-versus-greedy pickup-window comparison does not load it; that
  comparison uses only the strict name-and-address-matched records in
  `google_restaurant_closing_times.csv`, and excludes all other senders.
  Consequently, that comparison does not represent all 1,795 restaurants.

  The template is selected reproducibly by SHA-256 of `seed:sender_id`. The
  default seed is zero. Change it with `--seed` to test another deterministic
  assignment. Rebuild:

```powershell
.\.venv\Scripts\python.exe scripts\build_seoul_complete_hours_scenario.py
```

The source schedule parser takes the end time of the last written service
interval (and removes parenthetical last-order notes when recognized). This is
only a scenario-template extraction rule; source schedule prose can be
day-specific, irregular, or ambiguous. The full source snapshot and its
provenance remain in `data/raw/seoul_tourism_food_OA-21054_2026-11-11.csv`.
