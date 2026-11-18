# Refined Seoul scenario inputs

These are reproducible hypothetical scenario inputs. They do not represent
observed edible donations, verified NGO capacities, confirmed donation
acceptance, or delivered food.

## Separate public quantities from scenario variables

- `sender_observations.csv` stores deduplicated public source observations in
  `reported_expected_waste_kg_month` (\(W_i\)). The source field is expected
  waste discharge, not measured edible/unserved surplus.
- `supply_fraction_scenarios.csv` stores \(s_i=W_i\alpha\) separately, with
  alpha values 0.05, 0.10, 0.20, 0.30, and 0.40. These are illustrative
  assumptions only.
- `receiver_capacity_shares.csv` stores normalized hypothetical \(q_j\)
  distributions. Actual capacities are generated as
  \(C_j=\beta(\sum_i s_i)q_j\).
- The original complete OSRM route matrix remains in
  `data/scenario/eligibility_matrix.csv`; the refinement engine derives
  distance-based geographic edges from it. It does not overwrite the original
  route results.

## Experiments

`scenario_experiment_results.csv` stores the deterministic parameter grid and
one comparison row per greedy sender order. Parameters include alpha, beta,
capacity-share distribution, road-distance threshold (or complete network),
strict geocoding quality, and greedy order. Results include Stage 1 maximum kg,
Stage 2 kg-km and average km/kg, greedy kg and kg-km, unallocated supply, and
remaining receiver capacity.

Scenario IDs are deterministic hashes of canonical parameter JSON, greedy
order, and seed. The current methods are deterministic and use no random
sampling; recorded seed is zero. Since alpha scales both supply and beta-based
capacities uniformly, experiment LP and greedy outcomes are solved once per
other parameter combination and scaled linearly for alpha.

Geographic thresholds of 5, 10, 15, 20, and 25 km are hypothetical
maximum-distance settings. The complete-network benchmark is also included.
The optional strict quality scenario requires both endpoints to have a
road-and-house-number Photon match and OSRM snap metadata. It retains
co-located businesses meeting this rule.

`google_restaurant_closing_times.csv` is a separate, partial enrichment table:
it records Google Search/Maps closing-time results, the query, lookup date,
match status, and notes for sender/day pairs that could be matched to the
listed restaurant location. Blank or absent records mean unknown; they are
never filled with a common or generated time. The current lookup covers only
a small subset of 1,795 senders. A location alias is marked separately and
must not be mistaken for an independently verified listing.

`seoul_restaurant_hours_coverage.csv` is a separate one-row-per-sender coverage
ledger built from Seoul Open Data dataset OA-21054. It retains only exact
normalized Korean business-name plus road-number matches and preserves the
source's raw operating-hours text. The 2026-11-11 snapshot contains 29 exact
matches with schedule text; 1,766 senders have no exact match. One match has
duplicate source rows whose schedule text agrees after ignoring whitespace.
These are not day-specific parsed closing times, so this ledger does not
complete the 1,795-restaurant deadline database. Rebuild it with
`.\.venv\Scripts\python.exe scripts\build_seoul_hours_coverage.py`.

For a complete, explicitly assumption-driven experiment input, see
`seoul_restaurant_hours_complete_scenario.csv` and
[`docs/seoul_complete_hours_scenario.md`](../../docs/seoul_complete_hours_scenario.md).
It contains seven weekday rows per sender. Only 29 senders have exact source
schedule text; the other 1,766 rows use clearly tagged schedule templates,
not asserted business hours. Do not mix these scenario values with verified
restaurant operating data.

The app's sourced-hours comparison uses each matched restaurant's own window:
closing time through closing time plus two hours, including midnight
rollovers. It evaluates only the matched-hours subset for the selected weekday.
The free drive-time proxy is OSRM road distance divided by an assumed average
speed, not a Google Maps ETA; each NGO-to-restaurant pair is checked
independently, without cumulative multi-stop scheduling.

The obsolete `deadline_window_experiment_results.csv` and
`hypothetical_closing_schedules.csv` outputs were removed during cleanup.
They contained hypothetical closing schedules, not observed restaurant hours.
Current source-hours results are generated separately by
`scripts/run_seoul_deadline_experiment.py`.

## Audits

- `data/reports/seoul_reported_waste_distribution.csv` gives summary
  statistics for nationwide restaurant records, original Seoul records, and
  deduplicated Seoul senders.
- `data/reports/seoul_large_reported_quantities_review.csv` lists top values
  and Tukey-fence flags. A statistical flag is a review signal, not proof of a
  source error.
- `zero_distance_pairs.csv` lists the seven OSRM zero-distance sender/receiver
  pairs for review.
- [`docs/route_quality_audit.md`](../../docs/route_quality_audit.md) reports
  geocoding match quality, shared coordinates, missing metadata, snap offsets,
  and the strict quality rule.
- [`docs/scenario_parameters.md`](../../docs/scenario_parameters.md) and
  [`docs/research_limitations.md`](../../docs/research_limitations.md) define
  assumptions and interpretation limits.

## Historical-throughput-weighted capacity experiment

`scripts/run_seoul_historical_capacity_experiment.py` builds an additional
scenario where 2025 provision quantities determine only the relative capacity
shares among the 31 exact-name-matched Seoul sites. The `수량` unit is unstated,
so those historical quantities are normalized as shares only; they are not
converted to kilograms or interpreted as capacities. The unmatched
nationwide-level directory row receives zero modeled share. Total hypothetical
capacity is set equal to scenario supply (`beta=1`), with 10% of reported
expected waste treated as scenario supply (`alpha=0.10`).

The script compares the same LP and nearest-receiver greedy baseline under
identical scenario constraints for 5, 10, 15, 20, and 25 km distance cutoffs,
plus a complete-network benchmark. Distance eligibility is still an assumption,
not observed donation acceptance. It writes the capacity shares,
LP/greedy comparison results, and detailed LP/greedy assignments for the 15 km
case to `historical_provision_weighted_capacities.csv`,
`historical_provision_weighted_lp_greedy_results.csv`, and
`historical_provision_weighted_15km_allocations.csv`, respectively. All outputs
are labeled as hypothetical scenarios, not measured NGO capacities or
confirmed food donations. The observed comparison is summarized in
[`docs/historical_capacity_lp_vs_greedy.md`](../../docs/historical_capacity_lp_vs_greedy.md).

## Rebuild

From the repository root with project dependencies installed:

```powershell
.\.venv\Scripts\python.exe scripts\prepare_seoul_refinement.py
.\.venv\Scripts\python.exe scripts\run_seoul_experiments.py
.\.venv\Scripts\python.exe scripts\run_seoul_deadline_experiment.py
```

The runner consumes the retained route matrix and makes no external network
requests.
