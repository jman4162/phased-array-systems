# Digital Array Models API

ADC/DAC converters, bandwidth calculations, and timeline scheduling for digital phased arrays.

## Overview

```python
from phased_array_systems.models.digital import (
    # Converters
    enob_to_snr,
    snr_to_enob,
    enob_to_sfdr,
    sfdr_to_enob,
    quantization_noise_floor,
    sample_rate_for_bandwidth,
    max_signal_bandwidth,
    adc_dynamic_range,
    dac_output_power,
    # Bandwidth
    beam_bandwidth_product,
    max_simultaneous_beams,
    digital_beamformer_data_rate,
    channelizer_output_rate,
    processing_margin,
    beamformer_operations,
    # Scheduling
    Dwell,
    Timeline,
    Function,
    timeline_utilization,
    max_update_rate,
    search_timeline,
    interleaved_timeline,
)
```

## Converters

Functions for analyzing ADC/DAC performance including ENOB, SNR, SFDR, and quantization noise.

### Key Relationships

- SNR (ideal) = 6.02 * ENOB + 1.76 dB
- SFDR ~ SNR for ideal converters
- Nyquist: fs >= 2 * BW (practical: fs >= 2.5 * BW)

::: phased_array_systems.models.digital.converters.enob_to_snr
    options:
      show_root_heading: true

::: phased_array_systems.models.digital.converters.snr_to_enob
    options:
      show_root_heading: true

::: phased_array_systems.models.digital.converters.enob_to_sfdr
    options:
      show_root_heading: true

::: phased_array_systems.models.digital.converters.sfdr_to_enob
    options:
      show_root_heading: true

::: phased_array_systems.models.digital.converters.quantization_noise_floor
    options:
      show_root_heading: true

::: phased_array_systems.models.digital.converters.sample_rate_for_bandwidth
    options:
      show_root_heading: true

::: phased_array_systems.models.digital.converters.max_signal_bandwidth
    options:
      show_root_heading: true

::: phased_array_systems.models.digital.converters.adc_dynamic_range
    options:
      show_root_heading: true

::: phased_array_systems.models.digital.converters.dac_output_power
    options:
      show_root_heading: true

## Bandwidth

Functions for analyzing digital beamformer bandwidth constraints, beam-bandwidth products, and data rates.

::: phased_array_systems.models.digital.bandwidth.beam_bandwidth_product
    options:
      show_root_heading: true

::: phased_array_systems.models.digital.bandwidth.max_simultaneous_beams
    options:
      show_root_heading: true

::: phased_array_systems.models.digital.bandwidth.digital_beamformer_data_rate
    options:
      show_root_heading: true

::: phased_array_systems.models.digital.bandwidth.channelizer_output_rate
    options:
      show_root_heading: true

::: phased_array_systems.models.digital.bandwidth.processing_margin
    options:
      show_root_heading: true

::: phased_array_systems.models.digital.bandwidth.beamformer_operations
    options:
      show_root_heading: true

## Scheduling

Classes and functions for timeline and scheduling in multi-function arrays.

### Classes

::: phased_array_systems.models.digital.scheduling.Function
    options:
      show_root_heading: true
      members_order: source

::: phased_array_systems.models.digital.scheduling.Dwell
    options:
      show_root_heading: true
      members_order: source

::: phased_array_systems.models.digital.scheduling.Timeline
    options:
      show_root_heading: true
      members_order: source

### Functions

::: phased_array_systems.models.digital.scheduling.timeline_utilization
    options:
      show_root_heading: true

::: phased_array_systems.models.digital.scheduling.max_update_rate
    options:
      show_root_heading: true

::: phased_array_systems.models.digital.scheduling.search_timeline
    options:
      show_root_heading: true

::: phased_array_systems.models.digital.scheduling.interleaved_timeline
    options:
      show_root_heading: true

## Usage Examples

### ADC Performance Analysis

```python
from phased_array_systems.models.digital import (
    enob_to_snr,
    adc_dynamic_range,
    sample_rate_for_bandwidth,
)

# 14-bit ADC analysis
enob = 14
snr = enob_to_snr(enob)
print(f"Ideal SNR: {snr:.1f} dB")  # 86.0 dB

# Dynamic range with front-end noise
result = adc_dynamic_range(
    enob=14,
    noise_figure_db=3,
    bandwidth_hz=100e6
)
print(f"Dynamic Range: {result['dynamic_range_db']:.1f} dB")

# Sample rate for 100 MHz signal
fs = sample_rate_for_bandwidth(100e6)
print(f"Required Sample Rate: {fs/1e6:.0f} MHz")  # 250 MHz
```

### Digital Beamformer Data Rate

```python
from phased_array_systems.models.digital import (
    digital_beamformer_data_rate,
    beam_bandwidth_product,
    max_simultaneous_beams,
)

# 256-element array with 1 GSPS ADCs
result = digital_beamformer_data_rate(
    n_elements=256,
    sample_rate_hz=1e9,
    bits_per_sample=14,
)
print(f"Total Data Rate: {result['with_overhead_gbps']:.1f} Gbps")

# How many beams with 10 GHz processing bandwidth?
n_beams = max_simultaneous_beams(
    processing_bandwidth_hz=10e9,
    bandwidth_per_beam_hz=100e6,
)
print(f"Max Simultaneous Beams: {n_beams}")
```

### Radar Search Timeline

```python
from phased_array_systems.models.digital import (
    search_timeline,
    timeline_utilization,
    max_update_rate,
)

# Generate raster search pattern
tl = search_timeline(
    azimuth_range_deg=(-60, 60),
    elevation_range_deg=(0, 30),
    azimuth_step_deg=3.0,
    elevation_step_deg=3.0,
    dwell_time_us=100,
)
print(f"Search requires {tl.n_dwells} beam positions")

# Analyze utilization
util = timeline_utilization(tl)
print(f"Frame time: {util['frame_time_ms']:.1f} ms")
print(f"Utilization: {util['total_utilization']*100:.1f}%")
```

### Multi-Function Interleaved Timeline

```python
from phased_array_systems.models.digital import (
    Function,
    interleaved_timeline,
    timeline_utilization,
)

# Create interleaved search/track timeline
tl = interleaved_timeline(
    functions=[
        {"function": Function.RADAR_SEARCH, "time_percent": 60,
         "dwell_time_us": 100, "priority": 1},
        {"function": Function.RADAR_TRACK, "time_percent": 30,
         "dwell_time_us": 50, "priority": 2},
        {"function": Function.ESM, "time_percent": 10,
         "dwell_time_us": 200, "priority": 1},
    ],
    frame_time_ms=100,
)

util = timeline_utilization(tl)
print(f"Search allocation: {util['by_function_percent']['radar_search']:.1f}%")
print(f"Track allocation: {util['by_function_percent']['radar_track']:.1f}%")
```

## Key Equations

### ENOB-SNR Relationship

$$
SNR = 6.02 \times ENOB + 1.76 \text{ dB}
$$

### Quantization Noise Floor

$$
N_{floor} = P_{fs} - SNR - 10\log_{10}\left(\frac{f_s}{2}\right) \text{ dBm/Hz}
$$

### Beam-Bandwidth Product

$$
BBP = N_{beams} \times BW_{per\_beam}
$$

### Digital Beamformer Data Rate

$$
R_{data} = N_{elements} \times f_s \times bits \times N_{channels} \times overhead
$$

## See Also

- [RF Models](rf.md) - RF cascade analysis
- [Radar Models](radar.md) - Radar detection calculations
- [Theory: Phased Arrays](../../theory/phased-arrays.md)
