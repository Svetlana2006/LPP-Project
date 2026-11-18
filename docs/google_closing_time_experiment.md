# Google closing-time subset experiment

## What this represents

Google Search/Maps closing-time observations were used only where the result matched
the restaurant's listed name/location. For each restaurant, the collection window
starts at its own closing time and ends two hours later (midnight rollovers included).
The restaurant hours file is
[`data/scenario_refined/google_restaurant_closing_times.csv`](../data/scenario_refined/google_restaurant_closing_times.csv).

Hours coverage by day in the current lookup subset:

- Monday: 6 matched sender records
- Tuesday: 6 matched sender records
- Wednesday: 7 matched sender records
- Thursday: 6 matched sender records
- Friday: 6 matched sender records
- Saturday: 6 matched sender records
- Sunday: 6 matched sender records

The Seoul source contains 1795 sender records; only the
small subset with matched hours is evaluated on each day. (Hours are not available for
most restaurants.) Reported monthly food-waste quantities are not edible-food estimates.
The experiment uses illustrative alpha=10% and beta=1; neither is measured
operational data.

## Travel-time proxy and model scope

Direct travel time is approximated as existing OSRM road distance divided by an assumed
average speed (15.0, 20.0, 25.0 km/h sensitivity). This is not a
Google Maps ETA. Each NGO-to-restaurant pair is checked independently; cumulative
restaurant-to-restaurant travel, multi-stop ordering, loading time, actual traffic, and
confirmed pickup arrangements are not modeled.

The LP and greedy methods receive the same supply, scaled receiver capacities, distances,
and window-feasible edges. Ties are valid; no strict LP advantage is guaranteed.

Across these 63 partial-data comparisons, LP allocated more in 7,
they tied in 56, and greedy allocated more in 0. These counts apply
only to the stated hours subset and scenario settings.

## Comparison output

See [`data/scenario_refined/google_closing_time_experiment_results.csv`](../data/scenario_refined/google_closing_time_experiment_results.csv)
for each weekday, assumed speed, and greedy order. These are partial, assumption-driven
scenario results, not validated delivery outcomes.
