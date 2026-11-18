# Public-source database guide

## What is included

This repository now includes four curated CSV tables under `data/processed/`:

- `korea_restaurant_waste_observations.csv` — 14,476 rows classified as restaurants in the official South Korean large-scale food-waste generator extract.
- `korea_seoul_restaurant_waste_observations.csv` — the 1,796 restaurant rows whose reported administrative locality begins with Seoul.
- `korea_foodbank_sites.csv` — 440 organizations/sites listed in the Korea Foodbank public map directory; 32 entries are labelled in Seoul.
- `korea_foodbank_seoul_operations_2025.csv` — 2025 receipt and provision statistics for 31 of the 32 Seoul directory entries, matched by exact Korean name.

The original 26,574-row portal extract is retained at `data/raw/south_korea_large_food_waste_generators.csv`. It contains different establishment classes and is not the restaurant-only table.

The food-bank directory table deliberately contains only site name, administrative label, listed address, source, and snapshot date. Staff names, telephone numbers, and fax numbers present in the source page were excluded. Addresses are copied as listed, not geocoded or independently verified. An address may identify only a neighborhood rather than a street number.

## Table interpretation

The Korean government source field `PROD_QTY` is retained as `raw_reported_discharge_quantity`. The official Public Data Provision Standard, 20th revised edition, defines `배출량` as the reported expected amount of food waste and specifies `kg/월` (kg/month). The separate dataset catalog says the dataset refreshes annually; that is not the quantity interval. The source does not establish that the waste is edible, unserved, or redistributable. The curated source-data table therefore labels interpreting it as eligible supply as `PROXY` and sets `model_supply_eligibility` to `NOT_ESTABLISHED`.

The food-bank map establishes listed names and locations only. It does not publish additional receiving capacity in kilograms; `capacity_kg` is blank and `receiving_capacity_status` is `NOT_PUBLISHED`. A listed site is not automatically a confirmed receiver for a particular food type, donor, or collection window.

The official Foodbank operating-statistics page exposes 2025 receipt and provision figures by region for 31 named entries in the Seoul directory. All 31 were matched by exact Korean name. The national-level directory entry `전국푸드뱅크` has no separate Seoul site row. The page labels a field `수량` (quantity) but does not state its unit; the CSV marks both reported quantity units as `NOT_STATED`. These annual historical flows are not kilogram capacity, spare capacity, or a measure of how much a site can pick up from a restaurant now. The CSV keeps `additional_pickup_capacity_kg` blank and `capacity_status` as `NOT_PUBLISHED`.

The source restaurant and food-bank tables have no verified join key, food-acceptance evidence, operating-window compatibility, pickup commitment, or site-level capacity. A separate hypothetical Seoul LP input set now exists under `data/scenario/`; it makes user-requested assumptions explicit and labels all model node evidence `SCENARIO`.

## Snapshot profile

The downloaded government extract contains 26,574 rows, of which 14,476 are classified as restaurants. Restaurant source-reference dates range from 2023-05-20 to 2026-10-14. The restaurant extract has 192 missing road addresses and 57 repeated business-name/road-address groups (118 rows in those groups); these are retained as source observations, not silently deduplicated. The `observation_id` values are local identifiers assigned in extraction order, not government-issued IDs.

The map page reported 440 entries across its paginated directory. Three entries have no administrative-area label; none has a blank address field. Some address strings are still incomplete for street-level geocoding. The Seoul counts above indicate overlap in a city, not operational compatibility.

The operating-statistics snapshot was retrieved on 2026-11-18 with 2025 selected and Seoul regional statistics displayed. It returned 31 matching directory rows for both receipt and provision. The page provides counts, reported quantity, and book value; it does not display a unit for quantity. The table is preserved as reported, with no conversion to kilograms or inference of current capacity. The current CSV also preserves empty book-value fields where the site-level value was not verified from the captured result.

## Sources and reproduction

- Government dataset 15107746: <https://www.data.go.kr/data/15107746/standard.do>
- Korea Foodbank map: <https://www.foodbank1377.org/introduce/foodbankMap.do>
- Korea Foodbank operating statistics: <https://www.foodbank1377.org/statistics/statistics_new.do>
- Snapshot date: 2026-11-09

`scripts/build_korea_public_database.ps1` rebuilds the curated tables from the retained government extract and the live paginated Korea Foodbank map. The portal extract itself was retrieved from the dataset's official standard-data download endpoint. Re-running the script later may produce different directory rows or ordering; the current IDs are snapshot-local. Check item-level reuse terms before republishing the data.

## Scenario input and English-readable data

The complete assumed Seoul input set is documented in [`../data/scenario/README.md`](../data/scenario/README.md). Its quantities use the standard's kg/month unit, and its receiver capacities follow the requested equal-share assumption. It covers November 2026 by scenario assumption, assumes all reported discharge is distributable, gives every restaurant-site pair eligibility, and interprets pickup timing as within two hours after the restaurant closes. Source data do not verify those behavioral assumptions or actual closing times.

English-readable reference tables are provided for Seoul restaurants and food-bank sites. Column labels and generic categories are in English. Korean proper names and address names are rendered in Revised Romanization where available, while their original Korean values are retained. Romanization supports reading/search but is not certified English translation or verification of the business identity/address.

## Suitable next use

Run the scenario through the LP to demonstrate software behavior, with results labelled hypothetical. `scripts/enrich_seoul_routes.py` queries a locally hosted Photon instance built from a South Korea OpenStreetMap extract, then obtains point-to-point driving distances from the OSRM table service. The nearest-receiver greedy baseline uses those route distances; geocoding and routing remain estimates, not evidence of food acceptance or actual pickup feasibility. For empirical conclusions, replace the SCENARIO quantities/capacities/eligibility with source-supported values and verify a common period, site locations, food acceptance, and pickup windows.
