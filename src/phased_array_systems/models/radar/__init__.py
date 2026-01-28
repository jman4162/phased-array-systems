"""Radar detection models."""

from phased_array_systems.models.radar.detection import (
    albersheim_snr,
    compute_detection_threshold,
    compute_pd_from_snr,
    compute_snr_for_pd,
)
from phased_array_systems.models.radar.equation import RadarModel
from phased_array_systems.models.radar.integration import (
    coherent_integration_gain,
    integration_loss,
    noncoherent_integration_gain,
)

__all__ = [
    "RadarModel",
    "compute_detection_threshold",
    "compute_pd_from_snr",
    "compute_snr_for_pd",
    "albersheim_snr",
    "coherent_integration_gain",
    "noncoherent_integration_gain",
    "integration_loss",
]
