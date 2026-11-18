# Seoul Food-Rescue Allocation: Data, LP, Greedy Comparison, and Tests

## 1. Project purpose

This project formulates a food-allocation problem as a continuous linear
program (LP): allocate available food from restaurant senders to food-bank
receivers without exceeding sender supply, receiver limits, or the selected
sender-receiver eligibility network. A deterministic nearest-receiver greedy
algorithm is used as a baseline.

The project has two related goals:

1. Implement and test the optimization software on transparent inputs.
2. Explore how the LP and greedy baseline behave on a Seoul public-data-based
   scenario.

The second goal is **not** a validated operational food-rescue deployment.
The available public records do not establish which restaurant waste is safe,
edible, unserved, and donatable; nor do they publish each receiver's spare
pickup capacity. Accordingly, the model separates source observations from
assumptions and labels its allocations as hypothetical scenario results.

The central methodological rules are:

- Reported food waste is not automatically edible or donatable food.
- Historical food-bank receipt or provision is not additional capacity.
- The LP is guaranteed to allocate at least as many kilograms as a feasible
  greedy result when both use the same instance and the LP reaches its optimum.
  A strict LP improvement is **not** guaranteed.
- Distance-based edges and assumed capacity values in the Seoul model are
  scenario inputs, not verified donation permissions or operating limits.

## 2. Data required for a real allocation problem

A real operational instance needs, for one compatible planning period:

1. **Sender supply:** quantity of safe, edible, unserved food actually
   available at each identified sender.
2. **Receiver capacity or demand:** quantity each identified receiver can
   additionally accept or use in that same period.
3. **Pair eligibility:** evidence that a specific sender can donate the food
   type to a specific receiver, including geographic and time feasibility.
4. **Distance or route cost:** a comparable travel measure for every eligible
   pair, if distance is to be optimized.
5. **Common units and time basis:** for example, kilograms during the same
   day or week.

The Seoul sources provide identity, waste context, addresses, historic
operations, and estimated road distances, but they do not supply all those
operational facts. This gap is why model inputs below are explicitly marked
`SCENARIO`.

## 3. Source data and preparation

### 3.1 Restaurant sender observations

The South Korean Public Data Portal dataset [Nationwide Standard Data for
Large-Scale Food Waste Discharge Businesses (15107746)](https://www.data.go.kr/data/15107746/standard.do)
was downloaded as a source extract. It contains **26,574 records**, including
**14,476 records classified as restaurants**. The Seoul-filtered source table
contains **1,796 restaurant records**.

The government field `PROD_QTY` (`배출량`) is defined in the official data
standard as expected food-waste discharge in **kg/month**. This unit is useful
for constructing a scenario, but the field does not say that the material is
edible, unserved, safe, or accepted by an NGO. The source reference date is not
proof that the expected quantity applies to the model's specific month.

The 1,796 Seoul rows were reduced to **1,795 sender nodes** by collapsing one
repeated business-name/road-address record and retaining the row with the
latest source-reference date. This is a practical deduplication rule, not a
government establishment identifier. Source names, addresses, values, and
provenance are retained in the data tables.

Relevant files:

- `data/raw/south_korea_large_food_waste_generators.csv` — downloaded source
  extract.
- `data/processed/korea_restaurant_waste_observations.csv` — restaurant-class
  observations nationwide.
- `data/processed/korea_seoul_restaurant_waste_observations.csv` — Seoul
  restaurant-class observations before scenario deduplication.
- `data/scenario_refined/sender_observations.csv` — the 1,795 deduplicated
  Seoul sender nodes used by the refined model.

### 3.2 Receiver directory and historical operations

The Korea Foodbank public map lists **440 organizations/sites**, of which **32
are labelled Seoul**. It provides listed names and addresses, not extra
receiving capacity, food-type acceptance, pickup commitments, or proof of a
restaurant-to-site relationship.

The public 2025 Seoul operating-statistics tables contain receipt and
provision records matching **31 of the 32 directory entries by exact Korean
name**. The national-level directory listing `전국푸드뱅크` has no separate
Seoul site row. For the 31 matched sites, the reported provision quantities
sum to **10,396,277 source units**. The dashboard calls the field `수량`
(quantity) but does **not** state its unit. It must not be interpreted as
kilograms or converted to kilograms. These are annual historical flows, not
spare capacity.

Relevant files:

- `data/processed/korea_foodbank_sites.csv` — public directory snapshot.
- `data/processed/korea_foodbank_seoul_operations_2025.csv` — site-level
  2025 receipt/provision counts and quantities as reported. Capacity fields
  remain blank; an absent statistics row is not recorded as zero capacity.
- `data/scenario/receivers.csv` — the 32 receiver IDs, names, and locations
  used in the original scenario.

### 3.3 Locations and road distances

Restaurant and receiver addresses were geocoded against a locally processed
South Korea OpenStreetMap/Photon dataset. Among **1,735 unique address
queries**, **1,216** matched a road and house number; **519** had lower
precision (301 partial, 210 approximate, and 8 street-only). The model uses
these points as estimates, not field-verified locations.

Point-to-point driving distances were obtained from the OSRM public demo
service using the OpenStreetMap road network. The retained matrix contains
**57,440 sender-receiver pairs** (1,795 × 32). Distances range from 0 to
42.838 km; seven pairs have a reported distance of zero. These are pairwise
distance estimates, not traffic-aware travel times or complete multi-stop
vehicle routes.

Relevant files:

- `data/processed/seoul_osm_geocoding.csv`
- `data/processed/seoul_osm_routed_locations.csv`
- `data/scenario/eligibility_matrix.csv`
- `data/scenario_refined/zero_distance_pairs.csv`
- `docs/route_quality_audit.md`

### 3.4 Evidence versus assumptions

| Model concept | Public observation | What the model uses |
|---|---|---|
| Restaurant amount | Expected food-waste discharge \(W_i\), kg/month | \(s_i=\alpha W_i\), an assumed fraction treated as available scenario supply |
| NGO amount | 2025 historical receipt/provision activity; quantity unit unstated | A selected hypothetical capacity rule; no historical flow is called capacity |
| Sender-receiver relationship | No verified donor acceptance or service-area link | A scenario edge based on distance and, optionally, address-quality filters |
| Route distance | Estimated OpenStreetMap/OSRM pair distance | A pairwise distance coefficient in km |
| Closing time / receiving window | Partial location-matched hours exist for a small subset; most are unknown | Separate deadline scenarios use explicit assumptions or only matched records, as described in the related documentation |

Every model result is a planned allocation under its specified inputs; it is
not proof that food was accepted, picked up, or delivered.

## 4. How the LP is constructed

### 4.1 Sets, parameters, and units

- \(I\): restaurant sender nodes, with \(i\in I\).
- \(J\): listed receiver nodes, with \(j\in J\).
- \(W_i\): source-reported expected food waste for sender \(i\), in kg/month.
- \(\alpha\): assumed eligible fraction of expected waste. The sensitivity
  grid uses \(0.05, 0.10, 0.20, 0.30,\) and \(0.40\).
- \(s_i=\alpha W_i\): scenario supply in kg/month. This is not measured
  edible surplus.
- \(S=\sum_{i\in I}s_i\): total scenario supply.
- \(\beta\): assumed ratio of total receiving capacity to total scenario
  supply. The main sensitivity grid uses \(0.50, 1.00,\) and \(1.50\).
- \(q_j\): nonnegative receiver share, with
  \(\sum_{j\in J}q_j=1\).
- \(C_j=\beta S q_j\): hypothetical receiver capacity in kg/month.
- \(d_{ij}\): estimated pairwise OSRM road distance from sender \(i\) to
  receiver \(j\), in km.
- \(e_{ij}\in\{0,1\}\): scenario geographic-eligibility indicator.

### 4.2 Decision variable

\[
x_{ij}\ge 0
\]

is kilograms of scenario supply allocated from sender \(i\) to receiver \(j\)
during the modeled period. The LP is continuous, so one sender's supply may
be split among multiple receivers.

### 4.3 Stage 1: maximize allocated kilograms

\[
\boxed{\max Z=\sum_{i\in I}\sum_{j\in J}x_{ij}}
\]

Subject to sender supply:

\[
\sum_{j\in J}x_{ij}\le s_i
\qquad \forall i\in I
\]

Subject to receiver capacity:

\[
\sum_{i\in I}x_{ij}\le C_j
\qquad \forall j\in J
\]

Subject to pair eligibility and non-negativity:

\[
0\le x_{ij}\le \min(s_i,C_j)e_{ij}
\qquad \forall i\in I,\ j\in J
\]

If a pair is ineligible, its allocation is fixed to zero. If it is eligible,
its allocation cannot exceed either its sender's supply or receiver's
capacity. Stage 1 returns the maximum feasible allocated amount \(Z^\star\).

### 4.4 Stage 2: minimize pairwise kilogram-kilometres

The second LP uses the same supply, capacities, and eligible pairs, and fixes
total allocation at the Stage 1 optimum:

\[
\boxed{\min \sum_{i\in I}\sum_{j\in J}d_{ij}x_{ij}}
\]

subject to all Stage 1 constraints and:

\[
\sum_{i\in I}\sum_{j\in J}x_{ij}=Z^\star.
\]

The objective is kg-km. This lexicographic design maximizes food allocated
first and then minimizes pairwise distance **without reducing that maximum**.
It does not minimize full vehicle-tour distance, number of vehicles, elapsed
time, cost, or emissions. The solver is SciPy HiGHS with primal and dual
feasibility tolerances of \(10^{-8}\).

The implementation is in `src/food_allocation/solver.py`; typed model objects
are in `src/food_allocation/models.py`.

## 5. Capacity and eligibility scenarios

### 5.1 Main sensitivity grid

The original/refined experiment grid explores:

- **5 eligible-fraction values:** 5%, 10%, 20%, 30%, and 40%.
- **3 total-capacity ratios:** \(\beta=0.5, 1.0, 1.5\).
- **4 hypothetical capacity-share distributions:**
  - `uniform`: equal share to all 32 sites.
  - `linear_rank`: shares increase with alphabetical receiver-ID rank.
  - `quadratic_rank`: shares increase with the square of that rank.
  - `concentrated_75_percent_first`: 75% to the first alphabetical receiver
    and 25% divided among the remaining sites.
- **6 geographic networks:** maximum OSRM distances of 5, 10, 15, 20, or
  25 km, plus a complete-network benchmark.
- **2 location-quality settings:** all geocoded endpoints, or a strict
  road-and-house-number match at both endpoints.
- **3 greedy processing orders:** sender ID, fewest eligible receivers first,
  or largest supply first.

The full grid contains **2,160 result rows**:
\(5\times3\times4\times6\times2\times3\).
Because all supplies and beta-derived capacities scale together with
\(\alpha\), outcomes for the five alpha values are linear rescalings of the
same underlying network/capacity solve. Therefore, 2,160 rows are not 2,160
independent empirical trials.

### 5.2 Historical-throughput-weighted capacity scenario

A separate experiment uses the 2025 site provision quantities only to define
relative shares:

\[
q_j=
\frac{\text{2025 reported provision quantity}_j}
{\sum_{k\in J_{\mathrm{matched}}}
 \text{2025 reported provision quantity}_k}.
\]

The source quantity has no stated unit. This ratio is used only as a
dimensionless historical-throughput share; the source quantity is never
converted to kilograms or described as capacity. The 31 exact-name-matched
sites receive shares in proportion to this value. The unmatched
nationwide-level directory listing receives zero **modeled share** because
there is no separate Seoul statistic row. This is a modeling convention, not
evidence that its real capacity is zero.

For the focused run, the assumptions are \(\alpha=0.10\) and \(\beta=1.00\).
The deduplicated Seoul source expected-waste quantities total 5,181,995.20
kg/month, so scenario supply is **518,199.52 kg**. Total hypothetical capacity
is set equal to that supply and distributed by the historical shares. Thus
the capacity values in the output CSV are **throughput-weighted hypothetical
kg values**, not measured NGO capacities.

Files for this experiment:

- `scripts/run_seoul_historical_capacity_experiment.py`
- `data/scenario_refined/historical_provision_weighted_capacities.csv`
- `data/scenario_refined/historical_provision_weighted_lp_greedy_results.csv`
- `data/scenario_refined/historical_provision_weighted_15km_allocations.csv`
- [Detailed result interpretation](docs/historical_capacity_lp_vs_greedy.md)

## 6. Greedy baseline and comparison method

For each sender, the greedy baseline ranks its eligible receivers by nearest
road distance and assigns as much remaining sender supply as possible to the
nearest receiver with remaining capacity. It then proceeds to the next
receiver until that sender's supply is exhausted or no capacity remains. The
algorithm processes senders in one of the selected orders:

- `sender_id`
- `fewest_eligible`
- `largest_supply`

The broad experiment also uses identical supplies, receiver capacities, edge
sets, and distances for the LP and greedy result being compared. This matters:
an LP result and a greedy result from different assumptions are not a fair
algorithm comparison.

For any one instance, the greedy allocation is feasible for the LP's Stage 1
problem. Consequently, if the LP solver reaches the optimum,
\[
Z_{\mathrm{LP}}\ge Z_{\mathrm{greedy}}.
\]
This proves “no worse” on the **kilograms allocated** objective for a matched
instance, not a strict improvement. A tie is expected when greedy happens to
find a maximum allocation.

## 7. LP-versus-greedy results

### 7.1 Full sensitivity grid

The retained `scenario_experiment_results.csv` contains **2,160 matched
comparisons**:

- LP allocated strictly more kilograms in **1,035/2,160 (47.9%)**.
- LP and greedy tied in **1,125/2,160 (52.1%)**.
- LP allocated less in **0/2,160**.

The strict-win count is data- and scenario-dependent; it is not a promise of
real-world superiority. By geographic threshold, the strict-win counts were:

| Geographic network | LP strict wins | Ties | Comparisons |
|---|---:|---:|---:|
| 5 km | 260 | 100 | 360 |
| 10 km | 330 | 30 | 360 |
| 15 km | 270 | 90 | 360 |
| 20 km | 120 | 240 | 360 |
| 25 km | 55 | 305 | 360 |
| Complete network | 0 | 360 | 360 |

Across capacity ratios, the grid had 265 strict wins and 455 ties for
\(\beta=0.5\); 420 wins and 300 ties for \(\beta=1.0\); and 350 wins and 370
ties for \(\beta=1.5\) (720 comparisons each).

**Observed pattern:** strict improvements were most frequent at the 10 km
cutoff (330/360) and occurred in all complete-network comparisons as ties.
When the network is complete and total capacity equals total supply, the
greedy algorithm can allocate all supply, so there is no room for Stage 1 to
strictly improve. More generally, the LP's advantage appears when restricted
edges and uneven capacities create bottlenecks that a locally nearest-first
assignment can consume in an unhelpful order.

The win rate is not monotonic in distance threshold or capacity ratio.
Changing distance limits changes which senders compete for which receivers;
changing capacity shares changes the bottlenecks. The 25 km cases often tie,
but not all do. No claim is made that one threshold or one share rule is
empirically correct.

### 7.2 Historical-throughput-weighted run

This focused experiment contains six networks (5, 10, 15, 20, and 25 km,
plus complete network) and three greedy sender orders: **18 comparisons**.

- LP allocated at least as much as greedy in **18/18**.
- LP strictly allocated more in **13/18** and tied in **5/18**.
- There were **no cases where LP allocated less**.

| Distance cutoff | LP strict wins | Ties | Result pattern |
|---|---:|---:|---|
| 5 km | 3/3 | 0 | LP wins for each sender order |
| 10 km | 3/3 | 0 | LP wins for each sender order |
| 15 km | 3/3 | 0 | LP wins for each sender order |
| 20 km | 2/3 | 1 | Tie only for `fewest_eligible` |
| 25 km | 2/3 | 1 | Tie only for `fewest_eligible` |
| Complete network | 0/3 | 3 | All methods allocate the same total |

At 15 km, the LP allocated **518,199.52 kg** in Stage 1 and Stage 2. Greedy
allocated:

| Greedy sender order | Greedy kg | LP minus greedy |
|---|---:|---:|
| `sender_id` | 444,430.51 | 73,769.01 kg |
| `fewest_eligible` | 468,715.82 | 49,483.70 kg |
| `largest_supply` | 461,109.83 | 57,089.69 kg |

The 5 km and 10 km networks restrict the attainable LP total below total
scenario supply, but LP still beats all three greedy orders in this focused
run. At 15 km and wider, LP can allocate all scenario supply; greedy sometimes
does so and ties, or leaves some unallocated depending on sender order.

### 7.3 Is LP ever worse than greedy?

**On the primary objective—kilograms allocated—no.** In both retained
comparisons the LP is never below greedy. This follows from the LP's
optimization over the same feasible set, assuming an optimal solve and a
feasible greedy result; it is not a special property of the Seoul data.

This does not mean every LP result is “better” on every possible metric:

- Stage 1 optimizes kilograms, not distance.
- Stage 2 minimizes kg-km only among allocations that retain the maximum LP
  kilograms.
- A greedy run that allocates fewer kilograms is not an equal-volume
  comparison for total kg-km. Its kg-km may be lower simply because it moved
  less food.
- Neither objective measures complete vehicle routes, time, cost, or
  emissions.

When greedy ties the LP on kilograms, it is itself feasible at the LP optimum;
the Stage 2 optimum therefore cannot have higher total kg-km than that greedy
allocation on that same instance (up to solver tolerances). This distance
statement applies to equal-volume comparisons only.

## 8. Pickup-window experiments

The repository also contains separate experiments about restaurant-specific
closing times and NGO latest-arrival assumptions. These are not part of the
18-case throughput-weighted comparison above.

The sources contain only partial matched closing-hour observations. Unknown
restaurant hours are not treated as verified closing times. Separate scenario
tools support explicit assumed closing schedules, two-hour post-close windows,
an assumed 23:00 NGO cutoff, and estimated travel time from distance divided by
an assumed average speed. Pairwise windows do not model cumulative travel
between multiple restaurants, loading/service duration, or full tour order.
The Google-matched subset comparison is also limited to restaurants with
location-matched hours.

See `docs/google_closing_time_experiment.md`,
`docs/pickup_deadline_experiment.md`,
`docs/seoul_complete_hours_scenario.md`, and
`docs/seoul_lp_hours_scenario.md` for the distinct assumptions and results.

## 9. Automated tests and what they establish

The most recent full test run collected and passed **54 tests**. Tests use
small constructed examples and fixture data; they verify software behavior,
not the accuracy of public data or real operational assumptions.

| Test module | Tests collected | What they check |
|---|---:|---|
| `tests/test_allocation.py` | 13 | Hand-computed LP result and a case where greedy loses; tie behavior; sender/receiver limits; isolated nodes; upload schema, provenance, units, and deadline-order validation |
| `tests/test_refined_allocation.py` | 17 | LP/greedy bottleneck and order sensitivity; Stage 1/2 behavior; kg-km calculations; conservation and edge eligibility; normalized capacity shares; historical-weighted shares, unmatched site handling, and Seoul scenario construction |
| `tests/test_deadline_scenario.py` | 9 | Sender-specific matched close times, two-hour windows, 23:00 cutoff, exact-boundary feasibility, midnight rollover, missing distance/hours, and duplicate rejection |
| `tests/test_build_seoul_complete_hours_scenario.py` | 4 | Schedule extraction, overnight hours, deterministic complete-week scenario labels, and distinction between matched hours and assumed repeated closes |
| `tests/test_build_seoul_hours_coverage.py` | 6 | Exact business/address matching, address normalization, language duplicates, and conflicting schedule rejection |
| `tests/test_build_seoul_hours_source_union.py` | 2 | Source-union provenance, deduplication, and strict OSM match handling |
| `tests/test_build_seoul_lp_hours_scenario.py` | 1 | Matched daily close retention and explicit assumption labels for unknown hours |
| `tests/test_import_seoul_osm_hours.py` | 2 | Road-address parsing and strict name/location/context matching for OSM hours |
| **Total** | **54** | All passed in the last full run |

To run them from the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Tests establish such properties as: allocations respect the modeled limits;
ineligible pairs get no allocation; the LP's computed optimum is valid for
constructed test cases; Stage 2 preserves Stage 1's maximum; greedy is
order-sensitive; a matched closing time is used only for the matched sender;
unknown hours are not silently promoted to observations; and historical
provision shares are normalized without inventing a quantity for the
unmatched directory entry. They do **not** prove food is edible, an NGO has
the modeled capacity, or an OSRM distance is an operational route.

## 10. Run the application and reproduce results

Python 3.10 or later is required. Install project and development dependencies
and launch the Streamlit app:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev,research]"
.\.venv\Scripts\streamlit.exe run app.py
```

The historical-throughput-weighted LP-versus-greedy experiment can be
reproduced from retained local data without new route requests:

```powershell
.\.venv\Scripts\python.exe scripts\run_seoul_historical_capacity_experiment.py
```

The main refinement grid and separate hours experiments are run with:

```powershell
.\.venv\Scripts\python.exe scripts\prepare_seoul_refinement.py
.\.venv\Scripts\python.exe scripts\run_seoul_experiments.py
.\.venv\Scripts\python.exe scripts\run_seoul_deadline_experiment.py
```

Preparing or rebuilding source data may require the optional research
dependencies and, for geocoding/routing enrichment, the relevant local
services. The checked-in route matrix is used by the experiment runners and
does not itself request new routes.

## 11. Main project files

- `app.py` — Streamlit interface for built-in scenarios and validated user
  uploads.
- `src/food_allocation/models.py` — sender, receiver, pair, instance, and
  result data structures.
- `src/food_allocation/solver.py` — Stage 1 and Stage 2 LPs.
- `src/food_allocation/baseline.py` — nearest-eligible-receiver greedy
  baseline.
- `src/food_allocation/evaluation.py` — allocation, capacity, and distance
  metrics.
- `src/food_allocation/scenario_engine.py` — Seoul scenario construction and
  capacity-share logic.
- `src/food_allocation/validation.py` — uploaded-input validation.
- `data/scenario/` — preserved original sender, receiver, and route inputs.
- `data/scenario_refined/` — refined observations, assumptions, and experiment
  outputs.
- `data/processed/` and `data/raw/` — source and curated public-data tables.
- `docs/historical_capacity_lp_vs_greedy.md` — focused historical-weighted
  comparison report.
- `model_formulation.md` — compact mathematical formulation and modeling
  notes.
- `docs/data_feasibility_audit.md` and `docs/research_limitations.md` — data
  evidence and limits.
- `docs/source_register.md` and `docs/public_database_guide.md` — provenance,
  field definitions, and source-use notes.

## 12. Bottom line

The project implements a valid allocation LP and a comparable greedy
baseline. The model maximizes kilograms first and can then minimize pairwise
kg-km without losing the kilogram optimum. On the retained Seoul scenario
grids, the LP never allocated less than greedy; it strictly allocated more
in a substantial but scenario-dependent subset and tied in the rest. That
result demonstrates the value of global optimization over a greedy heuristic
for some constrained networks—not universal strict superiority and not a
validated estimate of food rescued in Seoul.

For empirical operational conclusions, replace scenario supply with
source-supported eligible surplus, replace modeled capacities with actual
same-period additional receiving capacity, and verify donor acceptance,
food-type compatibility, location, and pickup windows. Until then, report
the outputs as **assumption-driven optimization scenarios**.
