# Historical hypothetical pickup-window experiment

> **Superseded for the application by the sourced-hours workflow.** This report
> preserves the earlier sensitivity experiment so its assumptions/results are
> not lost. Its generated restaurant closing times were hypothetical. The app
> now reads the partial, location-matched Google Search/Maps enrichment table
> [`data/scenario_refined/google_restaurant_closing_times.csv`](../data/scenario_refined/google_restaurant_closing_times.csv)
> and reports only the restaurants with hours recorded for the selected day.
> See [`google_closing_time_experiment.md`](google_closing_time_experiment.md).

This experiment applies a separate hypothetical closing time to each restaurant and sets its pickup deadline to closing time plus two hours. It uses no Google Maps API, paid service, or new external route requests.

## Assumptions used

- Original all-reported-waste scenario: alpha=1.0; equal receiver shares; total receiver capacity equals total scenario supply (beta=1.0).
- Each schedule assigns balanced, reproducible hypothetical closing hours of 20:00, 21:00, 22:00, or 23:00 across restaurant IDs. Seeds 0, 1, and 2 vary which restaurant receives which hour. These are not observed Seoul business hours.
- Collection-start sensitivity: 20:00, 21:00, and 22:00. Each restaurant's own deadline is its assigned closing time plus two hours, including next-day deadlines.
- Estimated one-way driving duration = existing OSRM road distance divided by an assumed average speed. Sensitivity values: 15, 20, and 25 km/h. These speeds are scenario parameters, not Google Maps estimates.
- A pair is allowed if the estimated direct arrival from the NGO site is no later than that specific restaurant's deadline.

## Honest scope boundary

The continuous LP and greedy allocation use the exact same pairwise deadline-feasible edges, supplies, capacities, and route distances. This keeps the LP simple and the comparison fair. It does **not** simulate an NGO driving NGO→A→C→B: restaurant-to-restaurant legs, stop order, loading time, traffic, and cumulative route duration are not modeled. Therefore this tests restaurant-specific deadline filtering, not the complete multi-stop failure story. That exact story requires route-order decisions and is not representable in a plain continuous LP.

Among the 81 same-input LP/greedy comparisons, LP allocated more kg in **23**, tied within 1e-6 kg in **58**, and was below greedy in **0**. No strict win is guaranteed; the LP maximizes allocated kilograms over the same feasible edge set, while greedy can tie.

By fixed greedy order:
- `sender_id`: LP strictly higher in 8/27, ties 19/27.
- `fewest_eligible`: LP strictly higher in 0/27, ties 27/27.
- `largest_supply`: LP strictly higher in 15/27, ties 12/27.

## Results by schedule, collection start, and speed

| Seed | Collection start | Assumed speed km/h | Deadline-feasible pairs | LP max kg | Greedy orders min–max kg | LP Stage 2 kg-km |
|---:|:---:|---:|---:|---:|---:|---:|
| 0 | 20:00 | 15 | 57066 | 5,181,995.20 | 5,181,995.20–5,181,995.20 | 31,293,858.59 |
| 0 | 20:00 | 20 | 57435 | 5,181,995.20 | 5,181,995.20–5,181,995.20 | 31,293,858.59 |
| 0 | 20:00 | 25 | 57440 | 5,181,995.20 | 5,181,995.20–5,181,995.20 | 31,293,858.59 |
| 0 | 21:00 | 15 | 50496 | 5,181,995.20 | 5,006,985.20–5,181,995.20 | 31,298,977.00 |
| 0 | 21:00 | 20 | 54511 | 5,181,995.20 | 5,108,795.20–5,181,995.20 | 31,293,858.59 |
| 0 | 21:00 | 25 | 56278 | 5,181,995.20 | 5,177,390.20–5,181,995.20 | 31,293,858.59 |
| 0 | 22:00 | 15 | 36267 | 3,874,005.50 | 3,871,855.50–3,874,005.50 | 16,731,891.88 |
| 0 | 22:00 | 20 | 40205 | 3,874,005.50 | 3,872,805.50–3,874,005.50 | 16,731,891.88 |
| 0 | 22:00 | 25 | 41959 | 3,874,005.50 | 3,872,805.50–3,874,005.50 | 16,731,891.88 |
| 1 | 20:00 | 15 | 57132 | 5,181,995.20 | 5,181,995.20–5,181,995.20 | 31,293,858.59 |
| 1 | 20:00 | 20 | 57438 | 5,181,995.20 | 5,181,995.20–5,181,995.20 | 31,293,858.59 |
| 1 | 20:00 | 25 | 57440 | 5,181,995.20 | 5,181,995.20–5,181,995.20 | 31,293,858.59 |
| 1 | 21:00 | 15 | 50598 | 5,181,995.20 | 4,994,282.90–5,181,995.20 | 31,299,016.00 |
| 1 | 21:00 | 20 | 54650 | 5,181,995.20 | 5,123,060.20–5,181,995.20 | 31,293,858.59 |
| 1 | 21:00 | 25 | 56390 | 5,181,995.20 | 5,151,395.20–5,181,995.20 | 31,293,858.59 |
| 1 | 22:00 | 15 | 36088 | 3,942,963.75 | 3,940,463.75–3,942,963.75 | 17,213,762.30 |
| 1 | 22:00 | 20 | 40007 | 3,942,963.75 | 3,940,463.75–3,942,963.75 | 17,213,762.30 |
| 1 | 22:00 | 25 | 41836 | 3,942,963.75 | 3,940,463.75–3,942,963.75 | 17,213,762.30 |
| 2 | 20:00 | 15 | 57044 | 5,181,995.20 | 5,181,995.20–5,181,995.20 | 31,293,858.59 |
| 2 | 20:00 | 20 | 57433 | 5,181,995.20 | 5,181,995.20–5,181,995.20 | 31,293,858.59 |
| 2 | 20:00 | 25 | 57440 | 5,181,995.20 | 5,181,995.20–5,181,995.20 | 31,293,858.59 |
| 2 | 21:00 | 15 | 50429 | 5,181,995.20 | 4,875,019.15–5,181,995.20 | 31,294,978.87 |
| 2 | 21:00 | 20 | 54364 | 5,181,995.20 | 5,036,795.20–5,181,995.20 | 31,293,858.59 |
| 2 | 21:00 | 25 | 56191 | 5,181,995.20 | 5,082,369.70–5,181,995.20 | 31,293,858.59 |
| 2 | 22:00 | 15 | 36213 | 3,771,301.20 | 3,771,301.20–3,771,301.20 | 16,216,962.42 |
| 2 | 22:00 | 20 | 40200 | 3,771,301.20 | 3,771,301.20–3,771,301.20 | 16,216,962.42 |
| 2 | 22:00 | 25 | 41952 | 3,771,301.20 | 3,771,301.20–3,771,301.20 | 16,216,962.42 |

The legacy per-order results and assumed schedules were removed during
repository cleanup. They were hypothetical, not observed restaurant hours;
the currently retained source-hours experiments are generated by
`scripts/run_seoul_deadline_experiment.py`.
