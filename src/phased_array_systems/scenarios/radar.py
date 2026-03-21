"""Radar detection scenario definition."""

from typing import Literal

from pydantic import Field, computed_field

from phased_array_systems.constants import C_LIGHT
from phased_array_systems.scenarios.base import ScenarioBase

ClutterType = Literal["none", "sea", "ground", "rain"]
TerrainType = Literal["rural", "urban", "forest", "desert", "wetland"]
CFARType = Literal["none", "CA", "OS", "GO", "SO"]
PolarizationType = Literal["HH", "VV", "HV"]


class RadarDetectionScenario(ScenarioBase):
    """Scenario for radar detection analysis.

    Defines the operating conditions for monostatic radar detection,
    including target characteristics, detection requirements, pulse
    integration parameters, clutter environment, and propagation effects.

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
        clutter_type: Type of clutter environment
        sea_state: Sea state for sea clutter (0-6 Douglas scale)
        terrain_type: Terrain type for ground clutter
        rain_rate_mm_hr: Rain rate for rain clutter/attenuation
        grazing_angle_deg: Grazing angle for clutter calculations
        antenna_height_m: Antenna height above surface
        target_height_m: Target height above surface
        polarization: Antenna polarization
        cfar_type: CFAR detector type
        cfar_ref_cells: Number of CFAR reference cells
        cfar_guard_cells: Number of CFAR guard cells
        include_atmos_loss: Include atmospheric attenuation
        temperature_c: Ambient temperature for atmos model
        humidity_pct: Relative humidity for atmos model
    """

    bandwidth_hz: float = Field(gt=0, description="Signal bandwidth (Hz)")
    range_m: float = Field(gt=0, description="Target range (m)")
    target_rcs_dbsm: float = Field(description="Target RCS (dBsm)")
    rx_noise_temp_k: float = Field(
        default=290.0, gt=0, description="Receiver noise temperature (K)"
    )
    pfa: float = Field(default=1e-6, gt=0, lt=1, description="Probability of false alarm")
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

    # Clutter parameters
    clutter_type: ClutterType = Field(default="none", description="Type of clutter environment")
    sea_state: int = Field(default=3, ge=0, le=6, description="Sea state (0-6 Douglas scale)")
    terrain_type: TerrainType = Field(
        default="rural", description="Terrain type for ground clutter"
    )
    rain_rate_mm_hr: float = Field(default=0.0, ge=0, description="Rain rate (mm/hour)")
    grazing_angle_deg: float | None = Field(
        default=None,
        ge=0.1,
        le=90,
        description="Grazing angle (deg). If None, computed from geometry.",
    )
    antenna_height_m: float = Field(
        default=10.0, ge=0, description="Antenna height above surface (m)"
    )
    target_height_m: float = Field(default=0.0, ge=0, description="Target height above surface (m)")
    polarization: PolarizationType = Field(default="HH", description="Antenna polarization")

    # CFAR parameters
    cfar_type: CFARType = Field(default="none", description="CFAR detector type")
    cfar_ref_cells: int = Field(default=16, ge=2, description="Number of CFAR reference cells")
    cfar_guard_cells: int = Field(
        default=2, ge=0, description="Number of CFAR guard cells per side"
    )

    # Propagation parameters
    include_atmos_loss: bool = Field(default=False, description="Include atmospheric attenuation")
    temperature_c: float = Field(default=15.0, description="Ambient temperature (Celsius)")
    humidity_pct: float = Field(default=50.0, ge=0, le=100, description="Relative humidity (%)")

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

    @computed_field  # type: ignore[prop-decorator]
    @property
    def range_resolution_m(self) -> float:
        """Range resolution in meters (c / 2B)."""
        return C_LIGHT / (2 * self.bandwidth_hz)
