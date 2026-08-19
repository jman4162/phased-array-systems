# Radar Models API

Radar equation and detection probability calculations.

## Overview

```python
from phased_array_systems.models.radar import (
    RadarModel,
    compute_detection_threshold,
    compute_pd_from_snr,
    compute_snr_for_pd,
    albersheim_snr,
    coherent_integration_gain,
    noncoherent_integration_gain,
    integration_loss,
)
```

## Classes

::: phased_array_systems.models.radar.equation.RadarModel
    options:
      show_root_heading: true
      members_order: source

## Functions

::: phased_array_systems.models.radar.detection.compute_snr_for_pd
    options:
      show_root_heading: true

::: phased_array_systems.models.radar.detection.compute_pd_from_snr
    options:
      show_root_heading: true

::: phased_array_systems.models.radar.detection.albersheim_snr
    options:
      show_root_heading: true

::: phased_array_systems.models.radar.integration.coherent_integration_gain
    options:
      show_root_heading: true

::: phased_array_systems.models.radar.integration.noncoherent_integration_gain
    options:
      show_root_heading: true

## Output Metrics

| Metric | Units | Description |
|--------|-------|-------------|
| `snr_single_pulse_db` | dB | Single-pulse SNR |
| `snr_integrated_db` | dB | SNR after integration |
| `snr_required_db` | dB | Required SNR for Pd/Pfa |
| `snr_margin_db` | dB | Margin above required |
| `detection_range_m` | m | Maximum detection range |
| `integration_gain_db` | dB | Gain from pulse integration |

## Usage Examples

### Using RadarModel

```python
from phased_array_systems.models.radar import RadarModel
from phased_array_systems.scenarios import RadarDetectionScenario

scenario = RadarDetectionScenario(
    freq_hz=10e9,
    bandwidth_hz=100e3,
    range_m=100e3,
    target_rcs_dbsm=0.0,
    pd_required=0.9,
    pfa=1e-6,
    prf_hz=1000,
    n_pulses=10,
    integration_type="coherent",
    swerling=1,
)

model = RadarModel()
metrics = model.evaluate(arch, scenario, context={})

print(f"Single-Pulse SNR: {metrics['snr_single_pulse_db']:.1f} dB")
print(f"Integrated SNR: {metrics['snr_integrated_db']:.1f} dB")
print(f"SNR Margin: {metrics['snr_margin_db']:.1f} dB")
```

### Computing Required SNR

```python
from phased_array_systems.models.radar import compute_snr_for_pd

snr_req = compute_snr_for_pd(
    pd=0.9,
    pfa=1e-6,
    swerling=1,
)
print(f"Required SNR: {snr_req:.1f} dB")
```

### Computing Detection Probability

```python
from phased_array_systems.models.radar import compute_pd_from_snr

pd = compute_pd_from_snr(
    snr_db=15.0,
    pfa=1e-6,
    swerling=1,
)
print(f"Detection Probability: {pd:.3f}")
```

### Integration Gain

```python
from phased_array_systems.models.radar import coherent_integration_gain, noncoherent_integration_gain

# Coherent integration
gain_coherent = coherent_integration_gain(n_pulses=16)
print(f"Coherent Gain: {gain_coherent:.1f} dB")  # 12.0 dB

# Non-coherent integration
gain_noncoherent = noncoherent_integration_gain(n_pulses=16)
print(f"Non-coherent Gain: {gain_noncoherent:.1f} dB")  # ~6.0 dB
```

## Radar Range Equation

$$
SNR = \frac{P_t G^2 \lambda^2 \sigma}{(4\pi)^3 R^4 k T_s B_n L_s}
$$

Where:

- $P_t$ = Peak transmit power (W)
- $G$ = Antenna gain (linear)
- $\lambda$ = Wavelength (m)
- $\sigma$ = Target RCS (m²)
- $R$ = Target range (m)
- $k$ = Boltzmann constant
- $T_s$ = System noise temperature (K)
- $B_n$ = Noise bandwidth (Hz)
- $L_s$ = System losses (linear)

## Swerling Models

| Model | PDF | Decorrelation |
|-------|-----|---------------|
| 0 | Constant | None |
| 1 | Rayleigh | Scan-to-scan |
| 2 | Rayleigh | Pulse-to-pulse |
| 3 | Chi-squared (4 DOF) | Scan-to-scan |
| 4 | Chi-squared (4 DOF) | Pulse-to-pulse |

## MTI Clutter Suppression

Doppler-domain clutter rejection. See
[Theory: MTI Clutter Suppression](../../theory/mti-clutter-suppression.md).

::: phased_array_systems.models.radar.mti.clutter_spectral_std_hz

::: phased_array_systems.models.radar.mti.normalized_clutter_spread_rad

::: phased_array_systems.models.radar.mti.clutter_autocorrelation

::: phased_array_systems.models.radar.mti.canceller_weights

::: phased_array_systems.models.radar.mti.mti_signal_gain

::: phased_array_systems.models.radar.mti.mti_improvement_factor

::: phased_array_systems.models.radar.mti.mti_clutter_attenuation

::: phased_array_systems.models.radar.mti.required_clutter_attenuation_db

::: phased_array_systems.models.radar.mti.blind_speed_ms

::: phased_array_systems.models.radar.mti.doppler_shift_hz

::: phased_array_systems.models.radar.mti.unambiguous_range_m

## Track Accuracy

Closed-form measurement error and steady-state track performance. See
[Theory: Track Accuracy](../../theory/track-accuracy.md) for the equations and
the SNR-convention note.

::: phased_array_systems.models.radar.tracking.range_sigma_m

::: phased_array_systems.models.radar.tracking.angle_sigma_deg

::: phased_array_systems.models.radar.tracking.scan_broadened_beamwidth_deg

::: phased_array_systems.models.radar.tracking.crossrange_sigma_m

::: phased_array_systems.models.radar.tracking.velocity_sigma_ms

::: phased_array_systems.models.radar.tracking.combine_angle_errors_deg

::: phased_array_systems.models.radar.tracking.tracking_index

::: phased_array_systems.models.radar.tracking.deterministic_tracking_index

::: phased_array_systems.models.radar.tracking.process_noise_from_maneuver

::: phased_array_systems.models.radar.tracking.alpha_beta_gains

::: phased_array_systems.models.radar.tracking.steady_state_sigmas

::: phased_array_systems.models.radar.tracking.variance_reduction_position

::: phased_array_systems.models.radar.tracking.maneuver_lag_m

## See Also

- [Theory: Radar Equation](../../theory/radar-equation.md)
- [Theory: MTI Clutter Suppression](../../theory/mti-clutter-suppression.md)
- [Theory: Track Accuracy](../../theory/track-accuracy.md)
- [User Guide: Radar Detection](../../user-guide/radar-detection.md)
- [Scenarios API](../scenarios.md)
