# Seoul scenario study: research limitations

## What the public data establish

The South Korean public food-waste dataset reports expected food-waste
discharge in kg/month. The Korea Foodbank public map lists organization/site
names, area labels, and addresses. These public observations support a
reproducible, location-aware scenario exercise; they do not establish an
operating donor-to-receiver network.

The Korea Foodbank open-data description lists historical facility/organization
and operating statistics, including receipt/provision activity, users, items,
centers, and preference/inventory information. The page notes that API access
requires application and an API key. The described historical activity or
previous-day inventory is not additional future receiving capacity. No
defensible site-specific additional capacity quantity was extracted from the
public directory/open-data descriptions.

The public 2025 Seoul operating-statistics tables provide receipt and provision
activity for 31 of the 32 listed Seoul directory entries; the national-level
`전국푸드뱅크` entry has no separate Seoul row. Their reported `수량` (quantity)
unit is not stated, and historical activity does not measure spare pickup
capacity. The corresponding records are retained in
`data/processed/korea_foodbank_seoul_operations_2025.csv`; missing sites remain
unknown, not zero. Mapo Itta Food Bank's March 2025 receipt-ledger attachment
was inspected: it documents dated donations and product quantities, but most
quantities are not weights and the ledger does not establish additional
capacity.

## Unobserved operational quantities

The available Seoul data do not establish:

- Actual edible, unserved restaurant surplus.
- Actual additional NGO receiving capacity for a shared planning period.
- Verified restaurant-to-NGO donation acceptance.
- Actual food-category compatibility or food-safety acceptance.
- Actual operational pickup and receiving times or restaurant closing times.
- Verified receiver service areas or donor-specific acceptance policies.
- Restaurant-specific pickup feasibility.
- Live traffic conditions or actual travel times.
- Multi-stop vehicle routing, vehicle availability, or complete tour distance.

## Scenario assumptions

The model uses \(\alpha\) to turn reported expected waste \(W_i\) into scenario
supply \(s_i=W_i\alpha\). Tested values are 5%, 10%, 20%, 30%, and 40%; they are
illustrative, not measured eligible-food fractions.

Receiver capacity is modeled as
\(C_j=\beta(\sum_i s_i)q_j\). The tested beta values and uniform, linear-rank,
quadratic-rank, and 75%-concentrated share rules are hypothetical distributions,
not NGO capacity evidence.

Road-distance thresholds create `geographic_eligibility` scenarios only. The
5–25 km thresholds do not verify service radii or donation acceptance. A strict
geographic-quality filter excludes non-road-and-house-number geocodes but
retains distinct co-located businesses that meet the rule.

## Mathematical and evaluation limits

The first LP maximizes scenario kilograms; the second minimizes total pairwise
kg-km while fixing the first-stage maximum. Pairwise kg-km is not complete
vehicle-tour distance, travel time, cost, or emissions.

The nearest-receiver greedy baseline is order-sensitive. Results must be
compared on identical supplies, receiver capacities, geographic edges, and
distances. The LP is guaranteed to be no worse in allocated kilograms than a
feasible greedy result on that same instance, but it may tie; strict improvement
is data-dependent. The bottleneck example is a constructed illustration, not
evidence about Seoul organizations.

The separate pickup-window experiment assigns hypothetical close times to
restaurants and applies each restaurant's own close+2-hour deadline using
direct NGO-to-restaurant estimated duration. It tests hypothetical collection
starts at 20:00, 21:00, and 22:00 and estimates duration from OSRM distance
divided by an assumed 15/20/25 km/h. The assigned closing times and speeds are
not measured Seoul data or Google Maps estimates. This pairwise approximation does not enforce
cumulative NGO→restaurant→restaurant travel. The reported comparison is
therefore evidence about the stated pairwise scenario only, not about complete
multi-stop collection feasibility.

## Reporting statement

Present this work as a **public-data-based, assumption-driven optimization
scenario study**, not a validated real-world food redistribution deployment.
The model outputs are planned hypothetical allocations only. They are not
confirmed food donations, pickups, or deliveries.
