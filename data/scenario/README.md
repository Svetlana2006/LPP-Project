# Seoul monthly food-allocation scenario

> This directory is the preserved v1 input set. It retains the original
> all-reported-waste, equal-capacity, all-pairs scenario and its route matrix.
> The refined alpha/beta/geographic experiments are in
> [`data/scenario_refined/README.md`](../scenario_refined/README.md). The
> duplicate v1 repository snapshot was removed; current source tables and
> provenance remain in `data/processed/`, `data/raw/`, and `docs/`.

These are complete model inputs for a **hypothetical scenario**, not observed donation/redistribution data.

## Files

- `senders.csv`: 1,795 Seoul restaurant sender nodes.
- `receivers.csv`: 32 Seoul food-bank directory entries.
- `eligibility_matrix.csv`: all 57,440 sender-receiver pairs, explicitly marked eligible by assumption and annotated with OpenStreetMap-based driving-route distance estimates.
- English-readable reference copies are in `data/processed/korea_seoul_restaurant_waste_observations_en.csv` and `data/processed/korea_foodbank_sites_en.csv`. Original Korean names and addresses are retained in parallel columns.
- `data/processed/seoul_osm_geocoding.csv` records the address geocoding results; `data/processed/seoul_osm_routed_locations.csv` records geocoded points and the road-network snap locations used by OSRM.

## Applied assumptions

1. The official Public Data Provision Standard defines `PROD_QTY` as expected food-waste discharge in kg/month. Every selected reported amount is assumed to be edible, unserved, available, and redistributable.
2. The amounts are assumed to apply to the modeled period, November 1–30, 2026. This is a scenario assumption; the government source reference dates do not document that specific period.
3. Each of the 32 listed Seoul food-bank sites is assigned the same assumed capacity: total selected supply divided by 32, or 161,937.35 kg/month.
4. Every restaurant-site pair is assumed eligible.
5. “Pickup time is 2 hours + closing time” is interpreted as pickup within two hours after the restaurant closes. Actual business closing times, food acceptance, safety, and receiving windows are not present in the sources and have not been verified.
6. Addresses are geocoded against a locally hosted Photon 1.0.0 instance using a South Korea OpenStreetMap extract, then routed with the OSRM demo server's `driving` profile. Results are point-to-point route-distance estimates, not verified vehicle trips, traffic-aware travel times, or evidence that pickup is operationally possible. Geocoding match quality and OSRM snap offsets are retained for review.

## Scenario totals and interpretation

- Total sender supply: 5,181,995.20 kg/month.
- Total receiver capacity: 5,181,995.20 kg/month.
- The final route matrix contains all 57,440 sender-to-receiver estimates, retrieved 2026-11-10 UTC. Distances range from 0 to 42.838 km; the median is 14.146 km. Seven pairs have a reported distance of 0 km and should be reviewed before any operational use.
- All 1,735 unique addresses received coordinates. The retained match-quality labels are: 1,216 road-and-house-number matches, 301 partial-address matches, 210 approximate Seoul matches, and 8 street-only approximations. The latter 519 are not building-level exact matches; the route distances involving them are correspondingly uncertain. The maximum OSRM road-network snap offset was 119.386 m.
- The LP solver reached optimal status and allocated 5,181,995.20 kg; the nearest-receiver greedy baseline was feasible and allocated the same amount. This tie follows from assumed complete eligibility and total receiver capacity deliberately equal to total supply. It does not show strict LP improvement or route optimization by the LP.
- The greedy assignment's kilogram-weighted average one-way route distance was 8.811 km. This is descriptive only: the LP maximizes kilograms and does not minimize distance, so it is not a distance-performance comparison.
- Match-quality labels describe the presence of OSM road/house-number signals, not calibrated probabilities of address accuracy. The 210 approximate and 8 street-only matches in particular need manual review before operational use.
- One repeated restaurant business/address record was collapsed to one sender node, retaining the row with the latest source reference date. This is a practical deduplication rule, not a confirmed government establishment identifier.
- English proper-name and address fields use Revised Romanization for Korean text where an official English rendering is not available. Original Korean is preserved; the romanized field is not a certified business-name translation or verified postal address.

## Rebuild

From the repository root, run:

```powershell
.\.venv\Scripts\python.exe scripts\build_seoul_scenario.py
```

The script requires the optional `research` dependency (`ko-pron`) declared in `pyproject.toml`.

To prepare the local Photon database, download the Photon 1.0.0 JAR and the matching South Korea JSONL dump from the URLs in `docs/source_register.md`. The JAR's published SHA-256 is `b2eaad11add95aad149d1e72e67a4df5f6694e725ac5363793a912c5b3e3a7df`. Then import the dump into an empty directory (the import streams decompressed data and does not create an uncompressed copy):

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[research]"
.\.venv\Scripts\python.exe scripts\import_photon_dump.py `
  --dump "$env:TEMP\lpp-photon-seoul\photon-dump-korea-1.0-latest.jsonl.zst" `
  --jar "$env:TEMP\lpp-photon-seoul\photon-1.0.0.jar" `
  --data-dir "$env:TEMP\lpp-photon-seoul\photon-db"
```

In a separate PowerShell window, start Photon from the imported database directory:

```powershell
Set-Location "$env:TEMP\lpp-photon-seoul\photon-db"
java -jar "$env:TEMP\lpp-photon-seoul\photon-1.0.0.jar" serve
```

With Photon running locally, geocode addresses and request OSRM route distances:

```powershell
.\.venv\Scripts\python.exe scripts\enrich_seoul_routes.py
```

The route script caches successful local geocodes and refuses to write a partial route matrix if any address or eligible route is missing. OpenStreetMap data are © OpenStreetMap contributors, ODbL 1.0. The Photon service must be stopped before deleting its temporary database.
