"""Digital array models for DAC/ADC, bandwidth, and scheduling."""

from phased_array_systems.models.digital.bandwidth import (
    beam_bandwidth_product,
    beamformer_operations,
    channelizer_output_rate,
    digital_beamformer_data_rate,
    max_simultaneous_beams,
    processing_margin,
)
from phased_array_systems.models.digital.converters import (
    adc_dynamic_range,
    dac_output_power,
    enob_to_sfdr,
    enob_to_snr,
    max_signal_bandwidth,
    quantization_noise_floor,
    sample_rate_for_bandwidth,
    sfdr_to_enob,
    snr_to_enob,
)
from phased_array_systems.models.digital.scheduling import (
    Dwell,
    Function,
    Timeline,
    interleaved_timeline,
    max_update_rate,
    search_timeline,
    timeline_utilization,
)

__all__ = [
    # Converters
    "enob_to_sfdr",
    "sfdr_to_enob",
    "enob_to_snr",
    "snr_to_enob",
    "quantization_noise_floor",
    "sample_rate_for_bandwidth",
    "max_signal_bandwidth",
    "adc_dynamic_range",
    "dac_output_power",
    # Bandwidth
    "beam_bandwidth_product",
    "max_simultaneous_beams",
    "digital_beamformer_data_rate",
    "channelizer_output_rate",
    "processing_margin",
    "beamformer_operations",
    # Scheduling
    "Dwell",
    "Timeline",
    "Function",
    "timeline_utilization",
    "max_update_rate",
    "search_timeline",
    "interleaved_timeline",
]
