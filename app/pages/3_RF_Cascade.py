"""
RF Cascade Analyzer

Interactive analysis of cascaded RF chain performance including
noise figure, gain, linearity, and dynamic range.
"""

import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(
    page_title="RF Cascade Analyzer",
    page_icon="🔗",
    layout="wide",
)

st.title("🔗 RF Cascade Analyzer")
st.markdown("Analyze cascaded noise figure, gain, and linearity for multi-stage RF chains.")

# Try to import the package
try:
    from phased_array_systems.models.rf.cascade import (
        RFStage,
        cascade_analysis,
        friis_noise_figure,
        cascade_iip3,
        mds_from_noise_figure,
    )
    PACKAGE_AVAILABLE = True
except ImportError:
    PACKAGE_AVAILABLE = False
    st.info("Running in demo mode with simplified calculations.")


# Reference temperature
T0 = 290.0  # K
K_B = 1.380649e-23  # J/K


def friis_nf_simple(stages: list[tuple[float, float]]) -> dict:
    """Simple Friis calculation for demo mode."""
    if not stages:
        return {"total_nf_db": 0, "total_gain_db": 0, "stage_contributions_db": []}

    gains_linear = [10 ** (g / 10) for g, _ in stages]
    nfs_linear = [10 ** (nf / 10) for _, nf in stages]

    f_total = nfs_linear[0]
    cumulative_gain = gains_linear[0]
    contributions = [10 * np.log10(nfs_linear[0])]

    for i in range(1, len(stages)):
        contribution = (nfs_linear[i] - 1) / cumulative_gain
        f_total += contribution
        contributions.append(10 * np.log10(1 + contribution))
        cumulative_gain *= gains_linear[i]

    return {
        "total_nf_db": 10 * np.log10(f_total),
        "total_gain_db": sum(g for g, _ in stages),
        "stage_contributions_db": contributions,
    }


def cascade_iip3_simple(stages: list[tuple[float, float]]) -> dict:
    """Simple IIP3 cascade for demo mode."""
    if not stages:
        return {"iip3_dbm": 100, "oip3_dbm": 100, "total_gain_db": 0}

    gains_linear = [10 ** (g / 10) for g, _ in stages]
    iip3s_linear = [10 ** (iip3 / 10) for _, iip3 in stages]

    inv_iip3_total = 1 / iip3s_linear[0]
    cumulative_gain = gains_linear[0]

    for i in range(1, len(stages)):
        inv_iip3_total += cumulative_gain / iip3s_linear[i]
        cumulative_gain *= gains_linear[i]

    iip3_total = 1 / inv_iip3_total
    iip3_dbm = 10 * np.log10(iip3_total)
    total_gain_db = sum(g for g, _ in stages)

    return {
        "iip3_dbm": iip3_dbm,
        "oip3_dbm": iip3_dbm + total_gain_db,
        "total_gain_db": total_gain_db,
    }


# Sidebar - Stage Configuration
st.sidebar.header("RF Chain Configuration")

# Predefined stage templates
STAGE_TEMPLATES = {
    "LNA": {"gain_db": 20.0, "nf_db": 1.5, "iip3_dbm": -5.0},
    "Filter": {"gain_db": -2.0, "nf_db": 2.0, "iip3_dbm": 50.0},
    "Mixer": {"gain_db": -6.0, "nf_db": 8.0, "iip3_dbm": 10.0},
    "IF Amp": {"gain_db": 15.0, "nf_db": 3.0, "iip3_dbm": 15.0},
    "Driver Amp": {"gain_db": 10.0, "nf_db": 4.0, "iip3_dbm": 20.0},
    "Custom": {"gain_db": 10.0, "nf_db": 3.0, "iip3_dbm": 10.0},
}

# Number of stages
n_stages = st.sidebar.number_input(
    "Number of Stages",
    min_value=1,
    max_value=10,
    value=4,
    help="Number of RF stages in the cascade"
)

st.sidebar.divider()

# Configure each stage
stages = []
for i in range(n_stages):
    st.sidebar.subheader(f"Stage {i+1}")

    template = st.sidebar.selectbox(
        f"Type",
        list(STAGE_TEMPLATES.keys()),
        key=f"template_{i}",
        index=0 if i == 0 else (1 if i == 1 else (2 if i == 2 else 3))
    )

    defaults = STAGE_TEMPLATES[template]

    name = st.sidebar.text_input(
        f"Name",
        value=f"{template}" if template != "Custom" else f"Stage {i+1}",
        key=f"name_{i}"
    )

    gain = st.sidebar.slider(
        f"Gain (dB)",
        min_value=-10.0,
        max_value=40.0,
        value=defaults["gain_db"],
        step=0.5,
        key=f"gain_{i}"
    )

    nf = st.sidebar.slider(
        f"Noise Figure (dB)",
        min_value=0.5,
        max_value=15.0,
        value=defaults["nf_db"],
        step=0.5,
        key=f"nf_{i}"
    )

    iip3 = st.sidebar.slider(
        f"IIP3 (dBm)",
        min_value=-20.0,
        max_value=50.0,
        value=defaults["iip3_dbm"],
        step=1.0,
        key=f"iip3_{i}"
    )

    stages.append({
        "name": name,
        "gain_db": gain,
        "nf_db": nf,
        "iip3_dbm": iip3,
    })

    st.sidebar.divider()

# Analysis parameters
st.sidebar.header("Analysis Settings")

bandwidth_mhz = st.sidebar.slider(
    "Bandwidth (MHz)",
    min_value=0.1,
    max_value=100.0,
    value=10.0,
    step=0.1,
    help="Analysis bandwidth"
)

input_power_dbm = st.sidebar.slider(
    "Input Power (dBm)",
    min_value=-100.0,
    max_value=-20.0,
    value=-60.0,
    step=1.0,
    help="Reference input signal level"
)

bandwidth_hz = bandwidth_mhz * 1e6

# Perform cascade analysis
if PACKAGE_AVAILABLE:
    rf_stages = [
        RFStage(
            name=s["name"],
            gain_db=s["gain_db"],
            noise_figure_db=s["nf_db"],
            iip3_dbm=s["iip3_dbm"],
        )
        for s in stages
    ]
    results = cascade_analysis(rf_stages, bandwidth_hz, input_power_dbm)
else:
    # Demo mode calculations
    nf_stages = [(s["gain_db"], s["nf_db"]) for s in stages]
    iip3_stages = [(s["gain_db"], s["iip3_dbm"]) for s in stages]

    nf_result = friis_nf_simple(nf_stages)
    iip3_result = cascade_iip3_simple(iip3_stages)

    # MDS calculation
    kt_dbm_hz = 10 * np.log10(K_B * T0 * 1000)
    ktb_dbm = kt_dbm_hz + 10 * np.log10(bandwidth_hz)
    noise_floor_dbm = ktb_dbm + nf_result["total_nf_db"]
    mds_dbm = noise_floor_dbm

    # SFDR
    sfdr_db = (2/3) * (iip3_result["iip3_dbm"] - noise_floor_dbm)

    # Signal tracking
    levels = [input_power_dbm]
    level = input_power_dbm
    for s in stages:
        level += s["gain_db"]
        levels.append(level)

    results = {
        "total_gain_db": nf_result["total_gain_db"],
        "total_nf_db": nf_result["total_nf_db"],
        "noise_temp_k": T0 * (10 ** (nf_result["total_nf_db"] / 10) - 1),
        "stage_nf_contributions_db": nf_result["stage_contributions_db"],
        "iip3_dbm": iip3_result["iip3_dbm"],
        "oip3_dbm": iip3_result["oip3_dbm"],
        "sfdr_db": sfdr_db,
        "mds_dbm": mds_dbm,
        "noise_floor_dbm": noise_floor_dbm,
        "input_power_dbm": input_power_dbm,
        "output_power_dbm": levels[-1],
        "stage_levels_dbm": levels,
        "stage_names": ["Input"] + [s["name"] for s in stages],
    }

# Main content - Results display
st.header("Cascade Results")

# Key metrics
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "Total Gain",
        f"{results['total_gain_db']:.1f} dB",
        help="Sum of all stage gains"
    )

with col2:
    st.metric(
        "System NF",
        f"{results['total_nf_db']:.2f} dB",
        help="Cascaded noise figure (Friis)"
    )

with col3:
    st.metric(
        "System IIP3",
        f"{results['iip3_dbm']:.1f} dBm",
        help="Cascaded input IP3"
    )

with col4:
    st.metric(
        "SFDR",
        f"{results['sfdr_db']:.1f} dB",
        help="Spurious-Free Dynamic Range"
    )

st.divider()

# Detailed results in tabs
tab1, tab2, tab3 = st.tabs(["📊 Signal Level Chart", "📈 NF Contributions", "📋 Detailed Results"])

with tab1:
    st.subheader("Signal Level Through Chain")

    # Create waterfall chart
    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=("Signal Level (dBm)", "Cumulative Gain (dB)"),
        vertical_spacing=0.15,
    )

    stage_names = results["stage_names"]
    levels = results["stage_levels_dbm"]

    # Signal level trace
    fig.add_trace(
        go.Scatter(
            x=stage_names,
            y=levels,
            mode="lines+markers",
            marker=dict(size=12, color="blue"),
            line=dict(width=3, color="blue"),
            name="Signal Level",
            hovertemplate="%{x}<br>Level: %{y:.1f} dBm<extra></extra>",
        ),
        row=1, col=1
    )

    # Add noise floor reference
    noise_floor = results.get("noise_floor_dbm", -100)
    fig.add_hline(
        y=noise_floor,
        line_dash="dash",
        line_color="red",
        annotation_text=f"Noise Floor: {noise_floor:.1f} dBm",
        row=1, col=1
    )

    # Cumulative gain
    cumulative_gains = [0]
    cum_gain = 0
    for s in stages:
        cum_gain += s["gain_db"]
        cumulative_gains.append(cum_gain)

    fig.add_trace(
        go.Bar(
            x=stage_names,
            y=cumulative_gains,
            marker_color=["gray"] + ["green" if stages[i]["gain_db"] > 0 else "red"
                                      for i in range(len(stages))],
            name="Cumulative Gain",
            hovertemplate="%{x}<br>Cum. Gain: %{y:.1f} dB<extra></extra>",
        ),
        row=2, col=1
    )

    fig.update_layout(
        height=600,
        showlegend=True,
        legend=dict(yanchor="top", y=0.99, xanchor="right", x=0.99),
    )

    fig.update_yaxes(title_text="Level (dBm)", row=1, col=1)
    fig.update_yaxes(title_text="Gain (dB)", row=2, col=1)

    st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.subheader("Noise Figure Contributions by Stage")

    contributions = results.get("stage_nf_contributions_db", [])

    if contributions:
        # Bar chart of NF contributions
        fig = go.Figure()

        fig.add_trace(go.Bar(
            x=[stages[i]["name"] for i in range(len(contributions))],
            y=contributions,
            marker_color=["#FF6B6B" if i == 0 else "#4ECDC4" for i in range(len(contributions))],
            text=[f"{c:.2f} dB" for c in contributions],
            textposition="outside",
            hovertemplate="%{x}<br>NF Contribution: %{y:.3f} dB<extra></extra>",
        ))

        fig.update_layout(
            xaxis_title="Stage",
            yaxis_title="Noise Figure Contribution (dB)",
            height=400,
        )

        st.plotly_chart(fig, use_container_width=True)

        # Explanation
        st.markdown("""
        **Key Insight:** The first stage (typically an LNA) dominates the system noise figure.
        This is why low-noise amplifiers with high gain are placed at the front of receiver chains.

        *Friis Formula:* $F_{total} = F_1 + \\frac{F_2 - 1}{G_1} + \\frac{F_3 - 1}{G_1 G_2} + ...$
        """)

with tab3:
    st.subheader("Complete Analysis Results")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Gain & Noise**")
        st.write(f"- Total Gain: {results['total_gain_db']:.2f} dB")
        st.write(f"- System Noise Figure: {results['total_nf_db']:.3f} dB")
        st.write(f"- Noise Temperature: {results['noise_temp_k']:.1f} K")
        st.write(f"- Noise Floor: {results['noise_floor_dbm']:.1f} dBm ({bandwidth_mhz:.1f} MHz BW)")

    with col2:
        st.markdown("**Linearity & Dynamic Range**")
        st.write(f"- Input IP3: {results['iip3_dbm']:.1f} dBm")
        st.write(f"- Output IP3: {results['oip3_dbm']:.1f} dBm")
        st.write(f"- SFDR: {results['sfdr_db']:.1f} dB")
        st.write(f"- MDS (0 dB SNR): {results['mds_dbm']:.1f} dBm")

    st.divider()

    st.markdown("**Signal Levels**")
    st.write(f"- Input Power: {results['input_power_dbm']:.1f} dBm")
    st.write(f"- Output Power: {results['output_power_dbm']:.1f} dBm")

    # Stage summary table
    st.divider()
    st.markdown("**Stage Summary**")

    stage_df = pd.DataFrame(stages)
    stage_df.index = stage_df.index + 1
    stage_df.index.name = "Stage"
    stage_df.columns = ["Name", "Gain (dB)", "NF (dB)", "IIP3 (dBm)"]

    st.dataframe(stage_df, use_container_width=True)

# Dynamic range visualization
st.divider()
st.header("Dynamic Range Analysis")

col1, col2 = st.columns(2)

with col1:
    # Create dynamic range diagram
    fig = go.Figure()

    noise_floor = results["noise_floor_dbm"]
    iip3 = results["iip3_dbm"]
    sfdr = results["sfdr_db"]
    mds = results["mds_dbm"]

    # Dynamic range bar
    max_signal = noise_floor + sfdr

    fig.add_trace(go.Bar(
        y=["Dynamic Range"],
        x=[sfdr],
        orientation="h",
        base=[noise_floor],
        marker_color="lightgreen",
        name="SFDR",
        text=[f"SFDR: {sfdr:.1f} dB"],
        textposition="inside",
    ))

    # Markers
    fig.add_vline(x=noise_floor, line_dash="dash", line_color="blue",
                  annotation_text=f"Noise Floor\n{noise_floor:.1f} dBm")
    fig.add_vline(x=iip3, line_dash="dash", line_color="red",
                  annotation_text=f"IIP3\n{iip3:.1f} dBm")

    fig.update_layout(
        xaxis_title="Power Level (dBm)",
        height=200,
        showlegend=False,
        margin=dict(l=20, r=20, t=40, b=40),
    )

    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.markdown("""
    **Dynamic Range Metrics**

    | Metric | Value | Description |
    |--------|-------|-------------|
    | Noise Floor | {:.1f} dBm | Minimum detectable signal (SNR=0) |
    | SFDR | {:.1f} dB | Spurious-free dynamic range |
    | IIP3 | {:.1f} dBm | Input 3rd-order intercept |
    | OIP3 | {:.1f} dBm | Output 3rd-order intercept |

    *SFDR = (2/3) × (IIP3 - Noise Floor)*
    """.format(
        results["noise_floor_dbm"],
        results["sfdr_db"],
        results["iip3_dbm"],
        results["oip3_dbm"],
    ))
