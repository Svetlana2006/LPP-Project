# Limitations and current research status

The refined Seoul implementation is a reproducible **public-data-based,
assumption-driven scenario study**, not a validated food redistribution
deployment. Detailed limitations are in
[`research_limitations.md`](./research_limitations.md).

## Public observations versus scenario quantities

- The South Korean `PROD_QTY` field is expected food-waste discharge in
  kg/month. The data do not establish actual edible, unserved, safe, or
  available restaurant surplus.
- Scenario supply uses \(s_i=W_i\alpha\). Tested alpha values are illustrative,
  not measured eligible-food fractions.
- Korea Foodbank's directory gives candidate location records but not actual
  additional NGO receiving capacity, category acceptance, donor acceptance,
  receiver hours, or service areas.
- Publicly described historic receipts, provisions, user counts, inventory,
  and preferences do not establish future additional receiving capacity.
- Receiver capacity distributions and total-capacity ratios are assumptions,
  not empirical NGO capacity estimates.

## Geographic and operating limits

- The 5–25 km distance cutoffs are hypothetical `geographic_eligibility`
  scenarios, not verified service radii or permission to donate.
- A strict geocoding-quality scenario excludes non-road-and-house-number
  matches. Distinct co-located senders are retained when their locations meet
  the rule; repeated coordinates alone are not a reason to discard a business.
- Seven route pairs have 0 km outputs. The route-quality report lists their
  IDs and address-match evidence.
- Pairwise OSRM driving distance does not represent live traffic, pickup and
  receiving schedules, restaurant-specific feasibility, vehicle availability,
  or a complete multi-stop route.
- The two-hour-after-closing scenario assumption is not verified by actual
  opening hours or enforced from observed schedule data.

## Optimization and comparison limits

- Stage 1 maximizes scenario kilograms; Stage 2 minimizes pairwise kg-km while
  retaining the Stage 1 optimum. This does not minimize complete vehicle-tour
  distance, time, cost, or emissions.
- Greedy results depend on sender processing order. LP and greedy comparisons
  use the same scenario supply, capacity, geographic edges, and distances.
- The LP is guaranteed to be no worse in allocated kilograms than a feasible
  greedy result on that same instance, but strict improvement is not
  guaranteed. Ties are valid.
- Results are hypothetical planned allocations, not evidence that food was
  accepted, collected, or delivered.

## Reproducibility

The original all-waste scenario inputs remain under `data/scenario/`. A
duplicate snapshot of the earlier implementation was removed during
repository cleanup. The current refined inputs and experiment engine live
under `data/scenario_refined/` and `scripts/`.
