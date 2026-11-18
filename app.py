"""Streamlit interface for uploading, validating, and comparing allocation inputs."""

from dataclasses import replace

import pandas as pd
import streamlit as st
from pathlib import Path

from food_allocation.baseline import greedy_allocate
from food_allocation.deadline_scenario import (
    apply_pairwise_pickup_windows,
    collection_window_labels,
    load_google_closing_times,
)
from food_allocation.evaluation import calculate_metrics
from food_allocation.scenario_engine import (
    CAPACITY_DISTRIBUTIONS,
    ScenarioParameters,
    build_seoul_instance,
)
from food_allocation.solver import solve_lp, solve_two_stage_lp
from food_allocation.validation import DataValidationError, load_instance


ROOT = Path(__file__).resolve().parent

st.set_page_config(page_title="Food Allocation Optimisation", layout="wide")
st.title("Food Allocation Optimisation")
st.write(
    "Maximize kilograms allocated from eligible, safe, edible, unserved surplus "
    "to receiving sites with confirmed additional capacity."
)
st.warning(
    "Food-waste totals are not donatable-food quantities. Upload only source-supported "
    "eligible surplus and additional receiving capacity. This tool reports planned "
    "allocations, not confirmed deliveries."
)

st.header("Built-in Seoul scenario refinement")
st.markdown(
    "This public-data-based experiment keeps **reported expected food waste** separate "
    "from assumed eligible supply. The eligible food quantities and actual NGO capacities "
    "have not been observed. Every result below is a hypothetical scenario, not a confirmed "
    "food donation or delivery."
)
control_columns = st.columns(5)
alpha = control_columns[0].select_slider(
    "Illustrative eligible fraction α",
    options=(0.05, 0.10, 0.20, 0.30, 0.40),
    value=0.10,
    format_func=lambda value: f"{value:.0%}",
)
beta = control_columns[1].selectbox(
    "Total capacity ratio β",
    options=(0.50, 1.00, 1.50),
    index=1,
    format_func=lambda value: f"{value:g}× supply",
)
capacity_distribution = control_columns[2].selectbox(
    "Scenario receiver-capacity shares",
    options=CAPACITY_DISTRIBUTIONS,
    format_func=lambda value: value.replace("_", " "),
)
distance_label = control_columns[3].selectbox(
    "Geographic distance scenario",
    options=("Complete network", "5 km", "10 km", "15 km", "20 km", "25 km"),
)
strict_quality = control_columns[4].checkbox(
    "Strict address-quality filter",
    value=False,
    help=(
        "Retains only road-and-house-number geocodes with OSRM snap metadata. "
        "This is not operational donation eligibility."
    ),
)
distance_threshold = (
    None
    if distance_label == "Complete network"
    else float(distance_label.removesuffix(" km"))
)
greedy_order_labels = {
    "Sender ID order": "sender_id",
    "Fewest eligible receivers first": "fewest_eligible",
    "Largest supply first": "largest_supply",
}
selected_order_labels = st.multiselect(
    "Greedy sender-processing orders to compare",
    options=list(greedy_order_labels),
    default=list(greedy_order_labels),
)

if st.button("Run selected Seoul scenario", type="primary"):
    try:
        selected_instance = build_seoul_instance(
            ScenarioParameters(
                eligible_fraction_alpha=alpha,
                total_capacity_ratio_beta=beta,
                capacity_distribution=capacity_distribution,
                maximum_road_distance_km=distance_threshold,
                strict_geographic_quality=strict_quality,
            ),
            data_directory=ROOT / "data" / "scenario_refined",
        )
        two_stage = solve_two_stage_lp(selected_instance)
        sender_waste_rows = pd.read_csv(
            ROOT / "data" / "scenario_refined" / "sender_observations.csv"
        )
        original_total = sender_waste_rows[
            "reported_expected_waste_kg_month"
        ].sum()
        scenario_supply = sum(sender.supply_kg for sender in selected_instance.senders)
        supply_columns = st.columns(2)
        supply_columns[0].metric(
            "Reported expected waste (source records)",
            f"{original_total:,.2f} kg/month",
        )
        supply_columns[1].metric(
            f"Scenario supply at α={alpha:.0%}",
            f"{scenario_supply:,.2f} kg/month",
        )
        st.caption(
            "The first value is a public-source reported expected waste quantity; "
            "the second is an assumption-derived scenario input, not measured edible surplus."
        )
        st.bar_chart(
            pd.DataFrame(
                {
                    "Quantity kg/month": [original_total, scenario_supply],
                },
                index=[
                    "Reported expected waste — public observation",
                    "Scenario eligible supply — assumption-derived",
                ],
            )
        )

        st.subheader("Lexicographic LP results")
        result_columns = st.columns(3)
        result_columns[0].metric(
            "Stage 1: maximum allocation",
            f"{two_stage.stage1_optimal_kg:,.2f} kg",
        )
        result_columns[1].metric(
            "Stage 2: total allocated kg-km",
            f"{two_stage.stage2_total_kg_km:,.2f}",
        )
        result_columns[2].metric(
            "Average distance per allocated kg",
            (
                "Not defined"
                if two_stage.stage2_average_km_per_kg is None
                else f"{two_stage.stage2_average_km_per_kg:.3f} km/kg"
            ),
        )
        st.caption(
            "Stage 2 minimizes pairwise distance-weighted allocated quantity only after "
            "fixing the Stage 1 maximum. kg-km is not complete vehicle-tour distance."
        )

        comparison_rows = []
        greedy_results = {}
        for label in selected_order_labels:
            order = greedy_order_labels[label]
            greedy = greedy_allocate(selected_instance, order)
            greedy_results[order] = greedy
            metrics = calculate_metrics(selected_instance, greedy)
            difference = two_stage.stage1_optimal_kg - greedy.objective_kg
            comparison_rows.append(
                {
                    "Greedy order": label,
                    "LP max kg": two_stage.stage1_optimal_kg,
                    "Greedy allocated kg": greedy.objective_kg,
                    "LP minus greedy kg": difference,
                    "LP Stage 2 kg-km": two_stage.stage2_total_kg_km,
                    "Greedy kg-km": metrics["allocated_distance_kg_km"],
                    "Greedy unallocated supply kg": metrics["unallocated_surplus_kg"],
                    "Remaining receiver capacity kg": metrics[
                        "remaining_receiver_capacity_kg"
                    ],
                }
            )
        if comparison_rows:
            st.subheader("Greedy-order comparison")
            st.dataframe(
                pd.DataFrame(comparison_rows),
                use_container_width=True,
                hide_index=True,
            )
            st.info(
                "A tie is a valid result. The LP is guaranteed to be no worse in allocated "
                "kilograms only when it is optimal and the greedy allocation is feasible "
                "under these same inputs; strict improvement is not guaranteed."
            )

        experiments_path = (
            ROOT / "data" / "scenario_refined" / "scenario_experiment_results.csv"
        )
        if experiments_path.exists():
            experiments = pd.read_csv(experiments_path)
            experiment_threshold = (
                pd.isna(experiments["maximum_road_distance_km"])
                if distance_threshold is None
                else experiments["maximum_road_distance_km"] == distance_threshold
            )
            selected_experiments = experiments[
                (experiments["eligible_fraction_alpha"] == alpha)
                & (experiments["total_capacity_ratio_beta"] == beta)
                & (experiments["capacity_distribution"] == capacity_distribution)
                & experiment_threshold
                & (
                    experiments["strict_geographic_quality"]
                    == strict_quality
                )
            ]
            st.subheader("Saved experiment rows for these parameters")
            st.dataframe(selected_experiments, use_container_width=True, hide_index=True)
            st.subheader("Parameter-grid comparison at the selected α")
            comparison_grid = experiments[
                (experiments["eligible_fraction_alpha"] == alpha)
                & experiments["sender_processing_order"].isin(
                    [greedy_order_labels[label] for label in selected_order_labels]
                )
            ]
            st.dataframe(
                comparison_grid[
                    [
                        "scenario_id",
                        "total_capacity_ratio_beta",
                        "capacity_distribution",
                        "maximum_road_distance_km",
                        "strict_geographic_quality",
                        "sender_processing_order",
                        "lp_stage1_optimal_kg",
                        "greedy_allocated_kg",
                        "lp_minus_greedy_kg",
                        "lp_stage2_total_kg_km",
                        "greedy_total_kg_km",
                        "greedy_unallocated_supply_kg",
                        "greedy_remaining_receiver_capacity_kg",
                    ]
                ],
                use_container_width=True,
                hide_index=True,
            )

        allocated_senders = {
            sender_id
            for sender_id, _ in two_stage.stage2.allocations_kg
        }
        allocated_receivers = {
            receiver_id
            for _, receiver_id in two_stage.stage2.allocations_kg
        }
        map_rows = [
            {
                "latitude": node.latitude,
                "longitude": node.longitude,
                "type": node_type,
                "color": "#1f77b4" if node_type == "Sender" else "#ff7f0e",
                "node_id": node.sender_id if node_type == "Sender" else node.receiver_id,
            }
            for node_type, nodes, allocated_ids, id_field in (
                (
                    "Sender",
                    selected_instance.senders,
                    allocated_senders,
                    "sender_id",
                ),
                (
                    "Receiver",
                    selected_instance.receivers,
                    allocated_receivers,
                    "receiver_id",
                ),
            )
            for node in nodes
            if getattr(node, id_field) in allocated_ids
            and node.latitude is not None
            and node.longitude is not None
        ]
        st.subheader("Scenario allocation locations")
        st.caption(
            "Map shows locations of nodes with a planned LP allocation in this scenario; "
            "it does not display confirmed deliveries or vehicle routes."
        )
        if map_rows:
            st.map(pd.DataFrame(map_rows), color="color")
        else:
            st.info("No nodes received a positive allocation in this scenario.")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "sender_id": sender_id,
                        "receiver_id": receiver_id,
                        "planned_scenario_allocation_kg": amount,
                    }
                    for (sender_id, receiver_id), amount in sorted(
                        two_stage.stage2.allocations_kg.items()
                    )
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )
    except (OSError, KeyError, ValueError, RuntimeError) as exc:
        st.error(f"Could not run the selected Seoul scenario: {exc}")

with st.expander("Seoul scenario assumptions and data provenance"):
    st.markdown(
        """
        - `reported_expected_waste_kg_month` is the government's expected waste
          discharge field, defined in kg/month. Actual edible and unserved food
          quantities have not been observed.
        - Scenario supply is `s_i = W_i * alpha`; tested alpha values (5%, 10%,
          20%, 30%, 40%) are illustrative assumptions, not estimated Seoul rates.
        - Receiver capacity is `C_j = beta * total_scenario_supply * q_j`, with
          normalized nonnegative `q_j`. Uniform, linear-rank, quadratic-rank,
          and 75%-concentrated shares are hypothetical distributions, not NGO
          capacity measurements.
        - Distance thresholds create `geographic_eligibility` scenarios only.
          The complete network is retained as a benchmark. Distance does not
          prove food-category acceptance, donor acceptance, receiving hours,
          actual service areas, or restaurant-specific pickup feasibility.
        - Strict coordinate quality requires a road-and-house-number Photon
          match and OSRM snap metadata. Distinct co-located businesses are not
          removed just because coordinates repeat.
        - The model uses pairwise OSRM driving distances. It does not model
          live traffic or complete multi-stop vehicle tours.
        - Korea Foodbank's published open-data page describes historic receipt,
          provision, inventory/preference, center, facility, and user datasets.
          Those values do not establish additional future receiving capacity;
          no defensible site-specific capacity quantity was found in the public
          directory/open-data descriptions.
        """
    )

st.header("Restaurant-specific 2-hour collection-window scenario")
st.markdown(
    "This comparison uses only restaurant/day records with a strict name-and-address "
    "match in the Google lookup. These lookup results have not been independently "
    "confirmed as current restaurant hours. No closing time is imputed for unmatched "
    "restaurants. Each matched record's listed closing time starts its own two-hour window."
)
hours_data_path = (
    ROOT / "data" / "scenario_refined" / "google_restaurant_closing_times.csv"
)
hours_rows = pd.read_csv(hours_data_path)
matched_hours_sender_count = hours_rows.loc[
    hours_rows["match_status"] == "matched_name_address", "sender_id"
].nunique()
st.caption(
    f"Matched-hour coverage: {matched_hours_sender_count:,} of "
    "1,795 senders in the lookup file (checked 2026-11-11). This is not a verified "
    "all-restaurant hours dataset; unmatched senders are excluded, not assigned assumed hours."
)
deadline_controls = st.columns(4)
assumed_speed = deadline_controls[0].selectbox(
    "Assumed average driving speed (time proxy)",
    options=(15.0, 20.0, 25.0),
    index=1,
    format_func=lambda value: f"{value:g} km/h",
)
collection_day = deadline_controls[1].selectbox(
    "Restaurant operating day",
    options=(
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ),
    index=2,
)
deadline_controls[2].markdown("**Window:** each recorded close → close + 2h.")
deadline_controls[3].markdown("**Hours source:** strict name-and-address Google match.")
if st.button("Compare LP and greedy with pickup windows"):
    try:
        deadline_base = build_seoul_instance(
            ScenarioParameters(
                eligible_fraction_alpha=alpha,
                total_capacity_ratio_beta=beta,
                capacity_distribution=capacity_distribution,
                maximum_road_distance_km=distance_threshold,
                strict_geographic_quality=strict_quality,
            ),
            data_directory=ROOT / "data" / "scenario_refined",
        )
        closing_hours, hours_provenance = load_google_closing_times(
            hours_data_path, collection_day
        )
        source_sender_ids = {sender.sender_id for sender in deadline_base.senders}
        closing_hours = {
            sender_id: close_time
            for sender_id, close_time in closing_hours.items()
            if sender_id in source_sender_ids
        }
        if not closing_hours:
            st.info(
                f"No location-matched closing times are recorded for {collection_day}."
            )
        else:
            covered_ids = set(closing_hours)
            covered_senders = tuple(
                sender
                for sender in deadline_base.senders
                if sender.sender_id in covered_ids
            )
            covered_supply = sum(sender.supply_kg for sender in covered_senders)
            full_supply = sum(sender.supply_kg for sender in deadline_base.senders)
            capacity_scale = covered_supply / full_supply if full_supply else 0.0
            deadline_base = replace(
                deadline_base,
                senders=covered_senders,
                receivers=tuple(
                    replace(receiver, capacity_kg=receiver.capacity_kg * capacity_scale)
                    for receiver in deadline_base.receivers
                ),
                pairs=tuple(
                    pair
                    for pair in deadline_base.pairs
                    if pair.sender_id in covered_ids
                ),
            )
            deadline_instance = apply_pairwise_pickup_windows(
                deadline_base,
                closing_hours,
                average_speed_kmh=assumed_speed,
            )
            deadline_lp = solve_two_stage_lp(deadline_instance)
            deadline_comparisons = []
            for label, order in greedy_order_labels.items():
                greedy = greedy_allocate(deadline_instance, order)
                metrics = calculate_metrics(deadline_instance, greedy)
                deadline_comparisons.append(
                    {
                        "Greedy strategy": label,
                        "LP maximum kg": deadline_lp.stage1_optimal_kg,
                        "Greedy allocated kg": greedy.objective_kg,
                        "LP minus greedy kg": (
                            deadline_lp.stage1_optimal_kg - greedy.objective_kg
                        ),
                        "LP Stage 2 kg-km": deadline_lp.stage2_total_kg_km,
                        "Greedy kg-km": metrics["allocated_distance_kg_km"],
                        "Greedy unallocated kg": metrics["unallocated_surplus_kg"],
                    }
                )
            st.dataframe(
                pd.DataFrame(deadline_comparisons),
                use_container_width=True,
                hide_index=True,
            )
            st.caption(
                "The LP maximum is at least as large as any feasible greedy "
                "allocation under these identical constraints when the LP reaches "
                "its optimum. A strict improvement is not guaranteed; the reported "
                "gap is specific to this scenario."
            )
            st.subheader(f"Hours and collection windows — {collection_day}")
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "sender_id": sender_id,
                            "closing_time": close_time.strftime("%H:%M"),
                            "window_opens": collection_window_labels(close_time)[0],
                            "pickup_deadline": collection_window_labels(close_time)[1],
                            "hours source": hours_provenance[sender_id][
                                "source_platform"
                            ],
                            "match status": hours_provenance[sender_id][
                                "match_status"
                            ],
                            "checked date": hours_provenance[sender_id][
                                "checked_date"
                            ],
                        }
                        for sender_id, close_time in sorted(closing_hours.items())
                    ]
                ),
                use_container_width=True,
                hide_index=True,
            )
            st.caption(
                f"Run covers only {len(closing_hours):,} / "
                f"{len(source_sender_ids):,} senders with location-matched "
                "Google lookup records; receiver capacities are scaled to the subset. "
                "This is not a complete 1,795-restaurant comparison."
            )
            st.warning(
                "Travel-time check is a zero-cost proxy: existing OSRM road distance "
                "divided by the selected assumed average speed, not Google Maps live or "
                "historical ETA. Each edge is checked independently within that sender's "
                "close-to-close+2h window. The LP does not schedule multiple pickups, "
                "cumulative stop-to-stop travel, loading time, or traffic; results are "
                "scenario allocations, not confirmed collections."
            )
    except (OSError, KeyError, ValueError, RuntimeError) as exc:
        st.error(f"Could not run the pickup-window scenario: {exc}")

senders_file = st.file_uploader("Upload senders.csv", type="csv", key="senders")
receivers_file = st.file_uploader("Upload receivers.csv", type="csv", key="receivers")
pairs_file = st.file_uploader(
    "Upload eligibility_matrix.csv", type="csv", key="eligibility"
)

st.subheader("Model and comparison")
order_label = st.selectbox(
    "Greedy sender processing order",
    (
        "Fixed sender ID order",
        "Reverse sender ID order",
        "Fewest eligible receivers first",
        "Largest supply first",
        "Pickup deadline first (requires data)",
    ),
)
order_by_label = {
    "Fixed sender ID order": "sender_id",
    "Reverse sender ID order": "reverse_sender_id",
    "Fewest eligible receivers first": "fewest_eligible",
    "Largest supply first": "largest_supply",
    "Pickup deadline first (requires data)": "pickup_deadline",
}

if senders_file and receivers_file and pairs_file:
    try:
        instance = load_instance(
            senders_file.getvalue(),
            receivers_file.getvalue(),
            pairs_file.getvalue(),
        )
    except DataValidationError as exc:
        st.error(f"Input validation failed: {exc}")
    else:
        st.success(
            f"Validated {len(instance.senders)} sender(s), "
            f"{len(instance.receivers)} receiver(s), and "
            f"{len(instance.pairs)} explicit sender-receiver pair(s)."
        )
        st.caption(
            f"Collection period: {instance.senders[0].period_start} to "
            f"{instance.senders[0].period_end}. Units: kg."
        )
        input_evidence = {
            node.evidence_type for node in (*instance.senders, *instance.receivers)
        }
        if input_evidence - {"OBSERVED", "DERIVED"}:
            st.warning(
                "At least one supply or capacity is classified as PROXY or SCENARIO. "
                "The results are not an empirical performance claim."
            )
        else:
            st.info(
                "Input evidence is marked OBSERVED/DERIVED by the uploader. "
                "This application records the declarations but cannot independently verify the sources."
            )
        try:
            eligible_pairs_missing_distance = sum(
                pair.eligible and pair.road_distance_km is None
                for pair in instance.pairs
            )
            two_stage = (
                None
                if eligible_pairs_missing_distance
                else solve_two_stage_lp(instance)
            )
            stage1 = two_stage.stage1 if two_stage is not None else solve_lp(instance)
            optimum = two_stage.stage2 if two_stage is not None else stage1
            greedy = (
                None
                if eligible_pairs_missing_distance
                else greedy_allocate(instance, order_by_label[order_label])
            )
        except (RuntimeError, ValueError) as exc:
            st.error(f"Model execution failed: {exc}")
        else:
            lp_metrics = calculate_metrics(instance, optimum)
            st.subheader("Results")
            stage_columns = st.columns(3)
            stage_columns[0].metric(
                "Stage 1: maximum allocation",
                f"{stage1.objective_kg:.3f} kg",
            )
            if two_stage is not None:
                stage_columns[1].metric(
                    "Stage 2: total allocated kg-km",
                    f"{two_stage.stage2_total_kg_km:.3f}",
                )
                stage_columns[2].metric(
                    "Stage 2 average km/kg",
                    (
                        "Not defined"
                        if two_stage.stage2_average_km_per_kg is None
                        else f"{two_stage.stage2_average_km_per_kg:.3f}"
                    ),
                )
            else:
                stage_columns[1].info(
                    "Stage 2 skipped because eligible pair distances are missing."
                )
            if greedy is None:
                st.warning(
                    f"The LP ran, but the greedy comparison was skipped because "
                    f"{eligible_pairs_missing_distance} eligible pair(s) have no road "
                    "distance. Add verified route distances to compare the methods."
                )
            else:
                greedy_metrics = calculate_metrics(instance, greedy)
                difference = stage1.objective_kg - greedy.objective_kg
                columns = st.columns(3)
                columns[0].metric("Greedy allocated", f"{greedy.objective_kg:.3f} kg")
                columns[1].metric("LP optimum", f"{stage1.objective_kg:.3f} kg")
                columns[2].metric("LP minus greedy", f"{difference:.3f} kg")
                if difference <= 1e-7:
                    st.info(
                        "The LP ties the greedy baseline on this instance. Strict improvement "
                        "is not guaranteed; the optimum is at least as good when both use "
                        "the same feasible region."
                    )
                else:
                    st.info(
                        "The LP improves on this greedy order for these inputs. This is "
                        "instance-specific, not a guarantee of strict improvement."
                    )

            metric_rows = []
            for metric, value in lp_metrics.items():
                row = {"Metric": metric}
                if greedy is not None:
                    row["Greedy"] = greedy_metrics[metric]
                row["LP Stage 2" if two_stage is not None else "LP Stage 1"] = value
                metric_rows.append(row)
            metrics_table = pd.DataFrame(
                metric_rows
            )
            st.dataframe(metrics_table, use_container_width=True, hide_index=True)

            sender_totals = {sender.sender_id: 0.0 for sender in instance.senders}
            receiver_totals = {receiver.receiver_id: 0.0 for receiver in instance.receivers}
            for (sender_id, receiver_id), quantity in optimum.allocations_kg.items():
                sender_totals[sender_id] += quantity
                receiver_totals[receiver_id] += quantity
            balance_columns = st.columns(2)
            balance_columns[0].subheader("Sender balance")
            balance_columns[0].dataframe(
                pd.DataFrame(
                    [
                        {
                            "sender_id": sender.sender_id,
                            "eligible_supply_kg": sender.supply_kg,
                            "allocated_kg": sender_totals[sender.sender_id],
                            "unused_supply_kg": sender.supply_kg - sender_totals[sender.sender_id],
                        }
                        for sender in instance.senders
                    ]
                ),
                use_container_width=True,
                hide_index=True,
            )
            balance_columns[1].subheader("Receiver balance")
            balance_columns[1].dataframe(
                pd.DataFrame(
                    [
                        {
                            "receiver_id": receiver.receiver_id,
                            "capacity_kg": receiver.capacity_kg,
                            "received_kg": receiver_totals[receiver.receiver_id],
                            "remaining_capacity_kg": (
                                receiver.capacity_kg - receiver_totals[receiver.receiver_id]
                            ),
                        }
                        for receiver in instance.receivers
                    ]
                ),
                use_container_width=True,
                hide_index=True,
            )

            allocation_rows = [
                {
                    "sender_id": sender_id,
                    "receiver_id": receiver_id,
                    "allocated_kg": amount,
                }
                for (sender_id, receiver_id), amount in sorted(
                    optimum.allocations_kg.items()
                )
            ]
            allocation_frame = pd.DataFrame(
                allocation_rows,
                columns=["sender_id", "receiver_id", "allocated_kg"],
            )
            st.subheader("LP allocation plan")
            st.caption(
                "Stage 2 allocation minimizes total kg-km only among allocations "
                "that achieve the Stage 1 maximum. This is not a vehicle-tour route."
            )
            st.dataframe(allocation_frame, use_container_width=True, hide_index=True)
            eligible_connections = [
                {
                    "sender_id": pair.sender_id,
                    "receiver_id": pair.receiver_id,
                    "road_distance_km": pair.road_distance_km,
                    "allocated_kg": optimum.allocations_kg.get(
                        (pair.sender_id, pair.receiver_id), 0.0
                    ),
                    "eligibility_evidence": pair.evidence,
                }
                for pair in instance.pairs
                if pair.eligible
            ]
            st.subheader("Eligible and allocated connections")
            st.dataframe(
                pd.DataFrame(eligible_connections),
                use_container_width=True,
                hide_index=True,
            )
            st.download_button(
                "Download LP allocation CSV",
                allocation_frame.to_csv(index=False).encode("utf-8"),
                file_name="lp_allocations.csv",
                mime="text/csv",
            )

            sender_frame = pd.DataFrame(
                [
                    {
                        "sender_id": sender.sender_id,
                        "latitude": sender.latitude,
                        "longitude": sender.longitude,
                    }
                    for sender in instance.senders
                ]
            ).dropna(subset=["latitude", "longitude"])
            receiver_frame = pd.DataFrame(
                [
                    {
                        "receiver_id": receiver.receiver_id,
                        "latitude": receiver.latitude,
                        "longitude": receiver.longitude,
                    }
                    for receiver in instance.receivers
                ]
            ).dropna(subset=["latitude", "longitude"])
            st.subheader("Locations")
            if not sender_frame.empty or not receiver_frame.empty:
                sender_frame["type"] = "Sender"
                receiver_frame["type"] = "Receiver"
                location_frame = pd.concat(
                    [
                        sender_frame.rename(columns={"sender_id": "site_id"}),
                        receiver_frame.rename(columns={"receiver_id": "site_id"}),
                    ],
                    ignore_index=True,
                )
                st.map(location_frame, color="#1f77b4", size=80)
            else:
                st.info(
                    "No coordinates were provided. Locations are not fabricated; "
                    "the map is unavailable for this upload."
                )
else:
    st.info("Upload all three CSV files to validate the dataset and run both methods.")

with st.expander("Input schema and interpretation"):
    st.markdown(
        """
        - `senders.csv`: `sender_id`, `eligible_surplus_kg`, `quantity_unit` (`kg`),
          `period_start`, `period_end`, `evidence_type`, `surplus_evidence`, `source_id`;
          optional `pickup_deadline`, `latitude`, `longitude`.
        - `receivers.csv`: `receiver_id`, `effective_receiving_capacity_kg`,
          `capacity_unit` (`kg`), `period_start`, `period_end`, `evidence_type`,
          `capacity_evidence`, `source_id`; optional coordinates.
        - `eligibility_matrix.csv`: one explicit row for every possible pair with
          `sender_id`, `receiver_id`, `eligible` (`true`/`false`), `road_distance_km`,
          `source_id`, and `eligibility_evidence` for each eligible pair.

        All sites must use the same ISO date period. Missing or unknown eligibility must
        be recorded as false, not silently treated as eligible. The greedy baseline
        allocates to the nearest remaining eligible receiver and then tries the next
        nearest if capacity is exhausted. Tie-breaking uses receiver ID. Evidence
        labels are declarations from the uploader, not independently verified facts.
        """
    )
