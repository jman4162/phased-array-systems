# RF Cascade Models API

Noise figure, gain cascade, and dynamic range calculations for RF receiver/transmitter chains.

## Overview

```python
from phased_array_systems.models.rf import (
    # Noise figure
    friis_noise_figure,
    noise_figure_to_temp,
    noise_temp_to_figure,
    system_noise_temperature,
    # Gain
    cascade_gain,
    cascade_gain_db,
    # Dynamic range
    cascade_iip3,
    cascade_oip3,
    sfdr_from_iip3,
    sfdr_from_oip3,
    mds_from_noise_figure,
    # Complete cascade
    RFStage,
    cascade_analysis,
)
```

## Noise Figure Functions

Functions for calculating cascaded noise figure and noise temperature conversions.

::: phased_array_systems.models.rf.cascade.noise_figure_to_temp
    options:
      show_root_heading: true

::: phased_array_systems.models.rf.cascade.noise_temp_to_figure
    options:
      show_root_heading: true

::: phased_array_systems.models.rf.cascade.friis_noise_figure
    options:
      show_root_heading: true

::: phased_array_systems.models.rf.cascade.system_noise_temperature
    options:
      show_root_heading: true

## Gain Functions

Functions for calculating cascaded gain through multi-stage RF chains.

::: phased_array_systems.models.rf.cascade.cascade_gain
    options:
      show_root_heading: true

::: phased_array_systems.models.rf.cascade.cascade_gain_db
    options:
      show_root_heading: true

## Dynamic Range Functions

Functions for calculating cascaded intercept points and spurious-free dynamic range.

::: phased_array_systems.models.rf.cascade.cascade_iip3
    options:
      show_root_heading: true

::: phased_array_systems.models.rf.cascade.cascade_oip3
    options:
      show_root_heading: true

::: phased_array_systems.models.rf.cascade.sfdr_from_iip3
    options:
      show_root_heading: true

::: phased_array_systems.models.rf.cascade.sfdr_from_oip3
    options:
      show_root_heading: true

::: phased_array_systems.models.rf.cascade.mds_from_noise_figure
    options:
      show_root_heading: true

## Complete Cascade Analysis

Classes and functions for comprehensive RF chain analysis.

::: phased_array_systems.models.rf.cascade.RFStage
    options:
      show_root_heading: true
      members_order: source

::: phased_array_systems.models.rf.cascade.cascade_analysis
    options:
      show_root_heading: true

## Output Metrics

| Metric | Units | Description |
|--------|-------|-------------|
| `total_gain_db` | dB | Cascaded system gain |
| `total_nf_db` | dB | Cascaded noise figure |
| `noise_temp_k` | K | Equivalent noise temperature |
| `iip3_dbm` | dBm | Input third-order intercept point |
| `oip3_dbm` | dBm | Output third-order intercept point |
| `sfdr_db` | dB | Spurious-free dynamic range |
| `mds_dbm` | dBm | Minimum detectable signal |
| `noise_floor_dbm` | dBm | Integrated noise floor |

## Usage Examples

### Friis Noise Figure Cascade

```python
from phased_array_systems.models.rf import friis_noise_figure

# LNA -> Mixer -> IF Amp chain
result = friis_noise_figure([
    (20, 1.5),   # LNA: 20 dB gain, 1.5 dB NF
    (-8, 8),     # Mixer: -8 dB gain (loss), 8 dB NF
    (30, 4),     # IF Amp: 30 dB gain, 4 dB NF
])

print(f"System NF: {result['total_nf_db']:.2f} dB")
print(f"System Gain: {result['total_gain_db']:.1f} dB")
print(f"Noise Temperature: {result['noise_temp_k']:.1f} K")
```

### System Noise Temperature

```python
from phased_array_systems.models.rf import system_noise_temperature

# Satellite receiver with cold sky
result = system_noise_temperature(
    antenna_temp_k=50,       # Cold sky
    receiver_nf_db=2.0,      # Low-noise receiver
    line_loss_db=0.5,        # Cable/waveguide loss
)

print(f"System Temperature: {result['system_temp_k']:.1f} K")
print(f"Antenna contribution: {result['antenna_contribution_k']:.1f} K")
print(f"Receiver contribution: {result['receiver_contribution_k']:.1f} K")
```

### Cascaded IIP3 and SFDR

```python
from phased_array_systems.models.rf import cascade_iip3, sfdr_from_iip3

# Calculate cascaded linearity
iip3_result = cascade_iip3([
    (20, -5),    # LNA: 20 dB gain, -5 dBm IIP3
    (-8, 15),    # Mixer: -8 dB gain, +15 dBm IIP3
    (30, 10),    # IF Amp: 30 dB gain, +10 dBm IIP3
])

print(f"Cascaded IIP3: {iip3_result['iip3_dbm']:.1f} dBm")
print(f"Cascaded OIP3: {iip3_result['oip3_dbm']:.1f} dBm")

# Calculate SFDR
sfdr_result = sfdr_from_iip3(
    iip3_dbm=iip3_result['iip3_dbm'],
    noise_floor_dbm_hz=-170,  # -174 dBm/Hz + 4 dB NF
    bandwidth_hz=10e6,
)

print(f"SFDR: {sfdr_result['sfdr_db']:.1f} dB")
```

### Minimum Detectable Signal

```python
from phased_array_systems.models.rf import mds_from_noise_figure

result = mds_from_noise_figure(
    noise_figure_db=3,
    bandwidth_hz=1e6,
    snr_required_db=10,
)

print(f"MDS: {result['mds_dbm']:.1f} dBm")
print(f"Noise Floor: {result['noise_floor_dbm']:.1f} dBm")
print(f"kTB: {result['ktb_dbm']:.1f} dBm")
```

### Complete RF Chain Analysis

```python
from phased_array_systems.models.rf import RFStage, cascade_analysis

# Define receiver chain
stages = [
    RFStage("LNA", gain_db=20, noise_figure_db=1.5, iip3_dbm=-5),
    RFStage("BPF", gain_db=-2, noise_figure_db=2, iip3_dbm=30),
    RFStage("Mixer", gain_db=-8, noise_figure_db=8, iip3_dbm=15),
    RFStage("IF Amp", gain_db=30, noise_figure_db=4, iip3_dbm=10),
    RFStage("ADC Driver", gain_db=10, noise_figure_db=6, iip3_dbm=20),
]

result = cascade_analysis(
    stages=stages,
    bandwidth_hz=10e6,
    input_power_dbm=-60,
)

print(f"System NF: {result['total_nf_db']:.2f} dB")
print(f"System Gain: {result['total_gain_db']:.1f} dB")
print(f"IIP3: {result['iip3_dbm']:.1f} dBm")
print(f"SFDR: {result['sfdr_db']:.1f} dB")
print(f"MDS: {result['mds_dbm']:.1f} dBm")
print(f"Output Power: {result['output_power_dbm']:.1f} dBm")
```

## Key Equations

### Friis Noise Figure

$$
F_{total} = F_1 + \frac{F_2 - 1}{G_1} + \frac{F_3 - 1}{G_1 G_2} + \cdots
$$

### Noise Figure to Temperature

$$
T_e = T_0 (F - 1)
$$

Where $T_0 = 290$ K (reference temperature).

### Cascaded IIP3

$$
\frac{1}{IIP3_{total}} = \frac{1}{IIP3_1} + \frac{G_1}{IIP3_2} + \frac{G_1 G_2}{IIP3_3} + \cdots
$$

### Spurious-Free Dynamic Range

$$
SFDR = \frac{2}{3} (IIP3 - N_{floor})
$$

### Minimum Detectable Signal

$$
MDS = kTB + NF + SNR_{required}
$$

Where $kT = -174$ dBm/Hz at 290 K.

## Design Guidelines

### LNA Placement

The Friis equation shows why low-noise amplifiers (LNAs) must be placed first:

- First stage dominates system noise figure
- High gain in first stage reduces impact of subsequent stages
- Trade-off: high-gain LNA can degrade linearity

### Typical NF Budget

| Stage | Typical NF | Typical Gain |
|-------|------------|--------------|
| LNA | 1-3 dB | 15-25 dB |
| Filter | 1-3 dB | -1 to -3 dB |
| Mixer | 6-10 dB | -6 to -10 dB |
| IF Amp | 3-6 dB | 20-40 dB |

### Dynamic Range Considerations

- **IIP3** limited by early high-gain stages
- **SFDR** balances noise and linearity
- Back-off from P1dB typically 10-12 dB below IIP3

## See Also

- [Digital Models](digital.md) - ADC/DAC and digital beamforming
- [Communications Models](comms.md) - Link budget calculations
- [Theory: Link Budget Equations](../../theory/link-budget-equations.md)
