"""Base scenario class and utilities."""

from pydantic import BaseModel, ConfigDict, Field

from phased_array_systems.constants import C


class ScenarioBase(BaseModel):
    """Base class for all scenario types.

    All scenarios must have a frequency, which is used to compute
    wavelength and other frequency-dependent parameters.

    Attributes:
        freq_hz: Operating frequency in Hz
        name: Optional name for the scenario
    """

    # Reject unknown fields rather than silently dropping them. A misspelled or
    # relocated parameter (system_loss_db belongs on RFChainConfig, not here)
    # otherwise vanishes without warning and the run reports physics the user
    # did not ask for.
    model_config = ConfigDict(extra="forbid")

    freq_hz: float = Field(gt=0, description="Operating frequency (Hz)")
    name: str | None = Field(default=None, description="Scenario name")

    @property
    def wavelength_m(self) -> float:
        """Wavelength in meters."""
        return C / self.freq_hz

    @property
    def freq_ghz(self) -> float:
        """Frequency in GHz."""
        return self.freq_hz / 1e9
