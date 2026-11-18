# Seoul restaurant-hours coverage audit

## Current coverage

The 1,795-row source union contains source-listed hours for **42 distinct
senders** and leaves **1,753 unresolved**:

| Source | Distinct senders | What is retained |
|---|---:|---|
| Seoul Open Data tourist-food dataset OA-21054 | 29 | Original hours prose, matched source IDs, listing URL, and snapshot date |
| Existing Google Search/Maps lookups | 7 | Source-file reference, checked dates, and matched weekday-row counts; the closing-time values remain in the separate lookup file |
| OpenStreetMap | 6 | Raw `opening_hours` tag, OSM object ID/link, match evidence, snapshot version, and ODbL attribution |

These source groups do not overlap in the current union. The result is a
**partial source index**, not a complete or independently field-verified
schedule for all senders. A missing source match means unknown, not closed.

The 29 tourism records contain operating-hours prose, which is not
automatically converted to weekday closing times. The six OSM records retain
their original `opening_hours` expressions; those expressions are likewise
not yet converted into daily closing times for the LP. The seven Google lookup
records are the only source currently providing day-specific closing-time
rows to the existing comparison flow. Do not treat source-listed hours as
proof that food is edible/donatable, that an NGO will accept it, or that a
pickup is feasible.

## LP-ready assumption scenario

The LP-ready schedule at
`data/scenario_refined/seoul_lp_daily_hours_scenario.csv` has 12,565 rows
(1,795 senders × seven weekdays). It uses the 43 available location-matched
Google sender-day closing-time lookups. Every other sender-day is explicitly
assigned the user-requested **assumed 21:00 close**, including records with
tourism/OSM prose that has not been safely interpreted into a daily schedule.
Each row labels whether its close is a lookup or a scenario assumption and
retains a note when other source hours were not used.

The corresponding LP run assumes NGOs can accept deliveries through **23:00**.
For each sender-day, the direct-drive window is capped at the earlier of
closing time + two hours and the 23:00 receiver cutoff. Receiver opening times
and actual NGO capacity remain unknown. This is an assumption scenario, not
observed operating data.

The seven-day LP/greedy run is in
`data/scenario_refined/seoul_lp_hours_scenario_results.csv`, with its
limitations and summary in `docs/seoul_lp_hours_scenario.md`. The run uses
alpha=10% of reported expected waste as a scenario supply, not a measured
donatable-food quantity.

## OpenStreetMap extraction and matching

A Geofabrik South Korea OSM extract (`south-korea-261116`, retrieved
2026-11-17) was processed locally after public Overpass queries timed out.
Restaurant, fast-food, cafe, food-court, and ice-cream features were considered
when they had both a name and an `opening_hours` tag. A sender was counted only
when the normalized Korean business name matched exactly, it was within 50 m
of a high-quality sender coordinate or had an exact OSM road-address match,
and its address tags did not conflict. Six sender records passed this rule.
Near matches and conflicting records are not included as usable hours.

The retained OSM records link to their source objects and include the source
version/date and attribution. The 278.5 MiB country extract is not included in
the repository; only the six matched records are retained. OSM is community
maintained, so the tags may be incomplete or out of date. Reuse must comply
with the Open Database License (ODbL 1.0) and include attribution.

## Existing Seoul tourism source

The full Seoul Open Data tourist-food snapshot downloaded on 2026-11-11
contains 6,883 multilingual rows; 1,442 are Korean listings and 1,422 have
non-empty hours text. Conservative matching by normalized Korean business
name and road name/number found 29 sender records. One sender has two duplicate
source rows whose schedules agree after whitespace normalization; both source
IDs are retained.

This tourist-food listing is not a comprehensive register of the waste
generators. Address-only matches are not accepted because a building can
contain multiple venues. Same-name records at different addresses are also
rejected.

## Files and rebuilds

- `data/scenario_refined/seoul_restaurant_hours_coverage.csv`: 1,795-row
  coverage ledger for OA-21054 only.
- `data/scenario_refined/seoul_osm_restaurant_hours.csv`: exact-name OSM
  candidates with match status; only `matched_exact_name_and_location` rows
  are included as hours in the union.
- `data/scenario_refined/seoul_restaurant_hours_source_union.csv`: one row per
  sender, combining accepted source evidence while leaving unknowns blank.
- `data/scenario_refined/google_restaurant_closing_times.csv`: existing
  Google lookup rows, retained separately; the union does not duplicate their
  closing-time values.
- `data/raw/seoul_tourism_food_OA-21054_2026-11-11.csv`: untouched Seoul
  tourism source snapshot (CP949 encoding).

Rebuild the Seoul tourism coverage and source union:

```powershell
.\.venv\Scripts\python.exe scripts\build_seoul_hours_coverage.py
.\.venv\Scripts\python.exe scripts\build_seoul_hours_source_union.py
```

Rebuild the OSM match file from a downloaded South Korea extract:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[research]"
curl.exe -L --fail -o "$env:TEMP\south-korea-261116.osm.pbf" https://download.geofabrik.de/asia/south-korea-261116.osm.pbf
.\.venv\Scripts\python.exe scripts\import_seoul_osm_hours.py --pbf "$env:TEMP\south-korea-261116.osm.pbf"
.\.venv\Scripts\python.exe scripts\build_seoul_hours_source_union.py
```

The importer targets that dated extract; update its source-version constants
when using a newer snapshot.

## Other candidate sources checked

KTO TourAPI exposes restaurant operating-time fields but remains unavailable
through the signup path reported by the user. Geoapify's Places API requires
registration and an API key; no key was available for this run. Foursquare
also returned no usable public data without API access. Neither source
contributed records. No hours were imputed from neighborhood patterns.

## Sources and limitations

Seoul Open Data OA-21054 is listed at
<https://data.seoul.go.kr/dataList/OA-21054/S/1/datasetView.do>. Its portal
record lists monthly updates and Korea Open Government License Type 1
(attribution; commercial use and modification allowed). Source hours may be
incomplete or stale for an individual business.

The OSM extract is from
<https://download.geofabrik.de/asia/south-korea-261116.osm.pbf>. OpenStreetMap
contributors' data is available under ODbL 1.0; see
<https://www.openstreetmap.org/copyright>.
