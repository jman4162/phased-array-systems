"""
Radar Detection Calculator

Analyze radar detection performance using the radar range equation,
including SNR calculation, detection probability, and range curves.
"""

import streamlit as st
import numpy as np
import pandas
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(
    page_title="Radar Detection Calculator",
    page_icon="🎯",
    layout="wide",
)

st.title("🎯 Radar Detection Calculator")
st.markdown("Analyze radar detection performance using the monostatic radar equation.")

# Try to import the package
try:
    from phased_array_systems.architecture import Architecture, ArrayConfig, RFChainConfig
    from phased_array_systems.scenarios import RadarDetectionScenario
    from phased_array_systems.evaluate import evaluate_case
    from phased_array_systems.models.radar.detection import albersheim_snr, compute_pd_from_snr
    PACKAGE_AVAILABLE = True
except ImportError:
    PACKAGE_AVAILABLE = False
    st.info("Running in demo mode with simplified calculations.")


# Physical constants
C_LIGHT = 3e8  # m/s
K_B = 1.380649e-23  # J/K


def albersheim_snr_simple(pd: float, pfa: float) -> float:
    """Simplified Albersheim's equation for required SNR."""
    # Albersheim's approximation for single pulse
    a = np.log(0.62 / pfa)
    b = np.log(pd / (1 - pd))
    snr_db = a + 0.12 * a * b + 1.7 * b
    return snr_db


def compute_pd_simple(snr_db: float, pfa: float) -> float:
    """Simple Pd calculation from SNR."""
    # Approximation based on Albersheim inverse
    snr_linear = 10 ** (snr_db / 10)
    # Simplified detection probability
    threshold = np.sqrt(-2 * np.log(pfa))
    pd = 0.5 * (1 + np.tanh((snr_linear - threshold) / 2))
    return min(max(pd, 0.001), 0.999)


# Sidebar inputs
st.sidebar.header("Array Configuration")

nx = st.sidebar.select_slider(
    "Elements X (nx)",
    options=[2, 4, 8, 16, 32, 64],
    value=16,
)

ny = st.sidebar.select_slider(
    "Elements Y (ny)",
    options=[2, 4, 8, 16, 32, 64],
    value=16,
)

tx_power_w = st.sidebar.slider(
    "TX Power per Element (W)",
    min_value=0.5,
    max_value=10.0,
    value=2.0,
    step=0.5,
)

st.sidebar.header("Radar Parameters")

freq_ghz = st.sidebar.slider(
    "Frequency (GHz)",
    min_value=1.0,
    max_value=40.0,
    value=10.0,
    step=0.5,
)

bandwidth_mhz = st.sidebar.slider(
    "Bandwidth (MHz)",
    min_value=1.0,
    max_value=100.0,
    value=10.0,
    step=1.0,
)

st.sidebar.header("Target")

target_rcs_dbsm = st.sidebar.slider(
    "Target RCS (dBsm)",
    min_value=-30.0,
    max_value=30.0,
    value=0.0,
    step=1.0,
    help="Radar Cross Section in dB relative to 1 m²"
)

range_km = st.sidebar.slider(
    "Target Range (km)",
    min_value=1.0,
    max_value=500.0,
    value=100.0,
    step=5.0,
)

st.sidebar.header("Detection Requirements")

pd_required = st.sidebar.slider(
    "Required Pd",
    min_value=0.5,
    max_value=0.99,
    value=0.9,
    step=0.01,
    help="Required probability of detection"
)

pfa = st.sidebar.select_slider(
    "Pfa (False Alarm Rate)",
    options=[1e-3, 1e-4, 1e-5, 1e-6, 1e-7, 1e-8, 1e-9],
    value=1e-6,
    format_func=lambda x: f"{x:.0e}",
    help="Probability of false alarm"
)

st.sidebar.header("Integration")

n_pulses = st.sidebar.slider(
    "Number of Pulses",
    min_value=1,
    max_value=100,
    value=10,
    help="Pulses for integration"
)

integration_type = st.sidebar.radio(
    "Integration Type",
    ["Coherent", "Noncoherent"],
    help="Coherent: 10*log10(N), Noncoherent: ~5*log10(N)"
)

# Calculate radar parameters
n_elements = nx * ny
freq_hz = freq_ghz * 1e9
bandwidth_hz = bandwidth_mhz * 1e6
range_m = range_km * 1e3
wavelength_m = C_LIGHT / freq_hz

# Antenna gain approximation
aperture_lambda_sq = nx * 0.5 * ny * 0.5
g_peak_linear = 4 * np.pi * aperture_lambda_sq
g_peak_db = 10 * np.log10(g_peak_linear)

# Total peak power
peak_power_w = tx_power_w * n_elements
peak_power_dbw = 10 * np.log10(peak_power_w)

# System losses (assumed)
system_loss_db = 3.0  # dB
noise_figure_db = 3.0  # dB
noise_temp_k = 290.0  # K

# Noise power
noise_power_w = K_B * noise_temp_k * bandwidth_hz
noise_power_dbw = 10 * np.log10(noise_power_w) + noise_figure_db

# Radar equation constant: (4π)^3 in dB
radar_constant_db = 30 * np.log10(4 * np.pi)

# Single-pulse SNR
range_db = 10 * np.log10(range_m)
wavelength_db = 10 * np.log10(wavelength_m)

snr_single_db = (
    peak_power_dbw
    + 2 * g_peak_db
    + 2 * wavelength_db
    + target_rcs_dbsm
    - 4 * range_db
    - system_loss_db
    - radar_constant_db
    - noise_power_dbw
)

# Integration gain
if integration_type == "Coherent":
    integration_gain_db = 10 * np.log10(n_pulses)
else:
    # Noncoherent integration (approximate)
    integration_gain_db = 5 * np.log10(n_pulses) if n_pulses > 1 else 0

# Integrated SNR
snr_integrated_db = snr_single_db + integration_gain_db

# Required SNR for Pd/Pfa
if PACKAGE_AVAILABLE:
    snr_required_db = albersheim_snr(pd_required, pfa, n_pulses=1)
    pd_achieved = compute_pd_from_snr(snr_integrated_db, pfa)
else:
    snr_required_db = albersheim_snr_simple(pd_required, pfa)
    pd_achieved = compute_pd_simple(snr_integrated_db, pfa)

# SNR margin
snr_margin_db = snr_integrated_db - snr_required_db

# Detection range (where margin = 0)
# R_det / R = (SNR_integrated / SNR_required)^(1/4)
if snr_margin_db > -40:
    detection_range_m = range_m * 10 ** (snr_margin_db / 40)
else:
    detection_range_m = 0.0

# Main content
st.header("Detection Analysis")

# Summary metrics
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "Peak Power",
        f"{peak_power_w:.0f} W",
        f"{peak_power_dbw:.1f} dBW",
    )

with col2:
    st.metric(
        "Antenna Gain",
        f"{g_peak_db:.1f} dB",
        f"{n_elements} elements",
    )

with col3:
    margin_status = "PASS" if snr_margin_db >= 0 else "FAIL"
    st.metric(
        "SNR Margin",
        f"{snr_margin_db:.1f} dB",
        margin_status,
        delta_color="normal" if snr_margin_db >= 0 else "inverse",
    )

with col4:
    st.metric(
        "Max Detection Range",
        f"{detection_range_m/1e3:.1f} km",
        f"for Pd={pd_required:.0%}",
    )

st.divider()

# Detailed results in tabs
tab1, tab2, tab3 = st.tabs(["📈 Detection Curves", "📊 Link Budget", "📋 Detailed Results"])

with tab1:
    st.subheader("Detection Probability vs Range")

    # Generate Pd vs Range curve
    ranges_km = np.linspace(1, range_km * 2, 200)
    ranges_m = ranges_km * 1e3

    pd_values = []
    snr_values = []

    for r_m in ranges_m:
        r_db = 10 * np.log10(r_m)
        snr_single = (
            peak_power_dbw
            + 2 * g_peak_db
            + 2 * wavelength_db
            + target_rcs_dbsm
            - 4 * r_db
            - system_loss_db
            - radar_constant_db
            - noise_power_dbw
        )
        snr_int = snr_single + integration_gain_db
        snr_values.append(snr_int)

        if PACKAGE_AVAILABLE:
            pd = compute_pd_from_snr(snr_int, pfa)
        else:
            pd = compute_pd_simple(snr_int, pfa)
        pd_values.append(pd)

    pd_values = np.array(pd_values)
    snr_values = np.array(snr_values)

    # Create subplot
    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=("Detection Probability vs Range", "SNR vs Range"),
        vertical_spacing=0.15,
    )

    # Pd vs Range
    fig.add_trace(
        go.Scatter(
            x=ranges_km,
            y=pd_values * 100,
            mode="lines",
            line=dict(width=3, color="blue"),
            name="Pd",
            hovertemplate="Range: %{x:.1f} km<br>Pd: %{y:.1f}%<extra></extra>",
        ),
        row=1, col=1
    )

    # Required Pd line
    fig.add_hline(
        y=pd_required * 100,
        line_dash="dash",
        line_color="red",
        annotation_text=f"Required Pd = {pd_required:.0%}",
        row=1, col=1
    )

    # Current range marker
    fig.add_vline(
        x=range_km,
        line_dash="dot",
        line_color="green",
        annotation_text=f"Target Range = {range_km:.0f} km",
        row=1, col=1
    )

    # SNR vs Range
    fig.add_trace(
        go.Scatter(
            x=ranges_km,
            y=snr_values,
            mode="lines",
            line=dict(width=3, color="orange"),
            name="SNR (integrated)",
            hovertemplate="Range: %{x:.1f} km<br>SNR: %{y:.1f} dB<extra></extra>",
        ),
        row=2, col=1
    )

    # Required SNR line
    fig.add_hline(
        y=snr_required_db,
        line_dash="dash",
        line_color="red",
        annotation_text=f"Required SNR = {snr_required_db:.1f} dB",
        row=2, col=1
    )

    fig.update_layout(height=600, showlegend=True)
    fig.update_yaxes(title_text="Pd (%)", range=[0, 100], row=1, col=1)
    fig.update_yaxes(title_text="SNR (dB)", row=2, col=1)
    fig.update_xaxes(title_text="Range (km)", row=2, col=1)

    st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.subheader("Radar Link Budget")

    # Link budget table
    budget_items = [
        ("Peak Transmit Power", f"{peak_power_dbw:.1f} dBW", "Pt"),
        ("Transmit Antenna Gain", f"+{g_peak_db:.1f} dB", "Gt"),
        ("Receive Antenna Gain", f"+{g_peak_db:.1f} dB", "Gr (same antenna)"),
        ("Wavelength Factor", f"+{2*wavelength_db:.1f} dB", "2×λ²"),
        ("Target RCS", f"+{target_rcs_dbsm:.1f} dBsm", "σ"),
        ("Range Factor", f"-{4*range_db:.1f} dB", "R⁴"),
        ("System Losses", f"-{system_loss_db:.1f} dB", "L"),
        ("Radar Constant", f"-{radar_constant_db:.1f} dB", "(4π)³"),
        ("Noise Power", f"-{noise_power_dbw:.1f} dBW", "kTB + NF"),
    ]

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Radar Equation Components**")
        budget_df = pandas.DataFrame(budget_items, columns=["Component", "Value", "Symbol"])
        st.dataframe(budget_df, use_container_width=True, hide_index=True)

    with col2:
        st.markdown("**SNR Summary**")
        st.write(f"- Single-Pulse SNR: **{snr_single_db:.1f} dB**")
        st.write(f"- Integration Gain ({n_pulses} pulses, {integration_type.lower()}): **+{integration_gain_db:.1f} dB**")
        st.write(f"- Integrated SNR: **{snr_integrated_db:.1f} dB**")
        st.write(f"- Required SNR (Pd={pd_required:.0%}, Pfa={pfa:.0e}): **{snr_required_db:.1f} dB**")
        st.divider()
        margin_color = "green" if snr_margin_db >= 0 else "red"
        st.markdown(f"**SNR Margin: <span style='color:{margin_color}'>{snr_margin_db:.1f} dB</span>**",
                    unsafe_allow_html=True)

with tab3:
    st.subheader("Complete Results")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**System Parameters**")
        st.write(f"- Array Size: {nx} × {ny} = {n_elements} elements")
        st.write(f"- Frequency: {freq_ghz:.1f} GHz (λ = {wavelength_m*1000:.1f} mm)")
        st.write(f"- Bandwidth: {bandwidth_mhz:.1f} MHz")
        st.write(f"- Peak Power: {peak_power_w:.1f} W ({peak_power_dbw:.1f} dBW)")
        st.write(f"- Antenna Gain: {g_peak_db:.1f} dB")

    with col2:
        st.markdown("**Detection Performance**")
        st.write(f"- Target RCS: {target_rcs_dbsm:.1f} dBsm ({10**(target_rcs_dbsm/10):.2f} m²)")
        st.write(f"- Target Range: {range_km:.1f} km")
        st.write(f"- Achieved Pd: {pd_achieved:.1%}")
        st.write(f"- Detection Range: {detection_range_m/1e3:.1f} km")

    st.divider()
    st.markdown("**Integration**")
    st.write(f"- Number of Pulses: {n_pulses}")
    st.write(f"- Integration Type: {integration_type}")
    st.write(f"- Integration Gain: {integration_gain_db:.1f} dB")

    # SNR breakdown
    st.divider()
    st.markdown("**SNR Breakdown**")

    snr_breakdown = pandas.DataFrame({
        "Metric": ["Single-Pulse SNR", "Integration Gain", "Integrated SNR", "Required SNR", "SNR Margin"],
        "Value (dB)": [snr_single_db, integration_gain_db, snr_integrated_db, snr_required_db, snr_margin_db],
    })
    snr_breakdown["Value (dB)"] = snr_breakdown["Value (dB)"].round(1)

    st.dataframe(snr_breakdown, use_container_width=True, hide_index=True)

# RCS sensitivity analysis
st.divider()
st.header("RCS Sensitivity Analysis")

st.markdown("How does detection range vary with target RCS?")

rcs_values_dbsm = np.arange(-20, 21, 5)
detection_ranges = []

for rcs_dbsm in rcs_values_dbsm:
    # Find range where SNR margin = 0
    # SNR scales as 1/R^4, so we can solve directly
    # At current range, SNR_margin = snr_integrated - snr_required
    # SNR at R_det: SNR_det = SNR_required
    # SNR(R_det) = SNR(R) - 40*log10(R_det/R) + (rcs_dbsm - target_rcs_dbsm)

    # More directly: R_det^4 proportional to SNR_linear
    base_snr_margin = snr_margin_db + (rcs_dbsm - target_rcs_dbsm)
    if base_snr_margin > -40:
        r_det = range_m * 10 ** (base_snr_margin / 40)
    else:
        r_det = 0
    detection_ranges.append(r_det / 1e3)

fig = go.Figure()

fig.add_trace(go.Bar(
    x=[f"{rcs:.0f}" for rcs in rcs_values_dbsm],
    y=detection_ranges,
    marker_color=["green" if r > range_km else "orange" if r > range_km*0.5 else "red"
                  for r in detection_ranges],
    text=[f"{r:.0f}" for r in detection_ranges],
    textposition="outside",
    hovertemplate="RCS: %{x} dBsm<br>Detection Range: %{y:.1f} km<extra></extra>",
))

# Reference line for current target range
fig.add_hline(
    y=range_km,
    line_dash="dash",
    line_color="blue",
    annotation_text=f"Target Range: {range_km:.0f} km",
)

fig.update_layout(
    xaxis_title="Target RCS (dBsm)",
    yaxis_title="Detection Range (km)",
    height=400,
)

st.plotly_chart(fig, use_container_width=True)

# Common RCS reference
with st.expander("📋 Common Target RCS Values"):
    st.markdown("""
    | Target | Typical RCS (m²) | dBsm |
    |--------|------------------|------|
    | Small drone | 0.01 | -20 |
    | Bird | 0.01 | -20 |
    | Human | 1 | 0 |
    | Small aircraft | 2-5 | 3-7 |
    | Fighter jet (head-on) | 1-5 | 0-7 |
    | Commercial aircraft | 10-100 | 10-20 |
    | Large ship | 10,000-100,000 | 40-50 |
    """)
