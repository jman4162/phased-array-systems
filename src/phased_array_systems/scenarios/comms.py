"""Communications link scenario definition."""

from typing import Literal

from pydantic import Field

from phased_array_systems.scenarios.base import ScenarioBase


class CommsLinkScenario(ScenarioBase):
    """Scenario for communications link budget analysis.

    Defines the parameters needed for a point-to-point or
    satellite communications link budget calculation.

    Attributes:
        freq_hz: Operating frequency (Hz)
        bandwidth_hz: Signal bandwidth (Hz)
        range_m: Link range/distance (meters)
        required_snr_db: Required SNR for demodulation (dB)
        scan_angle_deg: Beam scan angle from boresight (degrees)
        rx_antenna_gain_db: Receive antenna gain (dB), None for isotropic
        rx_noise_temp_k: Receive system noise temperature (K)
        path_loss_model: Propagation model to use
        path_loss_exponent: Path loss exponent for log-distance model
        rain_rate_mmh: Rain rate for rain attenuation (mm/hr)
        elevation_deg: Link elevation angle for atmospheric model (degrees)
        atmospheric_loss_db: Additional atmospheric losses (dB)
        rain_loss_db: Rain fade margin (dB)
        polarization_loss_db: Polarization mismatch loss (dB)
    """

    bandwidth_hz: float = Field(gt=0, description="Signal bandwidth (Hz)")
    range_m: float = Field(gt=0, description="Link range (m)")
    required_snr_db: float = Field(description="Required SNR (dB)")
    scan_angle_deg: float = Field(
        default=0.0, ge=0, le=90, description="Scan angle from boresight (deg)"
    )
    rx_antenna_gain_db: float | None = Field(
        default=None, description="RX antenna gain (dB), None for isotropic"
    )
    rx_noise_temp_k: float = Field(
        default=290.0, gt=0, description="RX system noise temperature (K)"
    )
    path_loss_model: Literal["fspl", "two_ray", "log_distance"] = Field(
        default="fspl", description="Path loss model"
    )
    path_loss_exponent: float = Field(
        default=2.0, ge=1.0, le=8.0, description="Path loss exponent for log-distance model"
    )
    rain_rate_mmh: float = Field(
        default=0.0, ge=0, description="Rain rate for computed rain attenuation (mm/hr)"
    )
    elevation_deg: float = Field(
        default=90.0, ge=0, le=90, description="Link elevation angle (deg, 90=zenith)"
    )
    # Manual loss overrides (additive to computed losses)
    atmospheric_loss_db: float = Field(default=0.0, ge=0, description="Atmospheric loss (dB)")
    rain_loss_db: float = Field(default=0.0, ge=0, description="Rain loss margin (dB)")
    polarization_loss_db: float = Field(default=0.0, ge=0, description="Polarization loss (dB)")

    @property
    def total_extra_loss_db(self) -> float:
        """Total additional losses beyond free space path loss."""
        return self.atmospheric_loss_db + self.rain_loss_db + self.polarization_loss_db
