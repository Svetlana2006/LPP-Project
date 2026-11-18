# Historical-throughput-weighted Seoul LP scenario

## Result

The LP and nearest-receiver greedy baseline were compared on the same scenario
inputs: 1,795 Seoul restaurant nodes, 32 listed receiver nodes, a 10% fraction
of reported expected food waste treated as scenario supply, total hypothetical
receiver capacity equal to that supply, and OSRM distance-threshold eligibility.
The tests cover 5, 10, 15, 20, and 25 km thresholds plus a complete-network
benchmark, with three deterministic greedy sender orders per network.

- LP allocated at least as much as greedy in **18/18** comparisons.
- LP allocated strictly more in **13/18** comparisons and tied in **5/18**.
- At **15 km**, LP allocated **518,199.52 kg**. Greedy allocated between
  **444,430.51 kg** and **468,715.82 kg**, depending on sender order; LP's
  advantage was **49,483.70–73,769.01 kg**.
- At 20 km, LP allocated all scenario supply; greedy tied in one of three
  sender orders. At 25 km, it tied in one of three. In the complete network,
  LP and greedy tied in all three orders because total capacity equals total
  supply and no geographic edges are removed.

The test demonstrates that LP can outperform this particular greedy baseline
on the stated scenarios; it does not mean LP always strictly wins. The
objective is first to maximize allocated kilograms, then to minimize pairwise
kg-km at that maximum. At 15 km, LP's kg-km was higher than greedy's raw kg-km
because LP delivered more food; those totals are not a like-for-like distance
comparison. This study does not establish lower travel cost, time, emissions,
or vehicle-tour distance.

## How historical data is used

The 2025 Foodbank provision quantities are used only to compute relative shares
among the 31 exact-name-matched sites. Their unit is unstated, so they are not
converted to kilograms. The separate nationwide-level directory entry has no
Seoul row and receives zero modeled share rather than an invented value.
Normalized shares distribute the assumed total capacity in kilograms; that
total is itself hypothetical and is set equal to scenario supply. Thus the
resulting site capacities are **historical-throughput-weighted scenario
values**, not observed NGO capacity or spare capacity.

Sender supply is 10% of the government dataset's expected food-waste discharge.
This is an illustrative scenario fraction: the government data do not show
which material is edible, unserved, or donatable. Distance thresholds are also
assumed geographic eligibility, not verified food acceptance, service radius,
or pickup feasibility.

## Reproduction and outputs

From the repository root, run:

```powershell
.\.venv\Scripts\python.exe scripts\run_seoul_historical_capacity_experiment.py
```

The script writes:

- `data/scenario_refined/historical_provision_weighted_capacities.csv` —
  per-site historical quantity, normalized share, and scenario capacity.
- `data/scenario_refined/historical_provision_weighted_lp_greedy_results.csv` —
  18 LP/greedy comparisons.
- `data/scenario_refined/historical_provision_weighted_15km_allocations.csv` —
  detailed LP and greedy allocations for the 15 km case.

All model outputs are hypothetical, not confirmed donations or deliveries.
