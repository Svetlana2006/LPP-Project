# Seoul LP and greedy scenario comparison

This report summarizes the deterministic experiment output in `data/scenario_refined/scenario_experiment_results.csv`. Every row is a **hypothetical scenario result**, not a confirmed donation or delivery.

## Experiment coverage

- Rows: **2,160** (5 alpha values × 3 beta values × 4 capacity-share patterns × 6 geographic networks × 2 coordinate-quality modes × 3 greedy orders).
- Alpha values are illustrative (5%, 10%, 20%, 30%, 40%); beta values are 0.50, 1.00, 1.50; thresholds are 5, 10, 15, 20, 25 km plus complete network.
- Across comparison rows, LP strictly allocated more kg than greedy in **1,035**, tied within 1e-6 kg in **1,125**, and was below greedy in **0**.
- A negative difference would indicate a model or feasibility defect; zero violations are expected because Stage 1 is the LP optimum and greedy is feasible on identical inputs.
- Stage 2 minimizes pairwise kg-km subject to the Stage 1 allocation optimum. It does not minimize full vehicle-tour distance.

## Representative comparisons

The table below uses alpha=10%, beta=1.0, uniform hypothetical receiver shares, and the non-strict coordinate setting. It compares the named geographic network and fixed greedy order.

| Network | Greedy order | LP Stage 1 kg | Greedy kg | LP − greedy kg | LP Stage 2 kg-km | Greedy kg-km |
|---|---|---:|---:|---:|---:|---:|
| 5 km | fewest_eligible | 295,617.83 | 294,750.83 | 867.00 | 749,728.74 | 994,635.98 |
| 5 km | largest_supply | 295,617.83 | 289,081.47 | 6,536.36 | 749,728.74 | 897,830.87 |
| 5 km | sender_id | 295,617.83 | 288,294.33 | 7,323.50 | 749,728.74 | 850,022.72 |
| 15 km | fewest_eligible | 518,199.52 | 478,320.88 | 39,878.64 | 3,289,959.04 | 3,068,755.88 |
| 15 km | largest_supply | 518,199.52 | 460,340.99 | 57,858.53 | 3,289,959.04 | 2,746,702.34 |
| 15 km | sender_id | 518,199.52 | 453,009.98 | 65,189.54 | 3,289,959.04 | 2,893,520.50 |
| Complete network | fewest_eligible | 518,199.52 | 518,199.52 | 0.00 | 3,129,385.86 | 4,565,782.27 |
| Complete network | largest_supply | 518,199.52 | 518,199.52 | 0.00 | 3,129,385.86 | 3,817,203.75 |
| Complete network | sender_id | 518,199.52 | 518,199.52 | 0.00 | 3,129,385.86 | 4,565,782.27 |

## Strict coordinate-quality sensitivity

For alpha=10%, beta=1.0, uniform shares, complete route network, and sender-ID greedy order:

| Geographic quality setting | LP maximum kg | Greedy kg | LP − greedy kg | LP Stage 2 kg-km | Greedy kg-km |
|---|---:|---:|---:|---:|---:|
| All geocoded nodes | 518,199.52 | 518,199.52 | 0.00 | 3,129,385.86 | 4,565,782.27 |
| Strict road-and-house-number matches | 194,324.82 | 194,324.82 | 0.00 | 1,157,933.89 | 1,944,537.45 |

The strict filter changes the geographic network by excluding uncertain geocodes; it does not establish operational donation eligibility. Co-located businesses with qualifying address evidence remain represented.

## Interpretation

LP and greedy use identical supply, capacity, geographic edges, and route distances for each comparison. The LP can tie or strictly improve total allocated scenario kilograms depending on constraints and greedy order. No superiority claim is made for actual Seoul redistribution. Capacity-share patterns and distance thresholds are assumptions, not NGO capacities or verified service areas.
