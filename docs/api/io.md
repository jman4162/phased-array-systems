# I/O API

Configuration loading and results export.

## Overview

```python
from phased_array_systems.io import (
    load_config,
    export_results,
)
```

## Functions

::: phased_array_systems.io.config_loader.load_config
    options:
      show_root_heading: true

::: phased_array_systems.io.exporters.export_results
    options:
      show_root_heading: true

## Usage Examples

### Loading Configuration

```python
from phased_array_systems.io import load_config

# Load from YAML
config = load_config("config.yaml")

# Load from JSON
config = load_config("config.json")

# Access components
arch = config.get_architecture()
scenario = config.get_scenario()
requirements = config.get_requirement_set()
```

### Configuration Schema

```yaml
# config.yaml
name: "My Trade Study"

architecture:
  array:
    geometry: rectangular
    nx: 8
    ny: 8
    dx_lambda: 0.5
    dy_lambda: 0.5
    scan_limit_deg: 60.0
  rf:
    tx_power_w_per_elem: 1.0
    pa_efficiency: 0.3
    noise_figure_db: 3.0
  cost:
    cost_per_elem_usd: 100.0
    nre_usd: 10000.0

scenario:
  type: comms
  freq_hz: 10.0e9
  bandwidth_hz: 10.0e6
  range_m: 100.0e3
  required_snr_db: 10.0

requirements:
  - id: REQ-001
    name: Minimum EIRP
    metric_key: eirp_dbw
    op: ">="
    value: 40.0
    severity: must

design_space:
  variables:
    - name: array.nx
      type: categorical
      values: [4, 8, 16]
    - name: rf.tx_power_w_per_elem
      type: float
      low: 0.5
      high: 3.0
```

### Exporting Results

```python
from phased_array_systems.io import export_results
import pandas as pd

# Export to Parquet (recommended for large datasets)
export_results(results, "results.parquet")

# Export to CSV
export_results(results, "results.csv", format="csv")

# Loading back
results_loaded = pd.read_parquet("results.parquet")
```

### Format Options

| Format | Extension | Best For |
|--------|-----------|----------|
| Parquet | `.parquet` | Large datasets, fast I/O |
| CSV | `.csv` | Human-readable, Excel |

### Parquet Benefits

- Compressed storage
- Faster read/write
- Preserves data types
- Column-oriented (efficient for analysis)

```python
# Parquet is ~5x smaller and ~10x faster for typical results
export_results(results, "results.parquet")  # Recommended

# CSV for compatibility
export_results(results, "results.csv", format="csv")
```

## Config Object

::: phased_array_systems.io.schema.StudyConfig
    options:
      show_root_heading: true
      members_order: source

## YAML Schema Reference

### Architecture Section

```yaml
architecture:
  array:
    geometry: rectangular  # rectangular, circular, triangular
    nx: 8                  # Required
    ny: 8                  # Required
    dx_lambda: 0.5         # Default: 0.5
    dy_lambda: 0.5         # Default: 0.5
    scan_limit_deg: 60.0   # Default: 60.0
    max_subarray_nx: 8     # Default: 8
    max_subarray_ny: 8     # Default: 8
    enforce_subarray_constraint: true  # Default: true

  rf:
    tx_power_w_per_elem: 1.0  # Required
    pa_efficiency: 0.3        # Default: 0.3
    noise_figure_db: 3.0      # Default: 3.0
    n_tx_beams: 1             # Default: 1
    feed_loss_db: 1.0         # Default: 1.0
    system_loss_db: 0.0       # Default: 0.0

  cost:
    cost_per_elem_usd: 100.0     # Default: 100.0
    nre_usd: 0.0                 # Default: 0.0
    integration_cost_usd: 0.0    # Default: 0.0
```

### Scenario Section

```yaml
# Communications scenario
scenario:
  type: comms
  freq_hz: 10.0e9          # Required
  bandwidth_hz: 10.0e6     # Required
  range_m: 100.0e3         # Required
  required_snr_db: 10.0    # Required
  scan_angle_deg: 0.0      # Default: 0.0
  rx_antenna_gain_db: 0.0  # Default: None (isotropic)
  rx_noise_temp_k: 290.0   # Default: 290.0
  atmospheric_loss_db: 0.0 # Default: 0.0
  rain_loss_db: 0.0        # Default: 0.0

# Radar scenario
scenario:
  type: radar
  freq_hz: 10.0e9          # Required
  bandwidth_hz: 100.0e3    # Required
  range_m: 100.0e3         # Required
  target_rcs_dbsm: 0.0     # Required
  pd_required: 0.9         # Default: 0.9
  pfa: 1.0e-6              # Default: 1e-6
  n_pulses: 1              # Default: 1
  swerling: 0              # Default: 0
  integration_type: noncoherent  # Default: noncoherent
  prf_hz: 1000             # Optional; enables dwell and timeline metrics
```

### Requirements Section

```yaml
requirements:
  - id: REQ-001
    name: Minimum EIRP
    metric_key: eirp_dbw
    op: ">="
    value: 40.0
    units: dBW             # Optional
    severity: must         # must, should, nice

  - id: REQ-002
    name: Maximum Cost
    metric_key: cost_usd
    op: "<="
    value: 50000.0
    severity: must
```

### Design Space Section

```yaml
design_space:
  variables:
    # Categorical
    - name: array.nx
      type: categorical
      values: [4, 8, 16]

    # Integer range
    - name: array.ny
      type: int
      low: 4
      high: 16

    # Float range
    - name: rf.tx_power_w_per_elem
      type: float
      low: 0.5
      high: 3.0

    # Fixed value (low == high)
    - name: array.dx_lambda
      type: float
      low: 0.5
      high: 0.5
```

## See Also

- [User Guide: Trade Studies](../user-guide/trade-studies.md)
- [CLI Reference](../cli/index.md)
