# Scenarios API

Scenario classes for defining operating conditions.

## Overview

```python
from phased_array_systems.scenarios import (
    ScenarioBase,
    CommsLinkScenario,
    RadarDetectionScenario,
)
```

## Classes

::: phased_array_systems.scenarios.base.ScenarioBase
    options:
      show_root_heading: true
      members_order: source

::: phased_array_systems.scenarios.comms.CommsLinkScenario
    options:
      show_root_heading: true
      members_order: source

::: phased_array_systems.scenarios.radar.RadarDetectionScenario
    options:
      show_root_heading: true
      members_order: source

## Usage Examples

### Communications Scenario

```python
from phased_array_systems.scenarios import CommsLinkScenario

# Point-to-point link
scenario = CommsLinkScenario(
    freq_hz=10e9,
    bandwidth_hz=10e6,
    range_m=100e3,
    required_snr_db=10.0,
    scan_angle_deg=0.0,
    rx_antenna_gain_db=30.0,
    rx_noise_temp_k=290.0,
)

print(f"Wavelength: {scenario.wavelength_m * 100:.2f} cm")
print(f"Total extra loss: {scenario.total_extra_loss_db:.1f} dB")
```

### Radar Scenario

```python
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
```

### Satellite Link

```python
geo_scenario = CommsLinkScenario(
    freq_hz=12e9,
    bandwidth_hz=36e6,
    range_m=36000e3,
    required_snr_db=8.0,
    rx_antenna_gain_db=45.0,
    rx_noise_temp_k=80.0,
    atmospheric_loss_db=0.3,
    rain_loss_db=5.0,
)
```

## See Also

- [User Guide: Scenarios](../user-guide/scenarios.md)
- [User Guide: Link Budget](../user-guide/link-budget.md)
- [User Guide: Radar Detection](../user-guide/radar-detection.md)
