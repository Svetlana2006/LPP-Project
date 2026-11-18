# Seoul route-quality audit

Route and coordinate results are estimates for scenario analysis, not verified
addresses, donation eligibility, or dispatch routes. The original matrix is
preserved in `data/scenario/eligibility_matrix.csv`.

## Address-match quality

- Unique geocoded address queries: **1,735**.
- Road-and-house-number matches: **1,216**.
- Non-road-and-house-number matches: **519** (partial=301, approximate Seoul=210, street-only=8).
- Scenario node rows (including repeated addresses): **1,827**; 538 have non-exact match labels.
- Node-level match counts: {'approximate_Seoul_match': 220, 'partial_address_match_in_Seoul': 310, 'road_and_house_number_match_in_Seoul': 1289, 'street_only_approximation': 8}.
- Missing geocoding metadata counts: latitude=0, longitude=0, osm_type=0, osm_id=0, match_quality=0.
- Missing routed coordinate rows: geocoded=0, snapped=0.

## Routes and shared coordinates

- Zero-distance sender/receiver pairs: **7**; see `data/scenario_refined/zero_distance_pairs.csv` for IDs.
- Maximum OSRM snap offset: **119.386 m**.
- Repeated geocoded coordinate groups: **258** (672 node rows); groups with multiple senders: **257**; groups with multiple receivers: **0**; sender/receiver shared-coordinate groups: **2**.
- Repeated snapped-coordinate groups: **259** (674 node rows).
- Shared coordinates are not automatically discarded: distinct businesses can share a building, mall, or geocoder point. The strict quality scenario excludes non-road-and-house-number geocodes but retains co-located nodes that meet that rule.

## Strict geographic-quality scenario

The strict scenario retains a sender/receiver only when the Photon match is `road_and_house_number_match_in_Seoul` and OSRM snap metadata exists. An edge must also satisfy the selected road-distance threshold (or be in the complete network benchmark). This is a conservative coordinate-quality filter, not operational donation eligibility. Food-category acceptance, donor acceptance, receiving hours, actual service areas, restaurant-specific pickup feasibility, and traffic remain unverified.

OSRM uses pairwise driving-profile distances. They are not traffic-aware travel times and do not minimize complete vehicle-tour distance.
