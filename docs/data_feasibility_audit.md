# Public-data feasibility audit

**Audit date:** 2026-11-09  
**Decision:** Record-level Korean restaurant and food-bank location tables have been assembled, and Seoul is a geographic-overlap candidate. The empirical optimization-data gate still fails. Do not report an empirical optimization result.

## Executive finding

The required sender-side variable is not total discarded food. It is the quantity of safe, edible, unserved food genuinely available for redistribution, measured for an identified sender and a defined period (`eligible_surplus_kg`). The required receiver-side variable is additional food that an identified receiving site can use and accept during that same period—not historic receipts, distribution totals, inventory, meal counts, or beneficiary counts.

The official South Korean sources now provide real, named restaurant observations and food-bank map locations, but they do not establish both required model variables:

- The Korean government dataset was retrieved and profiled: 26,574 rows in total, including 14,476 rows classified as restaurants. It provides business names, administrative locality, and reported addresses. The official Public Data Provision Standard, 20th revised edition, defines `PROD_QTY` (`배출량`) as the reported expected food-waste amount, in `kg/월` (kg/month). This defines its unit and monthly basis, but not safe/edible/unserved status or whether local records comply. Only the user's explicit scenario assumption can treat it as eligible supply.
- Korea Foodbank's open-data catalog describes historic operating statistics for users, facilities, donors, receipts, provision, items, centres, and preferred-item quantities. These are potentially useful for identifying parts of the redistribution system, but the catalog does not establish additional demand or maximum additional receiving capacity at each actual receiving site. Historic receipt/provision statistics are not substitutes for that capacity.
- The official operating-statistics page was also inspected directly: its 2025 Seoul regional receipt and provision views return 31 named directory entries with historical counts, `수량` (quantity), and book value. All 31 match by exact Korean name. The national-level `전국푸드뱅크` entry has no separate Seoul site row. The page does not state the quantity unit, and annual historic flows do not measure additional pickup capacity.
- Mapo Itta Food Bank's public board lists monthly 2025 receipt posts for branch 1. Its March 2025 receipt-ledger PDF was retrieved and inspected; it contains dated donation records, product quantities, descriptions, and prices. Most quantities are not weights, so the ledger is not a consistent physical quantity series and does not establish spare capacity. Donor names are masked and were not copied into project data.
- Korea Foodbank's public map directory contains 440 listed site entries; 32 are labelled in Seoul. The directory provides names and addresses, not extra receiving capacity or proof that a listed site can accept food from a particular restaurant.
- The two Korean sources have no documented join key, compatible observation period, or shared operational definition. Their city-level geographic overlap does not establish pair eligibility.

International sources reviewed include FAO's Food Loss and Waste Database, Eurostat's food-waste statistics, Feeding America's Map the Meal Gap, and the UK WRAP source candidate. They are valuable for context or aggregated evidence, but their public descriptions do not establish a matched network of individually identified sender supplies and receiver additional capacities. For WRAP and some interactive portals, this audit records only the accessible catalog/page evidence; it does not claim that every downloadable record or API response was inspected.

The source tables form a **location and waste-context database**, not an empirical optimization dataset. They do not establish eligible surplus, site capacity, or operational pair eligibility. The preserved v1 scenario in `data/scenario/` applies the original all-waste, equal-capacity, all-pairs assumptions. The refined v2 scenario in `data/scenario_refined/` separates reported expected waste from alpha-scaled scenario supply, varies hypothetical capacity distributions and distance-based geographic networks, and performs two-stage LP experiments. Neither scenario represents measured redistribution data. The 57,440 route estimates remain a complete pairwise route-distance matrix; 519 unique address queries have partial, approximate, or street-only matches.

The curated files and field meanings are documented in [`public_database_guide.md`](./public_database_guide.md). The reported quantity is standardized as expected food-waste kg/month, but that does not make it safe, edible, unserved, or donated food. OpenStreetMap routes estimate distances only; they do not prove an eligible restaurant-to-site connection.

## Decision rule and evidence labels

A city qualifies only when public evidence establishes all of the following for one compatible period:

1. Multiple identifiable sending sites and site-specific numerical eligible surplus.
2. Multiple identifiable receiving sites and site-specific additional requirement or additional receiving capacity.
3. Compatible units and periods, with a reproducible unit conversion if needed.
4. Verifiable locations and evidence-based pair eligibility, including food acceptance and timing where relevant.
5. Provenance and reuse terms, and enough overlapping feasible connections to make an allocation comparison meaningful.

Every model input must be labelled:

- **OBSERVED:** directly reported numerical observation or administrative record.
- **DERIVED:** reproducibly calculated from directly reported values with compatible units and periods.
- **PROXY:** related value that does not directly measure the required model input.
- **SCENARIO:** hypothetical or synthetic value.

Only OBSERVED and defensibly DERIVED values can be empirical model inputs. A PROXY or SCENARIO cannot be relabelled as observed supply or capacity.

## Candidate-source findings

| Candidate | Sender-side evidence | Receiver-side evidence | Period, units, location, and licensing | Verdict |
|---|---|---|---|---|
| South Korea — Nationwide Standard Data for Large-Scale Food Waste Discharge Businesses | Retrieved 26,574 rows; 14,476 are classified as restaurants. Names and addresses support location research. `PROD_QTY` is an expected monthly food-waste amount, standardized as kg/month; it is **PROXY** for edible surplus unless treated as such under the user's scenario assumption. | None. | Restaurant source-reference dates range 2023-05-20 to 2026-10-14; those dates are not the monthly supply period. The standard defines kg/month, but record-level compliance is not independently verified. Public Data Portal lists free access; item-level reuse terms still require review. | **Fails as empirical supply**; supports a clearly labelled scenario if all waste is assumed redistributable. |
| South Korea — Korea Foodbank public map directory | None. | Retrieved all 440 paginated site listings, including names and listed addresses; 32 are labelled in Seoul. | No site-specific additional capacity, accepted food types, pickup times, or compatible donor period are published in this map. Some addresses are not street-number precise; the source directory contains no geocoded coordinates. The separate Seoul scenario uses estimated Photon coordinates. Staff and phone/fax fields were excluded. | **Fails** for capacity and pair eligibility; useful receiver-location directory only. |
| South Korea — Korea Foodbank Open Data and operating statistics | Donor, receipt, item, and related operating statistics may provide historic donation activity; item quantities and donor categories are not demonstrated to represent restaurant-level safe, unserved surplus available in a matching collection round. | 2025 Seoul page provides receipt/provision statistics for 31 directory entries matched by exact name. This is historic throughput, not additional demand or capacity; page quantity unit is unstated. | API still requires portal access; the public operating-statistics page was directly inspected on 2026-11-18 and its 31 matched rows retained in `data/processed/korea_foodbank_seoul_operations_2025.csv`. The national-level directory entry has no separate Seoul row. | **Fails** as an empirical capacity dataset; provides partial historic-flow context only. |
| Portugal — FIKWaste restaurant-kitchen dataset | Four weeks of sensor-based waste-bin volume measurements from three restaurant kitchens; the kitchens are identified only as Kitchen 1–3. No exact restaurant names or addresses are provided. | None paired. | Dataset fields include timestamp, distance, and volume. Bin volume is not verified mass or eligible edible/unserved surplus. The dataset does not identify a receiver network. | **Fails** the named-site and model-input requirements; useful anonymous waste-monitoring research only. |
| FAO Food Loss and Waste Database (international) | The database aggregates reported studies, publications, and grey literature; it can include food-service evidence, but the catalog describes data by products, value-chain stages, and geography, not a standardized set of individual restaurant nodes with eligible surplus for a common round. Where a study reports total food waste, that remains a **PROXY** unless it independently establishes edible, unserved surplus. | No matched receiving-site demand/capacity dataset is supplied by the database description. | Live searchable/downloadable collection; page reported nearly 40,000 data points from 167 countries as of January 2026. Units, periods, and site granularity vary by underlying study and must be checked record by record. It is a discovery source, not a ready-to-join network. | **Fails** as a standalone allocation dataset; useful for literature and context. |
| European Union — Eurostat food-waste statistics (`env_wasfw`) | Provides official food-waste statistics, including sector/country reporting; aggregated sector totals do not identify individual restaurant supply or edible, unserved fractions. Therefore a **PROXY**, not `eligible_surplus_kg`. | No receiving-site capacity field. | Public Eurostat table; national/sector/time dimensions can support contextual comparisons but do not match sender and receiver sites. | **Fails** for the required node-level network. |
| United States — Feeding America, Map the Meal Gap | County/community-level food insecurity estimates do not identify individual food-sending establishments or their eligible surplus. | Estimates food insecurity, not each receiving site's additional food requirement and physical acceptance capacity. | Public interactive resource; geography is community/county-level rather than matched sender/receiving sites. | **Fails** for node-level supply/capacity. |
| United Kingdom — WRAP food surplus and waste reports | Public reports are a potential source of sector-level estimates and research references; the page could not be retrieved successfully in this review, and no individual sender dataset or eligible per-site supply was verified. | No matched receiving-site capacity field verified. | Downloadable report, record granularity, period, and license require separate inspection before use. | **Conditional research lead**, not qualifying evidence. |

The detailed field-by-field comparison is in [`dataset_comparison.csv`](./dataset_comparison.csv).

## Specific review of the Korean candidates

### Government food-waste dataset

The official catalog describes a nationwide standard dataset managed by local governments and lists establishment-level descriptors and `discharge volume` among its fields. The complete download returned 26,574 rows; 14,476 have business type `음식점` (restaurant). The current restaurant table retains 14,476 observations, including repeated name/address combinations, and the Seoul subset contains 1,796 rows. There are 192 restaurant rows without a road address. Repeated business/address observations are retained, not silently deduplicated.

The catalog lists annual update frequency; this describes dataset refresh cadence, not the quantity interval. The official Public Data Provision Standard defines the field as expected kg/month. Its `CRTR_YMD` source-reference dates in the restaurant extract range from 2023-05-20 to 2026-10-14; these do not define which month the expected amount applies to, and record-level compliance with the standard is not independently verified. The catalog does not identify whether the discharged material is safe, edible, or unserved; waste may include spoiled food, plate waste, preparation scraps, and other ineligible material. It is not empirical eligible surplus. For a scenario only, the user explicitly assumes it all redistributable.

Sources: [Public Data Portal — Nationwide Standard Data for Large-Scale Food Waste Discharge Businesses](https://www.data.go.kr/data/15107746/standard.do); [Public Data Provision Standard, 20th revised edition, section 165 (official notice and attachments)](https://www.data.go.kr/bbs/rcr/selectRecsroom.do?originId=PDS_0000000001252). The standard defines `배출량` as `신고한 음식물류 폐기물의 배출 예상량` (reported expected amount of food waste) and sets its unit to `kg/월` (kg/month). It distinguishes `자가처리량` (self-treatment amount) as `kg/일` (kg/day). The dataset's annual refresh is not the measurement period. This standard does not establish edible surplus.

### Korea Foodbank open data

The provider's catalog describes eight API services: user, facility/organisation, donor, receipt, provision, item, centre, and preferred-item information. It describes operational sizes such as amounts, counts, users, items, and prior-day preferred-item inventory. Its file-data catalog includes statistics on donated-item receipt and provision, centre information, and donor information. These are not described as an additional quantity each receiving site can accept in a future collection period. Neither historic receipts nor distributions prove spare capacity or unmet demand.

The provider states that API use involves applying through the Public Data Portal and obtaining a development API key. The actual API field schemas and downloadable files were not retrieved or row-audited for this audit. The descriptions alone are enough to reject historic operations as a substitute for additional capacity, but not enough to assert that no useful fields exist in every API response. Further inspection may refine the source assessment; it cannot be used to silently reinterpret historical amounts as capacity.

The provider's public [operating-statistics page](https://www.foodbank1377.org/statistics/statistics_new.do) can be viewed without the API workflow. With 2025 and Seoul regional statistics selected, the receipt and provision tables return 31 named rows that match 31 Seoul directory entries by exact Korean name. The national-level `전국푸드뱅크` entry has no separate Seoul row. The page shows counts, `수량` (quantity), book value, and share, but no unit for quantity. The source rows are preserved in `data/processed/korea_foodbank_seoul_operations_2025.csv`; they are historical flow measures only. We do not convert the quantity to kilograms or use it as current or additional pickup capacity.

The [Mapo Itta Food Bank donation-status board](http://www.mapofood.com/main/sub.html?page=2&boardID=www21&keyfield=&key=&bCate=) lists monthly 2025 receipt posts for Mapo branch 1. Its March 2025 receipt-ledger PDF was retrieved and inspected; it documents dated donations, item quantities, descriptions, and prices. Most quantities are not weights, so it is not a consistent physical quantity series. Receipt records are historical throughput, not spare capacity. Donor names are masked in the public attachment and were not copied into project data.

Source: [Korea Foodbank — Open Data](https://www.foodbank1377.org/reference/openData.do).

### Korea Foodbank public map

The official map page reports 440 records and paginates them in groups of ten. All 44 pages were retrieved on 2026-11-09. The curated file [`data/processed/korea_foodbank_sites.csv`](../data/processed/korea_foodbank_sites.csv) retains site name, administrative area, and address as listed. Thirty-two entries carry a Seoul administrative-area label. Three records lack an administrative-area label; no address fields are blank, although some values identify only a neighborhood and are not sufficient for reliable geocoding. The Seoul scenario geocodes these addresses with Photon; those coordinates are estimates and do not verify site operations.

The map includes central and local food-bank/market listings. It does not show the amount a site can additionally receive, accepted-food categories, pickup windows, or a confirmed donor relationship. A listed site is therefore a location lead, not a validated LP receiver. Staff names, telephone numbers, and fax numbers present in the page were deliberately excluded from the curated output.

Source: [Korea Foodbank — Foodbank map](https://www.foodbank1377.org/introduce/foodbankMap.do).

### Geographic overlap candidate: Seoul

The government extract has 1,796 restaurant-classified rows whose administrative locality begins with Seoul; the scenario deduplicates one repeated business/address to create 1,795 sender nodes. The Korea Foodbank map lists 32 sites with a Seoul area label. The scenario has estimated routes between every sender and receiver, but these distances do not establish that any restaurant can donate to any site. Pair eligibility and equal receiver capacities remain explicit SCENARIO assumptions, not inferred or observed facts.

## Classification of the contemplated inputs

| Input | Current evidence | Classification | Use in empirical model now? |
|---|---|---|---|
| Korean discharge volume | Official standard defines expected food-waste amount in kg/month; edible/unserved status is not documented | PROXY for eligible surplus; SCENARIO when user assumes all can be redistributed | Empirical: no; scenario: yes, with explicit caveats |
| Restaurant name/address in the Korean extract | Direct administrative listing; 14,476 restaurant-classified rows, with incomplete addresses in some records | OBSERVED for the listed identity/location fields only | Location research only |
| Korea Foodbank map name/address | Direct public map listing; 440 entries, including 32 labelled Seoul | OBSERVED for the fields as listed only | Location research only |
| Korean food-bank historic receipt/provision amounts | 2025 regional dashboard reports per-site historic quantity and book value for 31 matched Seoul directory entries; quantity unit unstated and additional recipient capacity not established | PROXY | No |
| Preferred-item inventory | Provider describes a previous-day stock quantity for preferred items; stock is not the same as additional demand/capacity | PROXY | No |
| FAO study measures | Study-specific; definitions, units, periods, and aggregation vary | OBSERVED only for the exact measure a source reports; often PROXY for eligible site-level supply | Not without source-level verification and compatible receiver data |
| OSM-based route distances from geocoded locations | Reproducible route calculation, with address-match and road-snap uncertainty; not food acceptance or full route feasibility | DERIVED | Scenario route ordering only; not evidence that an edge is operationally eligible |
| Any generated values used to exercise the model | Hypothetical | SCENARIO | Scenario analysis/software exercise only; never empirical results |

## What is needed to reopen the empirical-data gate

1. Quantity unit is established by the official field standard as expected kg/month. Remaining government-source checks include record-level compliance, meaning of each source reference date, actual record grain, and duplicate identity. The source does not establish edible/unserved status.
2. Obtain the Korea Foodbank API documentation and/or files; record exact field definitions, granularity, units, time periods, location identifiers, and reuse conditions. Determine whether any field directly measures future additional receiving capacity. The public 2025 dashboard is only historical flow context and its quantity unit is unstated; it cannot provide \(c_j\).
3. Check public municipal and site-level annual/monthly reports for each of the 32 directory entries. Preserve only site identity, period, activity measure, explicit unit, and source; treat receipt/provision as historical flow, not capacity. The Mapo branch 1 board is an initial lead, not evidence that all sites publish similar records.
4. Identify a public source that measures eligible surplus for multiple individual sending sites and a separate or integrated source that measures additional capacity for multiple identifiable receiving sites for compatible periods.
5. Verify a documented join, food categories, receiving windows, and license compatibility. Scenario coordinates and distances are geocoded/routed using OpenStreetMap but remain unverified. Unknown food/time compatibility must not be set to eligible in an empirical model.
6. The November 2026 Seoul assumption set can be run as a labeled scenario. Re-run the empirical-data gate before presenting any output as an observed real-world result.

## Modeling and comparison guardrails

- The primary model is a continuous-variable LP that allows a sender's supply to be split across eligible receivers. Do not add a one-receiver-per-sender binary restriction unless evidence establishes that operational requirement; that would be a MILP.
- Keep both the LP and greedy method on identical sender supplies, receiver capacities, eligibility edges, and period.
- If the LP reaches its optimum and the greedy output is feasible for those same constraints, the LP objective is guaranteed to be **at least as large** as the greedy objective. It is not guaranteed to be strictly larger; a tie is valid and strict improvement depends on the instance.
- Report a simulated demonstration separately from an empirical case study. Do not describe scenario results as food rescued, available surplus, or NGO capacity in the real world.
- The model maximizes allocated kilograms. It does not minimize distance, establish food safety, confirm delivery, or certify multi-stop vehicle-route feasibility.

## Sources reviewed

- [South Korean Public Data Portal, dataset 15107746](https://www.data.go.kr/data/15107746/standard.do) — catalog metadata and field description.
- [Korea Foodbank, Open Data](https://www.foodbank1377.org/reference/openData.do) — official catalog descriptions and API/file access instructions.
- [FAO Food Loss and Waste Database](https://www.fao.org/platform-food-loss-waste/flw-data/en) — database scope and coverage description.
- [Eurostat food-waste statistics, dataset `env_wasfw`](https://ec.europa.eu/eurostat/databrowser/view/env_wasfw/default/table?lang=en) — official table landing page.
- [Feeding America, Map the Meal Gap](https://map.feedingamerica.org/) — public hunger/community context resource.
- [WRAP, food surplus and waste in the UK](https://www.wrap.ngo/resources/report/food-surplus-and-waste-in-the-uk-key-facts) — candidate report page; retrieval was unsuccessful during this review.
- [US EPA, Wasted Food Scale](https://www.epa.gov/sustainable-management-food/wasted-food-scale) — waste-management hierarchy/context; not node-level allocation data.

**Reproducibility note:** The Korean government extract was retrieved and row-profiled, and the official field standard was reviewed. All pages of the Korea Foodbank map directory were retrieved and row-profiled. This audit does not claim an exhaustive global dataset census or an API-level schema audit of Korea Foodbank's other services. The remaining evidence gaps are explicitly recorded rather than presented as facts.
