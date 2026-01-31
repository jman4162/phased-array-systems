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
    array=ArrayConfig(nx=16, ny=16, dx_lambda=0.5, dy_lambda=0.5),
    rf=RFChainConfig(
        tx_power_w_per_elem=10.0,
        pa_efficiency=0.25,
        noise_figure_db=4.0,
    ),
)

# Define scenario
scenario = RadarDetectionScenario(
    freq_hz=10e9,              # X-band
    target_rcs_m2=1.0,         # 1 m² target
    range_m=100e3,             # 100 km
    required_pd=0.9,           # 90% detection probability
    pfa=1e-6,                  # 10⁻⁶ false alarm rate
    pulse_width_s=10e-6,       # 10 μs pulse
    prf_hz=1000,               # 1 kHz PRF
    n_pulses=10,               # Integrate 10 pulses
    integration_type="coherent",
    swerling_model=1,
)

# Evaluate
metrics = evaluate_case(arch, scenario)

print(f"Single-Pulse SNR: {metrics['snr_single_pulse_db']:.1f} dB")
print(f"Integrated SNR: {metrics['snr_integrated_db']:.1f} dB")
print(f"Required SNR: {metrics['snr_required_db']:.1f} dB")
print(f"SNR Margin: {metrics['snr_margin_db']:.1f} dB")
```

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
scenario_sw0 = RadarDetectionScenario(..., swerling_model=0)  # Steady target
scenario_sw1 = RadarDetectionScenario(..., swerling_model=1)  # Typical aircraft
scenario_sw3 = RadarDetectionScenario(..., swerling_model=3)  # Ship
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
from phased_array_systems.models.radar.equation import RadarEquationModel
from phased_array_systems.models.radar.detection import compute_required_snr

# Calculate required SNR
snr_req = compute_required_snr(
    pd=0.9,
    pfa=1e-6,
    swerling_model=1,
    n_pulses=10,
)
print(f"Required SNR: {snr_req:.1f} dB")

# Use radar equation model directly
model = RadarEquationModel()
metrics = model.evaluate(arch, scenario, context={})
```

## Detection Range Calculation

Solve for range at which SNR equals required SNR:

```python
from phased_array_systems.models.radar.detection import compute_detection_range

max_range = compute_detection_range(
    snr_single_db=15.0,
    snr_required_db=13.0,
    current_range_m=100e3,
)
print(f"Detection range: {max_range/1000:.1f} km")
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
    target_rcs_m2=2.0,         # Medium aircraft
    range_m=200e3,             # 200 km search
    required_pd=0.8,           # 80% Pd
    pfa=1e-6,
    pulse_width_s=50e-6,       # Long pulse
    prf_hz=300,
    n_pulses=20,               # Long integration
    integration_type="noncoherent",
    swerling_model=1,
)

metrics = evaluate_case(arch, scenario)
print(f"SNR Margin at 200 km: {metrics['snr_margin_db']:.1f} dB")
```

## Example: Tracking Radar

```python
# Precision tracking radar
arch = Architecture(
    array=ArrayConfig(nx=16, ny=16, dx_lambda=0.5, dy_lambda=0.5),
    rf=RFChainConfig(
        tx_power_w_per_elem=5.0,
        pa_efficiency=0.30,
        noise_figure_db=3.0,
    ),
)

scenario = RadarDetectionScenario(
    freq_hz=10e9,              # X-band (precision)
    target_rcs_m2=0.5,         # Smaller target
    range_m=50e3,              # 50 km track
    required_pd=0.99,          # High Pd for tracking
    pfa=1e-4,                  # Relaxed Pfa (verified target)
    pulse_width_s=5e-6,        # Short pulse (range resolution)
    prf_hz=5000,               # High PRF
    n_pulses=100,              # Many pulses
    integration_type="coherent",
    swerling_model=0,          # Stabilized target
)

metrics = evaluate_case(arch, scenario)
```

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
