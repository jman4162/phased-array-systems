# SWaP-C Models API

Size, Weight, Power, and Cost models.

## Overview

```python
from phased_array_systems.models.swapc import PowerModel, CostModel
```

## Classes

::: phased_array_systems.models.swapc.power.PowerModel
    options:
      show_root_heading: true
      members_order: source

::: phased_array_systems.models.swapc.cost.CostModel
    options:
      show_root_heading: true
      members_order: source

## Functions

::: phased_array_systems.models.swapc.power.compute_thermal_load
    options:
      show_root_heading: true

::: phased_array_systems.models.swapc.cost.compute_cost_per_watt
    options:
      show_root_heading: true

    options:
      show_root_heading: true

## Output Metrics

### Power Metrics

| Metric | Units | Description |
|--------|-------|-------------|
| `rf_power_w` | W | Total RF power (all elements) |
| `dc_power_w` | W | DC power (RF / PA efficiency) |
| `heat_dissipation_w` | Heat to remove (DC in minus average RF out) |
| `heat_flux_w_per_cm2` | Dissipated power per aperture area (average power) |
| `radiated_power_density_peak_w_per_cm2` | Radiated power per aperture area, peak |
| `radiated_power_density_avg_w_per_cm2` | Radiated power per aperture area, average |
| `aperture_area_m2`, `cell_area_cm2` | Physical aperture and unit-cell area |
| `prime_power_w` | W | Total prime power |

### Cost Metrics

| Metric | Units | Description |
|--------|-------|-------------|
| `recurring_cost_usd` | USD | Element cost × count |
| `nre_cost_usd` | USD | Non-recurring engineering |
| `integration_cost_usd` | USD | System integration |
| `cost_usd` | USD | Total cost |

## Usage Examples

### Power Calculation

```python
from phased_array_systems.models.swapc import PowerModel

# Using PowerModel
model = PowerModel()
metrics = model.evaluate(arch, scenario, context={})
print(f"Prime Power: {metrics['prime_power_w']:.0f} W")
print(f"RF Power: {metrics['rf_power_w']:.0f} W")
print(f"DC Power: {metrics['dc_power_w']:.0f} W")
```

### Cost Calculation

```python
from phased_array_systems.models.swapc import CostModel

# Using CostModel
model = CostModel()
metrics = model.evaluate(arch, scenario, context={})
print(f"Total Cost: ${metrics['cost_usd']:,.0f}")
print(f"Recurring: ${metrics['recurring_cost_usd']:,.0f}")
print(f"NRE: ${metrics['nre_cost_usd']:,.0f}")
```

### Cost Analysis Utilities

```python
from phased_array_systems.models.swapc.cost import compute_cost_per_watt

# Cost efficiency metrics
cost_per_watt = compute_cost_per_watt(total_cost_usd=50000, rf_power_w=100)

print(f"Cost per Watt: ${cost_per_watt:.0f}/W")
```

## Power Equations

### RF Power

$$
P_{RF} = P_{elem} \times N
$$

### DC Power

$$
P_{DC} = \frac{P_{RF}}{\eta_{PA}}
$$

### Prime Power

Prime power includes additional overhead (typically DC power plus auxiliaries):

$$
P_{prime} = P_{DC} \times (1 + overhead)
$$

## Cost Equations

### Recurring Cost

$$
C_{recurring} = C_{elem} \times N
$$

### Total Cost

$$
C_{total} = C_{recurring} + C_{NRE} + C_{integration}
$$

## Trade-offs

### Power vs. Array Size

```python
# Power scales linearly with element count
# For constant EIRP, larger arrays need less power per element

# 8x8 at 1W each: P = 64W RF
# 16x16 at 0.25W each: P = 64W RF, but 6dB more gain from aperture
```

### Cost vs. Performance

```python
# Cost scaling factors:
# - Element count: linear
# - Power per element: typically superlinear
# - Frequency: higher frequency = higher cost per element
```

## See Also

- [Architecture API](../architecture.md) - CostConfig definition
- [User Guide: Trade Studies](../../user-guide/trade-studies.md)
