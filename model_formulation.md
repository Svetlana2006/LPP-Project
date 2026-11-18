# Seoul food-allocation scenario: mathematical formulation

## Interpretation and scope

This is a continuous, two-stage linear program for a public-data-based
hypothetical Seoul scenario. It does not estimate verified donations or
operational delivery performance. The source quantity is expected food-waste
discharge, not observed edible surplus; actual eligible food and receiver
capacity have not been observed.

The original pure LP is preserved as Stage 1. Stage 2 is a second LP that
minimizes pairwise kilogram-kilometres while preserving Stage 1's maximum
allocated kilograms. No integer variables are used, so allocations may be
split across receivers.

## Sets and parameters

- \(I\): restaurant sender records, \(i \in I\).
- \(J\): listed Seoul food-bank receiver sites, \(j \in J\).
- \(W_i \ge 0\): reported expected food-waste discharge for sender \(i\), in
  kg/month. This is a public-source field, not measured edible or donatable
  surplus.
- \(\alpha \in [0,1]\): illustrative eligible-fraction scenario parameter.
  Tested values are \(0.05, 0.10, 0.20, 0.30, 0.40\). None is an empirically
  estimated Seoul redistributable fraction.
- \(s_i = \alpha W_i\): scenario supply for sender \(i\), kg/month.
- \(\beta \ge 0\): assumed total-receiver-capacity / total-scenario-supply ratio.
  Tested values are \(0.50, 1.00, 1.50\).
- \(q_j \ge 0\): assumed share of total receiver capacity assigned to receiver
  \(j\), with \(\sum_{j\in J}q_j=1\).
- \(S=\sum_{i\in I}s_i\): total scenario supply.
- \(c_j=\beta S q_j\): scenario capacity of receiver \(j\), kg/month.
- \(d_{ij}\ge0\): OSRM OpenStreetMap driving-profile point-to-point distance
  from sender \(i\) to receiver \(j\), km. This is not traffic-aware travel
  time or a complete vehicle-tour distance.
- \(\tau\): selected hypothetical maximum-road-distance threshold, one of
  5, 10, 15, 20, or 25 km; or the separate complete-network benchmark.
- \(g_i\): 1 if sender \(i\)'s geocoding meets the strict address-quality rule,
  else 0. The rule requires a road-and-house-number Photon match and OSRM snap
  metadata.
- \(h_j\): equivalent strict geocoding-quality indicator for receiver \(j\).

Capacity-share scenarios are all assumptions, not NGO capacity observations:

- **Uniform:** equal \(q_j\).
- **Linear rank:** \(q_j\) proportional to the site's alphabetical receiver-ID
  rank.
- **Quadratic rank:** \(q_j\) proportional to rank squared.
- **75%-concentrated:** 75% of total capacity assigned to the first
  alphabetical receiver ID and 25% divided equally among the remainder.

## Geographic eligibility scenario

The geographic network indicator is:

\[
e_{ij}^{\text{geo}}(\tau)=
\begin{cases}
1, & \text{if the complete-network benchmark is selected, or } d_{ij}\le\tau,\\
0, & \text{otherwise.}
\end{cases}
\]

For the strict coordinate-quality sensitivity:

\[
e_{ij}^{\text{strict}}(\tau)=e_{ij}^{\text{geo}}(\tau)g_i h_j.
\]

This is named **geographic eligibility** deliberately. A distance threshold
does not verify food-category acceptance, donor acceptance, receiving hours,
actual service areas, food safety, or restaurant-specific pickup feasibility.
The threshold values are hypothetical maximum-road-distance scenarios, not
verified service radii. Co-located records are retained when they pass the
quality rule; repeated coordinates alone do not eliminate businesses.

## Restaurant-specific pickup window and NGO latest-arrival scenario

The LP-ready daily schedule is stored in
`data/scenario_refined/seoul_lp_daily_hours_scenario.csv` (1,795 senders ×
7 weekdays). A location-matched Google Search/Maps closing-time record is
used for that sender and weekday when available. Every other sender-day uses
the user's explicit hypothetical 21:00 restaurant close. In this schedule,
43 sender-days are lookup records and 12,522 are assumptions. Seoul tourism
and OSM hours prose remains preserved in the source-union data but is not
silently parsed into weekday closing times for this run.

For sender \(i\) on a modeled day, let \(c_i\) be that day's selected close.
The collection deadline is \(c_i+2\) hours. NGO delivery is assumed to be
accepted through 23:00. The effective latest arrival is the earlier of that
collection deadline and 23:00; if 23:00 has already passed at \(c_i\), the
effective window is zero. This uses the user's 23:00 cutoff assumption without
inventing an NGO opening time or measured receiving capacity.

For scenario average speed \(v\in\{15,20,25\}\) km/h, estimated direct travel
time is:

\[
t_{ij}=\frac{d_{ij}}{v}.
\]

The window-feasible pair indicator is:

\[
a_{ij}=
\begin{cases}
1,&t_{ij}\le \max(0,\min(c_i+2\text{ hours},23{:}00)-c_i),\\
0,&\text{otherwise.}
\end{cases}
\qquad
e_{ij}^{\text{deadline}}=e_{ij}^{\text{geo}}a_{ij}.
\]

The run uses \(\alpha=0.10\), uniform receiver shares, and \(\beta=1\).
Both LP and greedy are run on the same resulting edge set. Sender closes,
the 23:00 NGO cutoff, receiver capacity, eligible-food fraction, and average
speed are scenario inputs rather than observed operating conditions. Speed is
not a Google Maps duration. This simple pairwise restriction does not
represent a sequence such as NGO→A→C→B, travel between restaurants, service
time, or route accumulation. Exact stop-order and cumulative-window behavior
is outside this pure continuous LP.

## Decision variable

\[
x_{ij}\ge0
\]

is kilograms of scenario supply allocated from sender \(i\) to receiver \(j\)
during the modeled month.

## Stage 1: maximize allocated kilograms

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
\sum_{i\in I}x_{ij}\le c_j
\qquad \forall j\in J
\]

Subject to the pair bound:

\[
0\le x_{ij}\le
\min(s_i,c_j)e_{ij}^{\text{geo}}
\qquad \forall i\in I,\ j\in J
\]

For strict geographic quality, replace \(e_{ij}^{\text{geo}}\) with
\(e_{ij}^{\text{strict}}\). The \(\min(s_i,c_j)e_{ij}\) term is a constant
upper bound for a particular scenario, so the model remains linear.

Let \(Z^\star\) denote the Stage 1 optimal value.

## Stage 2: minimize total allocated kg-km

Using the same supply, capacity, and pair bounds as Stage 1, solve:

\[
\boxed{
\min \sum_{i\in I}\sum_{j\in J}d_{ij}x_{ij}
}
\]

with the additional optimal-quantity constraint:

\[
\sum_{i\in I}\sum_{j\in J}x_{ij}=Z^\star.
\]

The Stage 2 objective has units of kg-km. Its average pairwise distance per
allocated kilogram is:

\[
\frac{\sum_{i\in I}\sum_{j\in J}d_{ij}x_{ij}}{Z^\star}
\quad\text{km per allocated kg},\qquad Z^\star>0.
\]

The implementation fixes Stage 1's solver value as the equality target and
uses HiGHS primal/dual feasibility tolerances of \(10^{-8}\). This is
lexicographic optimization: Stage 1 maximizes kilograms first; Stage 2 improves
the distance-weighted allocation without sacrificing that maximum. It does not
minimize complete vehicle-tour distance, vehicle count, time, cost, or emissions.

## Greedy comparison

The nearest-eligible-receiver greedy baseline is run with exactly the same
scenario supplies, capacities, geographic edges, and pairwise distances. Its
sender orders include sender ID, fewest eligible receivers, largest supply,
and reverse sender ID. In the separate pickup-window experiment, the same
three primary orders are used after applying the hypothetical pairwise
restaurant deadlines.

When Stage 1 is optimal and greedy is feasible on the same instance, LP Stage 1
is guaranteed to allocate at least as many kilograms as greedy. A tie is valid;
strict improvement is not guaranteed. Stage 2 distance results are compared
separately, and greedy is not claimed to minimize distance.
