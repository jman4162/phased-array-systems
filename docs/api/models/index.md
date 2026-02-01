# Models API

Computational models for antenna, communications, radar, and SWaP-C analysis.

## Overview

Models follow the `ModelBlock` protocol:

```python
from typing import Protocol

class ModelBlock(Protocol):
    name: str

    def evaluate(
        self,
        arch: Architecture,
        scenario: Scenario,
        context: dict,
    ) -> dict[str, float]:
        """Evaluate model and return metrics."""
        ...
```

## Model Categories

| Module | Purpose |
|--------|---------|
| [Antenna](antenna.md) | Array metrics and `phased-array-modeling` adapter |
| [Communications](comms.md) | Link budget calculations |
| [Radar](radar.md) | Radar equation and detection |
| [Digital](digital.md) | ADC/DAC, bandwidth, timeline scheduling |
| [RF](rf.md) | Noise figure, gain cascade, dynamic range |
| [SWaP-C](swapc.md) | Size, Weight, Power, and Cost |

## Canonical Metrics

All models contribute to a unified metrics dictionary:

### Antenna Metrics

| Key | Units | Description |
|-----|-------|-------------|
| `g_peak_db` | dB | Peak antenna gain |
| `beamwidth_az_deg` | degrees | Azimuth beamwidth |
| `beamwidth_el_deg` | degrees | Elevation beamwidth |
| `sll_db` | dB | Sidelobe level |
| `scan_loss_db` | dB | Scan loss |
| `directivity_db` | dB | Directivity |

### Communications Metrics

| Key | Units | Description |
|-----|-------|-------------|
| `eirp_dbw` | dBW | Effective isotropic radiated power |
| `path_loss_db` | dB | Total path loss |
| `rx_power_dbw` | dBW | Received power |
| `noise_power_dbw` | dBW | Receiver noise power |
| `snr_rx_db` | dB | Received SNR |
| `link_margin_db` | dB | Link margin |

### Radar Metrics

| Key | Units | Description |
|-----|-------|-------------|
| `snr_single_pulse_db` | dB | Single-pulse SNR |
| `snr_integrated_db` | dB | Integrated SNR |
| `snr_required_db` | dB | Required SNR for Pd/Pfa |
| `snr_margin_db` | dB | SNR margin |
| `detection_range_m` | m | Maximum detection range |

### SWaP-C Metrics

| Key | Units | Description |
|-----|-------|-------------|
| `cost_usd` | USD | Total cost |
| `recurring_cost_usd` | USD | Recurring cost |
| `prime_power_w` | W | Prime power consumption |
| `rf_power_w` | W | RF power |
| `dc_power_w` | W | DC power |

### Metadata

| Key | Units | Description |
|-----|-------|-------------|
| `meta.case_id` | - | Unique case identifier |
| `meta.runtime_s` | s | Evaluation runtime |
| `meta.error` | - | Error message (if any) |

## Using Models Directly

```python
from phased_array_systems.models.comms.link_budget import CommsLinkModel

model = CommsLinkModel()

# Evaluate with context
context = {"g_peak_db": 28.0}  # Pre-computed antenna gain
metrics = model.evaluate(arch, scenario, context)
```

## See Also

- [User Guide: Link Budget](../../user-guide/link-budget.md)
- [User Guide: Radar Detection](../../user-guide/radar-detection.md)
