# Seoul LP hours and NGO cutoff scenario

## Assumptions and hours evidence

This is a hypothetical scenario, not a verified operating plan. Each sender's
collection window starts at its selected closing time and lasts at most two
hours. If a location-matched Google Search/Maps closing-time record exists for
that sender and weekday, that listed time is used. **Every other sender-day is
assigned the user-requested assumed 21:00 close.** The daily inputs, including
evidence labels and the assumption text, are in
[`data/scenario_refined/seoul_lp_daily_hours_scenario.csv`](../data/scenario_refined/seoul_lp_daily_hours_scenario.csv).
The 29 Seoul tourism and six OSM hours texts remain preserved in the source
union, but are not parsed into weekday closing times by this scenario. They
therefore do not silently become verified LP inputs.

All receivers are assumed able to accept delivery up to **23:00**, as
requested. Their actual opening times and actual receiving capacity are not
known. For each sender, pairwise travel is allowed only if estimated direct
travel fits both the restaurant's close-plus-two-hour window and the remaining
time to 23:00. This cutoff can shorten the allowed interval; it does not model
receiver opening time, service time, or a multi-stop tour.

## Other scenario inputs

- 1795 sender records, seven weekdays.
- Illustrative eligible fraction alpha=10%; government quantities are
  reported expected food-waste discharge, not edible or donatable surplus.
- Hypothetical total receiver capacity ratio beta=1; no additional NGO
  receiving capacity was measured.
- Direct travel time is OSRM pairwise road distance divided by assumed average
  speed (15.0, 20.0, 25.0 km/h); it is not live ETA.

## Results

Ran 63 comparisons (weekday × speed × greedy order). LP allocated
strictly more than greedy in 0, tied in 63, and greedy allocated more
in 0. LP Stage 1 is optimal and greedy is feasible on the same
instance, so LP cannot allocate less; ties are expected and strict improvement
is data-dependent. These results belong only to this assumption-driven
scenario and do not establish that the real system will perform similarly.

Daily comparison counts: Monday=9, Tuesday=9, Wednesday=9, Thursday=9, Friday=9, Saturday=9, Sunday=9.

Detailed output:
[`data/scenario_refined/seoul_lp_hours_scenario_results.csv`](../data/scenario_refined/seoul_lp_hours_scenario_results.csv)
