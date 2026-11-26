# Antenna Models API

Antenna array adapter and metrics extraction.

## Overview

```python
from phased_array_systems.models.antenna import (
    PhasedArrayAdapter,
    compute_beamwidth,
    compute_scan_loss,
    compute_sidelobe_level,
)
```

The antenna module provides an adapter to the `phased-array-modeling` package for detailed antenna pattern computations.

## Classes

::: phased_array_systems.models.antenna.adapter.PhasedArrayAdapter
    options:
      show_root_heading: true
      members_order: source

## Functions

::: phased_array_systems.models.antenna.metrics.compute_beamwidth
    options:
      show_root_heading: true

::: phased_array_systems.models.antenna.metrics.compute_scan_loss
    options:
      show_root_heading: true

::: phased_array_systems.models.antenna.metrics.compute_sidelobe_level
    options:
      show_root_heading: true

## Output Metrics

| Metric | Units | Description |
|--------|-------|-------------|
| `g_peak_db` | dB | Peak antenna gain |
| `beamwidth_az_deg` | degrees | 3 dB azimuth beamwidth, at the scenario's scan angle |
| `beamwidth_el_deg` | degrees | 3 dB elevation beamwidth, at the scenario's scan angle |
| `beamwidth_az_broadside_deg` | degrees | 3 dB azimuth beamwidth at broadside (scan-invariant) |
| `beamwidth_el_broadside_deg` | degrees | 3 dB elevation beamwidth at broadside (scan-invariant) |
| `sll_db` | dB | Peak sidelobe level |
| `scan_loss_db` | dB | Gain reduction due to scan |
| `directivity_db` | dB | Antenna directivity |
| `n_elements` | - | Total element count |

## Usage Examples

### Using the Adapter

```python
from phased_array_systems.models.antenna import PhasedArrayAdapter
from phased_array_systems.architecture import Architecture, ArrayConfig, RFChainConfig

arch = Architecture(
    array=ArrayConfig(nx=8, ny=8, dx_lambda=0.5, dy_lambda=0.5),
    rf=RFChainConfig(tx_power_w_per_elem=1.0),
)

adapter = PhasedArrayAdapter()
metrics = adapter.evaluate(arch, scenario, context={})

print(f"Peak Gain: {metrics['g_peak_db']:.1f} dB")
print(f"Beamwidth: {metrics['beamwidth_az_deg']:.1f}° x {metrics['beamwidth_el_deg']:.1f}°")
```

### With Scan Angle

```python
from phased_array_systems.scenarios import CommsLinkScenario

scenario = CommsLinkScenario(
    freq_hz=10e9,
    bandwidth_hz=10e6,
    range_m=100e3,
    required_snr_db=10.0,
    scan_angle_deg=30.0,  # 30° off boresight
)

metrics = adapter.evaluate(arch, scenario, context={})
print(f"Scan Loss: {metrics['scan_loss_db']:.1f} dB")
```

## Gain Approximation

When the full antenna adapter is not used, gain is approximated:

$$
G \approx 4\pi \cdot n_x d_x \cdot n_y d_y
$$

Where $d_x, d_y$ are element spacings in wavelengths.

This approximation is used in the link budget model when antenna metrics aren't pre-computed.

## See Also

- [Communications Models](comms.md)
- [User Guide: Link Budget](../../user-guide/link-budget.md)
