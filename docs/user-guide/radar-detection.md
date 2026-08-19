# Radar Detection Modeling

phased-array-systems provides radar detection performance analysis based on the radar range equation and detection theory.

## Overview

The radar detection model calculates:

- **Single-pulse SNR**: Signal-to-noise ratio for one pulse
- **Integrated SNR**: SNR after pulse integration
- **Required SNR**: SNR needed for detection
- **Detection range**: Maximum range for given Pd/Pfa
- **SNR margin**: Margin above detection threshold

## Radar Range Equation

The fundamental radar equation:

$$
SNR = \frac{P_t G^2 \lambda^2 \sigma}{(4\pi)^3 R^4 k T_s B_n L_s}
$$

Where:

- $P_t$ = Peak transmit power (W)
- $G$ = Antenna gain (linear)
- $\lambda$ = Wavelength (m)
- $\sigma$ = Target radar cross section (m²)
- $R$ = Target range (m)
- $k$ = Boltzmann constant
- $T_s$ = System noise temperature (K)
- $B_n$ = Noise bandwidth (Hz)
- $L_s$ = System losses (linear)

## Basic Usage

```python
from phased_array_systems.architecture import Architecture, ArrayConfig, RFChainConfig
from phased_array_systems.scenarios import RadarDetectionScenario
from phased_array_systems.evaluate import evaluate_case

# Define architecture
arch = Architecture(
    array=ArrayConfig(nx=64, ny=64, dx_lambda=0.5, dy_lambda=0.5),
    rf=RFChainConfig(
        tx_power_w_per_elem=10.0,
        pa_efficiency=0.25,
        noise_figure_db=4.0,
    ),
)

# Define scenario
scenario = RadarDetectionScenario(
    freq_hz=10e9,              # X-band
    bandwidth_hz=100e3,        # matched to a 10 us pulse (B ~ 1/tau)
    range_m=100e3,             # 100 km
    target_rcs_dbsm=0.0,       # 1 m^2 target, expressed in dBsm
    pd_required=0.9,           # 90% detection probability
    pfa=1e-6,                  # 1e-6 false alarm rate
    prf_hz=1000,               # 1 kHz PRF
    n_pulses=10,               # Integrate 10 pulses
    integration_type="coherent",
    swerling=1,
)

# Evaluate
metrics = evaluate_case(arch, scenario)

print(f"Single-Pulse SNR: {metrics['snr_single_pulse_db']:.1f} dB")
print(f"Integrated SNR: {metrics['snr_integrated_db']:.1f} dB")
print(f"Required SNR: {metrics['snr_required_db']:.1f} dB")
print(f"SNR Margin: {metrics['snr_margin_db']:.1f} dB")
```

```
Single-Pulse SNR: 13.8 dB
Integrated SNR: 23.8 dB
Required SNR: 21.1 dB
SNR Margin: 2.7 dB
```

Target cross-section is given in dBsm, so a 1 m^2 target is `0.0` and a 2 m^2
target is `3.0`. There is no pulse-width field: set `bandwidth_hz` directly,
which for an uncompressed pulse is about `1/tau`.

### Output Metrics

| Metric | Units | Description |
|--------|-------|-------------|
| `snr_single_pulse_db` | dB | SNR for one pulse |
| `snr_integrated_db` | dB | SNR after integration |
| `snr_required_db` | dB | Required SNR for Pd/Pfa |
| `snr_margin_db` | dB | Margin above required |
| `detection_range_m` | m | Max range for requirements |

## Detection Probability

### Required SNR Calculation

The required SNR depends on:

- Desired detection probability (Pd)
- False alarm probability (Pfa)
- Target fluctuation model (Swerling)

For Swerling 0 (non-fluctuating):

$$
SNR_{req} = \frac{[\text{erfc}^{-1}(2P_{fa}) - \text{erfc}^{-1}(2P_d)]^2}{2}
$$

### Swerling Target Models

| Model | Description | Typical Targets |
|-------|-------------|-----------------|
| 0 | Non-fluctuating | Sphere, corner reflector |
| 1 | Slow fluctuation, Rayleigh | Aircraft (scan-to-scan) |
| 2 | Fast fluctuation, Rayleigh | Aircraft (pulse-to-pulse) |
| 3 | Slow, one dominant + many | Ship, complex target |
| 4 | Fast, one dominant + many | Propeller aircraft |

```python
# Different Swerling models
scenario_sw0 = RadarDetectionScenario(..., swerling=0)  # Steady target
scenario_sw1 = RadarDetectionScenario(..., swerling=1)  # Typical aircraft
scenario_sw3 = RadarDetectionScenario(..., swerling=3)  # Ship
```

## Pulse Integration

### Coherent Integration

Maintains phase information; provides linear SNR improvement:

$$
SNR_{integrated} = N \cdot SNR_{single}
$$

```python
scenario = RadarDetectionScenario(
    ...,
    n_pulses=16,
    integration_type="coherent",
)
# SNR improves by 10*log10(16) = 12 dB
```

### Non-Coherent Integration

Magnitude-only; provides approximately √N improvement:

$$
SNR_{integrated} \approx \sqrt{N} \cdot SNR_{single}
$$

```python
scenario = RadarDetectionScenario(
    ...,
    n_pulses=16,
    integration_type="noncoherent",
)
# SNR improves by approximately 10*log10(√16) = 6 dB
```

## Using the Radar Model Directly

For advanced use cases:

```python
from phased_array_systems.models.radar.equation import RadarModel
from phased_array_systems.models.radar.detection import compute_snr_for_pd

# Calculate required SNR
snr_req = compute_snr_for_pd(
    pd=0.9,
    pfa=1e-6,
    swerling=1,
    n_pulses=10,
)
print(f"Required SNR: {snr_req:.1f} dB")   # 13.5 dB

# Use the radar model directly. It reads antenna gain and beamwidths from
# `context`; an empty context falls back to defaults, so in normal use pass
# the antenna model's metrics through as `evaluate_case` does.
model = RadarModel()
metrics = model.evaluate(arch, scenario, context={})
```

## Detection Range Calculation

Solve for range at which SNR equals required SNR:

Every evaluated case already carries it, scaled from the SNR margin by the
fourth-power range law:

```python
metrics = evaluate_case(arch, scenario)
print(f"Detection range: {metrics['detection_range_m']/1000:.1f} km")
```

To solve from radar parameters without building an `Architecture`:

```python
from phased_array_systems.models.radar.equation import compute_detection_range

max_range_m = compute_detection_range(
    peak_power_w=1000.0,
    g_ant_db=35.0,
    freq_hz=10e9,
    rcs_dbsm=0.0,
    noise_temp_k=290.0,
    bandwidth_hz=1e6,
    noise_figure_db=4.0,
    system_loss_db=3.0,
    snr_required_db=13.0,
)
print(f"Detection range: {max_range_m/1000:.1f} km")   # 10.3 km
```

## Example: Search Radar

```python
# Long-range search radar
arch = Architecture(
    array=ArrayConfig(nx=32, ny=32, dx_lambda=0.5, dy_lambda=0.5),
    rf=RFChainConfig(
        tx_power_w_per_elem=20.0,  # High power
        pa_efficiency=0.20,
        noise_figure_db=3.5,
    ),
)

scenario = RadarDetectionScenario(
    freq_hz=3e9,               # S-band (longer range)
    bandwidth_hz=20e3,         # matched to a 50 us pulse
    range_m=200e3,             # 200 km search
    target_rcs_dbsm=3.0,       # 2 m^2, medium aircraft
    pd_required=0.8,           # 80% Pd
    pfa=1e-6,
    prf_hz=300,
    n_pulses=20,               # Long integration
    integration_type="noncoherent",
    swerling=1,
)

metrics = evaluate_case(arch, scenario)
print(f"SNR Margin at 200 km: {metrics['snr_margin_db']:.1f} dB")
print(f"Detection range: {metrics['detection_range_m']/1000:.1f} km")
```

```
SNR Margin at 200 km: -0.5 dB
Detection range: 194.3 km
```

Half a dB short at the stated range, which the detection range restates as
194 km rather than 200 km.

## Example: Tracking Radar

Setting `target_accel_max_ms2` turns on the track-accuracy metrics: the
measurement errors that the detection SNR buys, and the steady-state filter
performance that follows from them and the revisit rate. See
[Track Accuracy](../theory/track-accuracy.md) for the equations.

```python
from phased_array_systems import Architecture, ArrayConfig, RFChainConfig, evaluate_case
from phased_array_systems.scenarios import RadarDetectionScenario

arch = Architecture(
    array=ArrayConfig(nx=64, ny=64, dx_lambda=0.5, dy_lambda=0.5),
    rf=RFChainConfig(
        tx_power_w_per_elem=10.0,
        pa_efficiency=0.30,
        noise_figure_db=3.0,
    ),
)

scenario = RadarDetectionScenario(
    freq_hz=10e9,                 # X-band
    bandwidth_hz=10e6,            # 15 m range resolution
    range_m=50e3,
    target_rcs_dbsm=0.0,
    pd_required=0.99,             # high Pd for track maintenance
    pfa=1e-4,                     # relaxed Pfa on a confirmed target
    n_pulses=64,
    prf_hz=5000,
    integration_type="coherent",
    swerling=0,                   # stabilized target
    track_revisit_s=1.0,          # track update rate
    target_accel_max_ms2=40.0,    # ~4 g maneuver
)

metrics = evaluate_case(arch, scenario)

print(f"SNR:            {metrics['snr_integrated_db']:.1f} dB")
print(f"sigma_range:    {metrics['sigma_range_m']:.2f} m")
print(f"sigma_crossrng: {metrics['sigma_crossrange_az_m']:.1f} m")
print(f"track position: {metrics['track_pos_rms_crossrange_m']:.1f} m")
```

```
SNR:            25.0 dB
sigma_range:    0.60 m
sigma_crossrng: 34.2 m
track position: 29.7 m
```

Cross-range error is 57x the range error here, and only a larger aperture
reduces it. `monopulse_snr_ok` reports whether the case sits above the 13 dB
floor where the angle-accuracy relation is valid.

## Radar Trade Studies

Combine with DOE for systematic analysis:

```python
from phased_array_systems.trades import DesignSpace, generate_doe, BatchRunner
from phased_array_systems.requirements import Requirement, RequirementSet

# Define requirements
requirements = RequirementSet(requirements=[
    Requirement("DET-001", "Positive SNR Margin", "snr_margin_db", ">=", 0.0, severity="must"),
    Requirement("COST-001", "Max Cost", "cost_usd", "<=", 1000000.0, severity="must"),
])

# Define design space
space = (
    DesignSpace()
    .add_variable("array.nx", type="categorical", values=[8, 16, 32])
    .add_variable("array.ny", type="categorical", values=[8, 16, 32])
    .add_variable("rf.tx_power_w_per_elem", type="float", low=5.0, high=20.0)
    # ... other parameters
)

# Run trade study
doe = generate_doe(space, method="lhs", n_samples=100, seed=42)
runner = BatchRunner(scenario, requirements)
results = runner.run(doe)

# Find Pareto-optimal designs
from phased_array_systems.trades import filter_feasible, extract_pareto

feasible = filter_feasible(results, requirements)
pareto = extract_pareto(feasible, [
    ("cost_usd", "minimize"),
    ("snr_margin_db", "maximize"),
])
```

## Sensitivity Analysis

Analyze how parameters affect detection:

```python
import numpy as np
import pandas as pd

# Vary range
ranges = np.linspace(50e3, 200e3, 20)
results = []

for range_m in ranges:
    scenario.range_m = range_m
    metrics = evaluate_case(arch, scenario)
    results.append({
        "range_km": range_m / 1000,
        "snr_margin_db": metrics["snr_margin_db"],
    })

df = pd.DataFrame(results)
print(df)
```

## Key Considerations

### Power-Aperture Product

Radar performance scales with power × aperture:

$$
PA = P_t \cdot A_{eff} = P_t \cdot \frac{G \lambda^2}{4\pi}
$$

Trade off between:

- More power (higher cost, heat)
- Larger aperture (more elements, higher cost)

### Frequency Selection

| Lower Frequency | Higher Frequency |
|-----------------|------------------|
| Longer range | Better resolution |
| Larger aperture for same gain | Smaller components |
| Better rain penetration | More atmospheric loss |

### Integration Time

More pulses = better SNR, but:

- Longer dwell time per beam position
- Target motion limits coherent integration
- Faster scan requires fewer pulses

## See Also

- [Theory: Radar Equation](../theory/radar-equation.md) - Detailed derivations
- [Scenarios](scenarios.md) - Configure radar scenarios
- [Trade Studies](trade-studies.md) - Systematic radar analysis
- [API Reference](../api/models/radar.md) - Full API documentation
