"""
Single Case Calculator

Interactive evaluation of a single phased array configuration
with real-time metrics display and requirement verification.
"""

import streamlit as st
import numpy as np

st.set_page_config(
    page_title="Single Case Calculator",
    page_icon="🎛️",
    layout="wide",
)

st.title("🎛️ Single Case Calculator")
st.markdown("Evaluate a single phased array configuration with real-time metrics.")

# Try to import the package
try:
    from phased_array_systems.architecture import Architecture, ArrayConfig, RFChainConfig, CostConfig
    from phased_array_systems.scenarios import CommsLinkScenario
    from phased_array_systems.evaluate import evaluate_case
    from phased_array_systems.requirements import RequirementSet, Requirement
    PACKAGE_AVAILABLE = True
except ImportError:
    PACKAGE_AVAILABLE = False
    st.warning("""
    **Package not installed.** Install with:
    ```bash
    pip install phased-array-systems
    ```
    Running in demo mode with simplified calculations.
    """)

# Sidebar inputs
st.sidebar.header("Array Configuration")

# Array geometry
nx = st.sidebar.select_slider(
    "Elements X (nx)",
    options=[2, 4, 8, 16, 32, 64],
    value=8,
    help="Number of elements in X direction (power of 2)"
)

ny = st.sidebar.select_slider(
    "Elements Y (ny)",
    options=[2, 4, 8, 16, 32, 64],
    value=8,
    help="Number of elements in Y direction (power of 2)"
)

dx_lambda = st.sidebar.slider(
    "Spacing X (λ)",
    min_value=0.3,
    max_value=0.7,
    value=0.5,
    step=0.05,
    help="Element spacing in wavelengths"
)

dy_lambda = st.sidebar.slider(
    "Spacing Y (λ)",
    min_value=0.3,
    max_value=0.7,
    value=0.5,
    step=0.05,
    help="Element spacing in wavelengths"
)

st.sidebar.header("RF Chain")

tx_power_w = st.sidebar.slider(
    "TX Power per Element (W)",
    min_value=0.1,
    max_value=5.0,
    value=1.0,
    step=0.1,
    help="Transmit power per element in Watts"
)

pa_efficiency = st.sidebar.slider(
    "PA Efficiency",
    min_value=0.1,
    max_value=0.7,
    value=0.3,
    step=0.05,
    help="Power amplifier efficiency (0-1)"
)

noise_figure_db = st.sidebar.slider(
    "Noise Figure (dB)",
    min_value=1.0,
    max_value=10.0,
    value=3.0,
    step=0.5,
    help="Receiver noise figure"
)

st.sidebar.header("Cost")

cost_per_elem = st.sidebar.number_input(
    "Cost per Element ($)",
    min_value=10,
    max_value=1000,
    value=100,
    step=10,
    help="Recurring cost per element in USD"
)

st.sidebar.header("Scenario")

freq_ghz = st.sidebar.slider(
    "Frequency (GHz)",
    min_value=1.0,
    max_value=40.0,
    value=10.0,
    step=0.5,
    help="Operating frequency"
)

range_km = st.sidebar.slider(
    "Range (km)",
    min_value=1.0,
    max_value=500.0,
    value=100.0,
    step=5.0,
    help="Link distance"
)

bandwidth_mhz = st.sidebar.slider(
    "Bandwidth (MHz)",
    min_value=1.0,
    max_value=100.0,
    value=10.0,
    step=1.0,
    help="Signal bandwidth"
)

required_snr_db = st.sidebar.slider(
    "Required SNR (dB)",
    min_value=0.0,
    max_value=30.0,
    value=10.0,
    step=1.0,
    help="SNR required for demodulation"
)

# Calculate derived values
n_elements = nx * ny
freq_hz = freq_ghz * 1e9
range_m = range_km * 1e3
bandwidth_hz = bandwidth_mhz * 1e6

# Main content area
if PACKAGE_AVAILABLE:
    # Use the actual package
    arch = Architecture(
        array=ArrayConfig(
            nx=nx, ny=ny,
            dx_lambda=dx_lambda,
            dy_lambda=dy_lambda,
            enforce_subarray_constraint=False,
        ),
        rf=RFChainConfig(
            tx_power_w_per_elem=tx_power_w,
            pa_efficiency=pa_efficiency,
            noise_figure_db=noise_figure_db,
        ),
        cost=CostConfig(cost_per_elem_usd=cost_per_elem),
    )

    scenario = CommsLinkScenario(
        freq_hz=freq_hz,
        bandwidth_hz=bandwidth_hz,
        range_m=range_m,
        required_snr_db=required_snr_db,
    )

    # Define requirements
    requirements = RequirementSet()
    requirements.add(Requirement(
        id="REQ-SNR",
        name="SNR Margin",
        metric_key="link_margin_db",
        op=">=",
        value=0.0,
        severity="must",
    ))
    requirements.add(Requirement(
        id="REQ-COST",
        name="System Cost",
        metric_key="cost_usd",
        op="<=",
        value=100000.0,
        severity="should",
    ))

    # Evaluate
    metrics = evaluate_case(arch, scenario, requirements)

else:
    # Demo mode with simplified calculations
    c = 3e8  # Speed of light

    # Approximate calculations
    wavelength_m = c / freq_hz
    aperture_lambda_sq = nx * dx_lambda * ny * dy_lambda
    g_peak_linear = 4 * np.pi * aperture_lambda_sq
    g_peak_db = 10 * np.log10(g_peak_linear)

    # Beamwidth approximation
    beamwidth_az = 0.886 * np.degrees(wavelength_m / (nx * dx_lambda * wavelength_m))
    beamwidth_el = 0.886 * np.degrees(wavelength_m / (ny * dy_lambda * wavelength_m))

    # Total TX power
    total_tx_power_w = tx_power_w * n_elements
    total_tx_power_dbw = 10 * np.log10(total_tx_power_w)

    # EIRP
    eirp_dbw = total_tx_power_dbw + g_peak_db

    # Free space path loss
    fspl_db = 20 * np.log10(range_m) + 20 * np.log10(freq_hz) + 20 * np.log10(4 * np.pi / c)

    # Noise power (kTB)
    k_b = 1.38e-23
    noise_temp = 290
    noise_power_w = k_b * noise_temp * bandwidth_hz
    noise_power_dbw = 10 * np.log10(noise_power_w) + noise_figure_db

    # SNR at receiver (assume isotropic RX antenna for simplicity)
    rx_power_dbw = eirp_dbw - fspl_db
    snr_db = rx_power_dbw - noise_power_dbw

    # Link margin
    link_margin_db = snr_db - required_snr_db

    # Power and cost
    prime_power_w = total_tx_power_w / pa_efficiency
    cost_usd = cost_per_elem * n_elements

    # Build metrics dict
    metrics = {
        "g_peak_db": g_peak_db,
        "beamwidth_az_deg": beamwidth_az,
        "beamwidth_el_deg": beamwidth_el,
        "sll_db": -13.0,  # Approximate for uniform
        "eirp_dbw": eirp_dbw,
        "path_loss_db": fspl_db,
        "snr_rx_db": snr_db,
        "link_margin_db": link_margin_db,
        "prime_power_w": prime_power_w,
        "cost_usd": cost_usd,
    }

# Display results
st.header("Results")

# Quick summary metrics
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "Total Elements",
        f"{n_elements:,}",
        help="nx × ny"
    )

with col2:
    st.metric(
        "Peak Gain",
        f"{metrics.get('g_peak_db', 0):.1f} dB",
        help="Antenna peak gain"
    )

with col3:
    st.metric(
        "EIRP",
        f"{metrics.get('eirp_dbw', 0):.1f} dBW",
        help="Effective Isotropic Radiated Power"
    )

link_margin = metrics.get('link_margin_db', 0)
with col4:
    st.metric(
        "Link Margin",
        f"{link_margin:.1f} dB",
        delta="PASS" if link_margin >= 0 else "FAIL",
        delta_color="normal" if link_margin >= 0 else "inverse",
        help="SNR margin above required"
    )

st.divider()

# Detailed metrics in tabs
tab1, tab2, tab3 = st.tabs(["📡 Antenna", "📶 Link Budget", "⚡ SWaP-C"])

with tab1:
    st.subheader("Antenna Metrics")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Configuration**")
        st.write(f"- Array Size: {nx} × {ny} = {n_elements} elements")
        st.write(f"- Element Spacing: {dx_lambda}λ × {dy_lambda}λ")
        st.write(f"- Frequency: {freq_ghz:.1f} GHz")
        st.write(f"- Wavelength: {3e8/freq_hz*1000:.1f} mm")

    with col2:
        st.markdown("**Performance**")
        st.write(f"- Peak Gain: {metrics.get('g_peak_db', 0):.1f} dB")
        st.write(f"- Beamwidth (Az): {metrics.get('beamwidth_az_deg', 0):.2f}°")
        st.write(f"- Beamwidth (El): {metrics.get('beamwidth_el_deg', 0):.2f}°")
        st.write(f"- Sidelobe Level: {metrics.get('sll_db', -13):.1f} dB")

with tab2:
    st.subheader("Link Budget")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Transmit**")
        st.write(f"- TX Power/Element: {tx_power_w:.1f} W")
        st.write(f"- Total TX Power: {tx_power_w * n_elements:.1f} W ({10*np.log10(tx_power_w * n_elements):.1f} dBW)")
        st.write(f"- Antenna Gain: {metrics.get('g_peak_db', 0):.1f} dB")
        st.write(f"- **EIRP: {metrics.get('eirp_dbw', 0):.1f} dBW**")

    with col2:
        st.markdown("**Receive**")
        st.write(f"- Path Loss: {metrics.get('path_loss_db', 0):.1f} dB")
        st.write(f"- Range: {range_km:.0f} km")
        st.write(f"- Bandwidth: {bandwidth_mhz:.0f} MHz")

    st.divider()

    st.markdown("**Link Performance**")
    col1, col2, col3 = st.columns(3)

    with col1:
        snr = metrics.get('snr_rx_db', 0)
        st.metric("Received SNR", f"{snr:.1f} dB")

    with col2:
        st.metric("Required SNR", f"{required_snr_db:.1f} dB")

    with col3:
        margin = metrics.get('link_margin_db', 0)
        color = "green" if margin >= 0 else "red"
        status = "✅ PASS" if margin >= 0 else "❌ FAIL"
        st.metric("Link Margin", f"{margin:.1f} dB", status)

with tab3:
    st.subheader("Size, Weight, Power, and Cost")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Power**")
        prime_power = metrics.get('prime_power_w', tx_power_w * n_elements / pa_efficiency)
        st.write(f"- RF Power: {tx_power_w * n_elements:.1f} W")
        st.write(f"- PA Efficiency: {pa_efficiency*100:.0f}%")
        st.write(f"- **Prime Power: {prime_power:.1f} W**")

    with col2:
        st.markdown("**Cost**")
        total_cost = metrics.get('cost_usd', cost_per_elem * n_elements)
        st.write(f"- Cost per Element: ${cost_per_elem:,}")
        st.write(f"- Number of Elements: {n_elements:,}")
        st.write(f"- **Total Cost: ${total_cost:,.0f}**")

    # Cost vs elements budget indicator
    st.divider()
    cost_limit = 100000
    cost_pct = min(total_cost / cost_limit * 100, 100)
    st.progress(cost_pct / 100, f"Cost Budget: ${total_cost:,.0f} / ${cost_limit:,} ({cost_pct:.0f}%)")

# Export configuration
st.divider()
with st.expander("📋 Configuration Export (YAML)"):
    yaml_config = f"""# Phased Array Configuration
architecture:
  array:
    nx: {nx}
    ny: {ny}
    dx_lambda: {dx_lambda}
    dy_lambda: {dy_lambda}
  rf:
    tx_power_w_per_elem: {tx_power_w}
    pa_efficiency: {pa_efficiency}
    noise_figure_db: {noise_figure_db}
  cost:
    cost_per_elem_usd: {cost_per_elem}

scenario:
  type: comms
  freq_hz: {freq_hz:.0f}
  bandwidth_hz: {bandwidth_hz:.0f}
  range_m: {range_m:.0f}
  required_snr_db: {required_snr_db}
"""
    st.code(yaml_config, language="yaml")

    st.download_button(
        label="Download Configuration",
        data=yaml_config,
        file_name="phased_array_config.yaml",
        mime="text/yaml"
    )
