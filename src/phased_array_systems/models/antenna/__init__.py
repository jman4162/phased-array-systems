"""Antenna modeling adapter wrapping phased-array-modeling."""

from phased_array_systems.models.antenna.adapter import PhasedArrayAdapter
from phased_array_systems.models.antenna.errors import (
    amplitude_error_loss_db,
    beam_pointing_rms_deg,
    error_budget,
    phase_error_loss_db,
    phase_quantization_loss_db,
    phase_quantization_rms_rad,
    rms_sidelobe_floor_db,
)
from phased_array_systems.models.antenna.grating import check_grating_lobes
from phased_array_systems.models.antenna.metrics import (
    compute_array_gain,
    compute_beamwidth,
    compute_directivity_rectangular,
    compute_scan_loss,
    compute_sidelobe_level,
)
from phased_array_systems.models.antenna.taper import (
    aperture_efficiency_components,
    beamformer_noise_factor,
    compute_taper_efficiency,
    compute_taper_loss,
    estimate_taper_parameters,
    generate_taper_weights,
    taper_loss_from_sll,
)

__all__ = [
    # Adapter
    "PhasedArrayAdapter",
    # Metrics
    "compute_beamwidth",
    "compute_scan_loss",
    "compute_sidelobe_level",
    "compute_array_gain",
    "compute_directivity_rectangular",
    # Taper loss models
    "compute_taper_loss",
    "compute_taper_efficiency",
    "generate_taper_weights",
    "taper_loss_from_sll",
    "beamformer_noise_factor",
    "estimate_taper_parameters",
    "aperture_efficiency_components",
    # Error budget
    "amplitude_error_loss_db",
    "beam_pointing_rms_deg",
    "error_budget",
    "phase_error_loss_db",
    "phase_quantization_loss_db",
    "phase_quantization_rms_rad",
    "rms_sidelobe_floor_db",
    # Grating lobe detection
    "check_grating_lobes",
]
