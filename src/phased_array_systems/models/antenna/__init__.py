"""Antenna modeling adapter wrapping phased-array-modeling."""

from phased_array_systems.models.antenna.adapter import PhasedArrayAdapter
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
    "taper_loss_from_sll",
    "beamformer_noise_factor",
    "estimate_taper_parameters",
    "aperture_efficiency_components",
    # Grating lobe detection
    "check_grating_lobes",
]
