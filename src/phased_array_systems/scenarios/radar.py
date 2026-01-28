"""Radar detection scenario definition."""

from typing import Literal

from pydantic import Field, computed_field

from phased_array_systems.constants import C_LIGHT
from phased_array_systems.scenarios.base import ScenarioBase


class RadarDetectionScenario(ScenarioBase):
    """Scenario for radar detection analysis.

    Defines the operating conditions for monostatic radar detection,
    including target characteristics, detection requirements, and
    pulse integration parameters.

    Attributes:
        freq_hz: Operating frequency (Hz)
        bandwidth_hz: Signal bandwidth (Hz)
        range_m: Target range (meters)
        target_rcs_dbsm: Target radar cross section (dBsm)
        rx_noise_temp_k: Receiver noise temperature (K)
        pfa: Probability of false alarm
        pd_required: Required probability of detection
        n_pulses: Number of pulses integrated
        scan_angle_deg: Beam scan angle from boresight (degrees)
        integration_type: Coherent or non-coherent integration
    """

    bandwidth_hz: float = Field(gt=0, description="Signal bandwidth (Hz)")
    range_m: float = Field(gt=0, description="Target range (m)")
    target_rcs_dbsm: float = Field(description="Target RCS (dBsm)")
    rx_noise_temp_k: float = Field(
        default=290.0, gt=0, description="Receiver noise temperature (K)"
    )
    pfa: float = Field(
        default=1e-6, gt=0, lt=1, description="Probability of false alarm"
    )
    pd_required: float = Field(
        default=0.9, gt=0, lt=1, description="Required probability of detection"
    )
    n_pulses: int = Field(default=1, ge=1, description="Number of pulses integrated")
    scan_angle_deg: float = Field(
        default=0.0, ge=0, le=90, description="Scan angle from boresight (deg)"
    )
    integration_type: Literal["coherent", "noncoherent"] = Field(
        default="noncoherent", description="Integration type"
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def wavelength_m(self) -> float:
        """Wavelength in meters."""
        return C_LIGHT / self.freq_hz

    @computed_field  # type: ignore[prop-decorator]
    @property
    def target_rcs_m2(self) -> float:
        """Target RCS in square meters."""
        return 10 ** (self.target_rcs_dbsm / 10)
