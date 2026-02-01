"""
Trade Study - DOE and Pareto Optimization

Generate Design of Experiments, run batch evaluations,
and visualize Pareto-optimal designs.
"""

import streamlit as st
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(
    page_title="Trade Study",
    page_icon="📊",
    layout="wide",
)

st.title("📊 Trade Study")
st.markdown("Design of Experiments with Pareto optimization for phased array systems.")

# Try to import the package
try:
    from phased_array_systems.architecture import Architecture, ArrayConfig, RFChainConfig, CostConfig
    from phased_array_systems.scenarios import CommsLinkScenario
    from phased_array_systems.evaluate import evaluate_case
    from phased_array_systems.trades import DesignSpace, generate_doe, extract_pareto
    PACKAGE_AVAILABLE = True
except ImportError:
    PACKAGE_AVAILABLE = False
    st.info("Running in demo mode. Install `phased-array-systems` for full functionality.")


def generate_demo_results(n_samples: int, nx_range: tuple, ny_range: tuple,
                          power_range: tuple, seed: int = 42) -> pd.DataFrame:
    """Generate demo results for visualization when package not available."""
    rng = np.random.default_rng(seed)

    # Generate random design points
    nx_vals = rng.choice([2, 4, 8, 16, 32], n_samples)
    ny_vals = rng.choice([2, 4, 8, 16, 32], n_samples)
    power_vals = rng.uniform(power_range[0], power_range[1], n_samples)

    results = []
    for i in range(n_samples):
        nx, ny = nx_vals[i], ny_vals[i]
        n_elem = nx * ny
        tx_power = power_vals[i]

        # Simplified calculations
        g_peak_db = 10 * np.log10(4 * np.pi * n_elem * 0.25)  # Rough gain
        eirp_dbw = 10 * np.log10(tx_power * n_elem) + g_peak_db
        cost_usd = 100 * n_elem
        prime_power_w = tx_power * n_elem / 0.3

        # Add some noise
        eirp_dbw += rng.normal(0, 0.5)
        cost_usd *= (1 + rng.normal(0, 0.05))

        results.append({
            "case_id": f"case_{i:05d}",
            "array.nx": nx,
            "array.ny": ny,
            "rf.tx_power_w_per_elem": tx_power,
            "n_elements": n_elem,
            "g_peak_db": g_peak_db,
            "eirp_dbw": eirp_dbw,
            "cost_usd": cost_usd,
            "prime_power_w": prime_power_w,
            "link_margin_db": eirp_dbw - 60 + rng.normal(0, 2),  # Rough margin
        })

    return pd.DataFrame(results)


# Sidebar - Design Space Configuration
st.sidebar.header("Design Space")

st.sidebar.subheader("Array Size (nx)")
nx_min = st.sidebar.select_slider("Min nx", [2, 4, 8, 16, 32], value=4, key="nx_min")
nx_max = st.sidebar.select_slider("Max nx", [2, 4, 8, 16, 32], value=16, key="nx_max")

st.sidebar.subheader("Array Size (ny)")
ny_min = st.sidebar.select_slider("Min ny", [2, 4, 8, 16, 32], value=4, key="ny_min")
ny_max = st.sidebar.select_slider("Max ny", [2, 4, 8, 16, 32], value=16, key="ny_max")

st.sidebar.subheader("TX Power (W/element)")
power_min = st.sidebar.slider("Min Power", 0.1, 5.0, 0.5, 0.1)
power_max = st.sidebar.slider("Max Power", 0.1, 5.0, 3.0, 0.1)

st.sidebar.divider()
st.sidebar.header("DOE Settings")

doe_method = st.sidebar.selectbox(
    "Sampling Method",
    ["Latin Hypercube (LHS)", "Random", "Grid"],
    help="LHS provides better space-filling properties"
)
method_map = {
    "Latin Hypercube (LHS)": "lhs",
    "Random": "random",
    "Grid": "grid"
}

n_samples = st.sidebar.slider(
    "Number of Samples",
    min_value=10,
    max_value=500,
    value=50,
    step=10,
    help="Number of design points to evaluate"
)

seed = st.sidebar.number_input(
    "Random Seed",
    min_value=0,
    max_value=9999,
    value=42,
    help="For reproducibility"
)

st.sidebar.divider()
st.sidebar.header("Scenario (Fixed)")

freq_ghz = st.sidebar.number_input("Frequency (GHz)", value=10.0, disabled=True)
range_km = st.sidebar.number_input("Range (km)", value=100.0, disabled=True)
bandwidth_mhz = st.sidebar.number_input("Bandwidth (MHz)", value=10.0, disabled=True)
required_snr = st.sidebar.number_input("Required SNR (dB)", value=10.0, disabled=True)

# Main content
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("Design Space Summary")
    st.markdown(f"""
    | Variable | Min | Max |
    |----------|-----|-----|
    | nx (elements) | {nx_min} | {nx_max} |
    | ny (elements) | {ny_min} | {ny_max} |
    | TX Power (W) | {power_min} | {power_max} |
    """)

with col2:
    run_study = st.button("🚀 Run Trade Study", type="primary", use_container_width=True)

# Session state for results
if "trade_results" not in st.session_state:
    st.session_state.trade_results = None

if run_study:
    with st.spinner(f"Running {n_samples} design cases..."):
        if PACKAGE_AVAILABLE:
            # Use actual package
            space = DesignSpace()

            # For array size, we need to use power-of-2 values
            nx_options = [v for v in [2, 4, 8, 16, 32, 64] if nx_min <= v <= nx_max]
            ny_options = [v for v in [2, 4, 8, 16, 32, 64] if ny_min <= v <= ny_max]

            space.add_variable("array.nx", "categorical", values=nx_options)
            space.add_variable("array.ny", "categorical", values=ny_options)
            space.add_variable("rf.tx_power_w_per_elem", "float", low=power_min, high=power_max)

            # Generate DOE
            method = method_map[doe_method]
            if method == "grid":
                doe = space.sample(method="grid")
            else:
                doe = space.sample(method=method, n_samples=n_samples, seed=seed)

            # Evaluate each case
            scenario = CommsLinkScenario(
                freq_hz=freq_ghz * 1e9,
                bandwidth_hz=bandwidth_mhz * 1e6,
                range_m=range_km * 1e3,
                required_snr_db=required_snr,
            )

            results = []
            progress_bar = st.progress(0)
            for i, row in doe.iterrows():
                arch = Architecture(
                    array=ArrayConfig(
                        nx=int(row["array.nx"]),
                        ny=int(row["array.ny"]),
                        dx_lambda=0.5,
                        dy_lambda=0.5,
                        enforce_subarray_constraint=False,
                    ),
                    rf=RFChainConfig(
                        tx_power_w_per_elem=row["rf.tx_power_w_per_elem"],
                        pa_efficiency=0.3,
                    ),
                    cost=CostConfig(cost_per_elem_usd=100),
                )

                metrics = evaluate_case(arch, scenario)
                result = dict(row)
                result.update(metrics)
                result["n_elements"] = int(row["array.nx"]) * int(row["array.ny"])
                results.append(result)

                progress_bar.progress((i + 1) / len(doe))

            st.session_state.trade_results = pd.DataFrame(results)

        else:
            # Demo mode
            st.session_state.trade_results = generate_demo_results(
                n_samples,
                (nx_min, nx_max),
                (ny_min, ny_max),
                (power_min, power_max),
                seed
            )

    st.success(f"Completed {len(st.session_state.trade_results)} design evaluations!")

# Display results
if st.session_state.trade_results is not None:
    results_df = st.session_state.trade_results

    st.divider()
    st.header("Results Analysis")

    # Extract Pareto frontier
    if PACKAGE_AVAILABLE:
        pareto_df = extract_pareto(results_df, [
            ("cost_usd", "minimize"),
            ("eirp_dbw", "maximize"),
        ])
    else:
        # Simple Pareto extraction for demo
        is_pareto = np.ones(len(results_df), dtype=bool)
        for i in range(len(results_df)):
            for j in range(len(results_df)):
                if i != j:
                    # j dominates i if j has lower cost AND higher EIRP
                    if (results_df.iloc[j]["cost_usd"] <= results_df.iloc[i]["cost_usd"] and
                        results_df.iloc[j]["eirp_dbw"] >= results_df.iloc[i]["eirp_dbw"] and
                        (results_df.iloc[j]["cost_usd"] < results_df.iloc[i]["cost_usd"] or
                         results_df.iloc[j]["eirp_dbw"] > results_df.iloc[i]["eirp_dbw"])):
                        is_pareto[i] = False
                        break
        pareto_df = results_df[is_pareto]

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Designs", len(results_df))

    with col2:
        st.metric("Pareto Optimal", len(pareto_df))

    with col3:
        feasible = len(results_df[results_df.get("link_margin_db", 0) >= 0]) if "link_margin_db" in results_df else len(results_df)
        st.metric("Feasible Designs", feasible)

    with col4:
        best_cost = pareto_df["cost_usd"].min()
        st.metric("Min Cost (Pareto)", f"${best_cost:,.0f}")

    # Tabs for different views
    tab1, tab2, tab3 = st.tabs(["📈 Pareto Plot", "📊 Scatter Matrix", "📋 Data Table"])

    with tab1:
        st.subheader("Pareto Frontier: Cost vs EIRP")

        # Create Pareto plot
        fig = go.Figure()

        # All points
        fig.add_trace(go.Scatter(
            x=results_df["cost_usd"],
            y=results_df["eirp_dbw"],
            mode="markers",
            marker=dict(
                size=8,
                color=results_df["n_elements"],
                colorscale="Viridis",
                colorbar=dict(title="Elements"),
                opacity=0.6,
            ),
            text=[f"nx={r['array.nx']}, ny={r['array.ny']}<br>Power={r['rf.tx_power_w_per_elem']:.1f}W"
                  for _, r in results_df.iterrows()],
            hovertemplate="<b>Cost:</b> $%{x:,.0f}<br><b>EIRP:</b> %{y:.1f} dBW<br>%{text}<extra></extra>",
            name="All Designs"
        ))

        # Pareto frontier
        pareto_sorted = pareto_df.sort_values("cost_usd")
        fig.add_trace(go.Scatter(
            x=pareto_sorted["cost_usd"],
            y=pareto_sorted["eirp_dbw"],
            mode="lines+markers",
            marker=dict(size=12, color="red", symbol="star"),
            line=dict(color="red", width=2, dash="dash"),
            name="Pareto Frontier"
        ))

        fig.update_layout(
            xaxis_title="System Cost (USD)",
            yaxis_title="EIRP (dBW)",
            legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01),
            height=500,
        )

        st.plotly_chart(fig, use_container_width=True)

        # Pareto table
        st.subheader("Pareto-Optimal Designs")
        pareto_display = pareto_sorted[["case_id", "array.nx", "array.ny", "n_elements",
                                         "rf.tx_power_w_per_elem", "eirp_dbw", "cost_usd"]].copy()
        pareto_display.columns = ["Case ID", "nx", "ny", "Elements", "TX Power (W)", "EIRP (dBW)", "Cost ($)"]
        pareto_display["EIRP (dBW)"] = pareto_display["EIRP (dBW)"].round(1)
        pareto_display["TX Power (W)"] = pareto_display["TX Power (W)"].round(2)
        pareto_display["Cost ($)"] = pareto_display["Cost ($)"].round(0).astype(int)
        st.dataframe(pareto_display, use_container_width=True)

    with tab2:
        st.subheader("Scatter Matrix")

        # Select columns for scatter matrix
        scatter_cols = ["n_elements", "rf.tx_power_w_per_elem", "eirp_dbw", "cost_usd"]
        if "link_margin_db" in results_df.columns:
            scatter_cols.append("link_margin_db")

        fig = px.scatter_matrix(
            results_df,
            dimensions=scatter_cols,
            color="n_elements",
            color_continuous_scale="Viridis",
            labels={
                "n_elements": "Elements",
                "rf.tx_power_w_per_elem": "TX Power (W)",
                "eirp_dbw": "EIRP (dBW)",
                "cost_usd": "Cost ($)",
                "link_margin_db": "Margin (dB)",
            },
            height=700,
        )
        fig.update_traces(diagonal_visible=False, showupperhalf=False)
        st.plotly_chart(fig, use_container_width=True)

    with tab3:
        st.subheader("Full Results Table")

        # Column selection
        all_cols = list(results_df.columns)
        default_cols = ["case_id", "array.nx", "array.ny", "n_elements",
                       "rf.tx_power_w_per_elem", "g_peak_db", "eirp_dbw", "cost_usd"]
        default_cols = [c for c in default_cols if c in all_cols]

        selected_cols = st.multiselect(
            "Select columns to display",
            all_cols,
            default=default_cols
        )

        if selected_cols:
            display_df = results_df[selected_cols].copy()

            # Format numeric columns
            for col in display_df.select_dtypes(include=[np.number]).columns:
                if "db" in col.lower() or col == "cost_usd":
                    display_df[col] = display_df[col].round(1)
                else:
                    display_df[col] = display_df[col].round(3)

            st.dataframe(display_df, use_container_width=True)

            # Download button
            csv = display_df.to_csv(index=False)
            st.download_button(
                label="📥 Download Results (CSV)",
                data=csv,
                file_name="trade_study_results.csv",
                mime="text/csv"
            )

else:
    st.info("👆 Configure your design space and click **Run Trade Study** to begin.")

    # Show example visualization
    st.subheader("Example Output")
    st.image("https://plotly.com/~chris/16312.png", caption="Example Pareto frontier visualization")
