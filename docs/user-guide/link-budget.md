# Link Budget Modeling

phased-array-systems provides comprehensive communications link budget analysis for point-to-point and satellite links.

## Overview

The link budget model calculates:

- **EIRP**: Effective Isotropic Radiated Power
- **Path Loss**: Free space and additional losses
- **Received Power**: Signal power at receiver
- **SNR**: Signal-to-noise ratio
- **Link Margin**: Margin above required SNR

## Link Budget Equation

The fundamental link budget equation:

$$
P_{rx} = EIRP - L_{path} + G_{rx}
$$

Where:

- $P_{rx}$ = Received power (dBW)
- $EIRP$ = Effective Isotropic Radiated Power (dBW)
- $L_{path}$ = Total path loss (dB)
- $G_{rx}$ = Receive antenna gain (dBi)

### EIRP Calculation

$$
EIRP = P_{tx} + G_{tx} - L_{tx}
$$

Where:

- $P_{tx}$ = Total transmit power (dBW)
- $G_{tx}$ = Transmit antenna gain (dBi)
- $L_{tx}$ = Transmit losses (feed + system)

### SNR Calculation

$$
SNR = P_{rx} - N
$$

$$
N = 10 \log_{10}(kTB) + NF
$$

Where:

- $k$ = Boltzmann constant (1.38×10⁻²³ J/K)
- $T$ = Noise temperature (K)
- $B$ = Bandwidth (Hz)
- $NF$ = Noise figure (dB)

## Basic Usage

### Single Evaluation

```python
from phased_array_systems.architecture import Architecture, ArrayConfig, RFChainConfig
from phased_array_systems.scenarios import CommsLinkScenario
from phased_array_systems.evaluate import evaluate_case

# Define architecture
arch = Architecture(
    array=ArrayConfig(nx=8, ny=8, dx_lambda=0.5, dy_lambda=0.5),
    rf=RFChainConfig(
        tx_power_w_per_elem=1.0,
        pa_efficiency=0.3,
        noise_figure_db=3.0,
        feed_loss_db=1.0,
    ),
)

# Define scenario
scenario = CommsLinkScenario(
    freq_hz=10e9,
    bandwidth_hz=10e6,
    range_m=100e3,
    required_snr_db=10.0,
    rx_antenna_gain_db=0.0,  # Isotropic receiver
    rx_noise_temp_k=290.0,
)

# Evaluate
metrics = evaluate_case(arch, scenario)

# Results
print(f"TX Power Total: {metrics['tx_power_total_dbw']:.1f} dBW")
print(f"TX Antenna Gain: {metrics['g_tx_db']:.1f} dB")
print(f"EIRP: {metrics['eirp_dbw']:.1f} dBW")
print(f"Path Loss: {metrics['path_loss_db']:.1f} dB")
print(f"RX Power: {metrics['rx_power_dbw']:.1f} dBW")
print(f"Noise Power: {metrics['noise_power_dbw']:.1f} dBW")
print(f"SNR: {metrics['snr_rx_db']:.1f} dB")
print(f"Link Margin: {metrics['link_margin_db']:.1f} dB")
```

### Output Metrics

| Metric | Units | Description |
|--------|-------|-------------|
| `tx_power_total_dbw` | dBW | Total TX power |
| `tx_power_per_elem_dbw` | dBW | TX power per element |
| `g_tx_db` | dB | Transmit antenna gain |
| `eirp_dbw` | dBW | Effective isotropic radiated power |
| `path_loss_db` | dB | Total path loss |
| `fspl_db` | dB | Free space path loss only |
| `g_rx_db` | dB | Receive antenna gain |
| `rx_power_dbw` | dBW | Received signal power |
| `noise_power_dbw` | dBW | Receiver noise power |
| `snr_rx_db` | dB | Received SNR |
| `link_margin_db` | dB | Margin above required SNR |
| `required_snr_db` | dB | Required SNR (from scenario) |

## Direct Link Budget Function

For quick calculations without full architecture/scenario objects:

```python
from phased_array_systems.models.comms.link_budget import compute_link_margin

result = compute_link_margin(
    eirp_dbw=50.0,
    path_loss_db=160.0,
    g_rx_db=30.0,
    noise_temp_k=290.0,
    bandwidth_hz=10e6,
    noise_figure_db=3.0,
    required_snr_db=10.0,
)

print(f"RX Power: {result['rx_power_dbw']:.1f} dBW")
print(f"Noise Power: {result['noise_power_dbw']:.1f} dBW")
print(f"SNR: {result['snr_db']:.1f} dB")
print(f"Margin: {result['margin_db']:.1f} dB")
```

## Path Loss Models

### Free Space Path Loss (FSPL)

The default model:

$$
L_{FSPL} = 20 \log_{10}\left(\frac{4\pi d f}{c}\right)
$$

```python
from phased_array_systems.models.comms.propagation import compute_fspl

# Calculate FSPL
loss_db = compute_fspl(freq_hz=10e9, range_m=100e3)
print(f"FSPL: {loss_db:.1f} dB")  # ~152.4 dB
```

### Additional Losses

The scenario can include extra losses:

```python
scenario = CommsLinkScenario(
    ...,
    atmospheric_loss_db=0.5,   # Atmospheric absorption
    rain_loss_db=3.0,          # Rain fade
    polarization_loss_db=0.3,  # Polarization mismatch
)

# Total path loss = FSPL + atmospheric + rain + polarization
```

## Antenna Gain

### From Context

If antenna metrics are pre-computed, they're used from context:

```python
# With pre-computed antenna gain
context = {
    "g_peak_db": 28.0,
    "scan_loss_db": 2.5,
}

# Link model uses these instead of approximation
```

### Approximation

Without pre-computed values, gain is approximated:

$$
G \approx 4\pi \cdot n_x d_x \cdot n_y d_y
$$

Where $d_x, d_y$ are spacings in wavelengths.

## Scan Loss

When the beam is scanned off boresight, gain is reduced:

```python
scenario = CommsLinkScenario(
    ...,
    scan_angle_deg=30.0,  # 30° off boresight
)
```

Scan loss is approximated or taken from antenna model context.

## Example: Satellite Link

```python
# GEO satellite downlink
arch = Architecture(
    array=ArrayConfig(nx=32, ny=32, dx_lambda=0.5, dy_lambda=0.5),
    rf=RFChainConfig(
        tx_power_w_per_elem=5.0,
        pa_efficiency=0.25,
        feed_loss_db=2.0,
    ),
)

scenario = CommsLinkScenario(
    freq_hz=12e9,              # Ku-band
    bandwidth_hz=36e6,         # Transponder BW
    range_m=36000e3,           # GEO distance
    required_snr_db=8.0,       # QPSK
    rx_antenna_gain_db=45.0,   # Large ground station
    rx_noise_temp_k=80.0,      # Cooled LNA
    atmospheric_loss_db=0.3,
    rain_loss_db=5.0,          # Heavy rain margin
)

metrics = evaluate_case(arch, scenario)
print(f"Link Margin: {metrics['link_margin_db']:.1f} dB")
```

## Example: Point-to-Point Link

```python
# Terrestrial backhaul
arch = Architecture(
    array=ArrayConfig(nx=8, ny=8, dx_lambda=0.5, dy_lambda=0.5),
    rf=RFChainConfig(tx_power_w_per_elem=0.5),
)

scenario = CommsLinkScenario(
    freq_hz=26e9,              # 26 GHz
    bandwidth_hz=100e6,        # 100 MHz
    range_m=5e3,               # 5 km
    required_snr_db=18.0,      # 64-QAM
    rx_antenna_gain_db=35.0,   # Matching antenna
    rx_noise_temp_k=500.0,
    atmospheric_loss_db=1.0,   # Higher at 26 GHz
    rain_loss_db=10.0,         # Significant at 26 GHz
)

metrics = evaluate_case(arch, scenario)
```

## Using CommsLinkModel Directly

For advanced use, access the model directly:

```python
from phased_array_systems.models.comms.link_budget import CommsLinkModel

model = CommsLinkModel()

# Evaluate with context (e.g., pre-computed antenna metrics)
context = {
    "g_peak_db": 30.0,
    "scan_loss_db": 1.5,
}

metrics = model.evaluate(arch, scenario, context)
```

## Link Budget Trade Studies

Combine with DOE for systematic analysis:

```python
from phased_array_systems.trades import DesignSpace, generate_doe, BatchRunner

# Vary array size and power
space = (
    DesignSpace()
    .add_variable("array.nx", type="categorical", values=[4, 8, 16])
    .add_variable("array.ny", type="categorical", values=[4, 8, 16])
    .add_variable("rf.tx_power_w_per_elem", type="float", low=0.5, high=3.0)
    # Fixed parameters...
)

doe = generate_doe(space, method="lhs", n_samples=100, seed=42)
runner = BatchRunner(scenario)
results = runner.run(doe)

# Analyze link margin vs cost trade-off
print(f"Margin range: {results['link_margin_db'].min():.1f} to {results['link_margin_db'].max():.1f} dB")
```

## Validation Tips

### Check Intermediate Values

```python
# Validate each stage of link budget
print(f"1. TX Power: {metrics['tx_power_total_dbw']:.2f} dBW")
print(f"2. + Gain: {metrics['g_tx_db']:.2f} dB")
print(f"3. - Feed Loss: {arch.rf.feed_loss_db:.2f} dB")
print(f"4. = EIRP: {metrics['eirp_dbw']:.2f} dBW")
print(f"5. - Path Loss: {metrics['path_loss_db']:.2f} dB")
print(f"6. + RX Gain: {metrics['g_rx_db']:.2f} dB")
print(f"7. = RX Power: {metrics['rx_power_dbw']:.2f} dBW")
```

### Sanity Checks

```python
# EIRP should be reasonable
assert 20 < metrics['eirp_dbw'] < 80, "EIRP out of typical range"

# Path loss increases with range and frequency
# At 10 GHz, 100 km: ~152 dB
assert 100 < metrics['path_loss_db'] < 200, "Path loss unusual"

# Margin should match expectations
expected_margin = metrics['snr_rx_db'] - scenario.required_snr_db
assert abs(metrics['link_margin_db'] - expected_margin) < 0.01
```

## See Also

- [Theory: Link Budget Equations](../theory/link-budget-equations.md) - Detailed derivations
- [Scenarios](scenarios.md) - Configure link scenarios
- [Trade Studies](trade-studies.md) - Systematic link analysis
- [API Reference](../api/models/comms.md) - Full API documentation
