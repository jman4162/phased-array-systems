"""Architecture configuration models using Pydantic."""

import math
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

# Valid power-of-two values for sub-array dimensions
VALID_POWERS_OF_TWO = [2**i for i in range(1, 10)]  # 2, 4, 8, 16, 32, 64, 128, 256, 512


def is_power_of_two(n: int) -> bool:
    """Check if n is a power of two (and >= 2)."""
    return n >= 2 and (n & (n - 1)) == 0


class ArrayConfig(BaseModel):
    """Configuration for the antenna array geometry.

    Attributes:
        geometry: Array geometry type
        nx: Number of elements in x-direction
        ny: Number of elements in y-direction
        dx_lambda: Element spacing in x-direction (wavelengths)
        dy_lambda: Element spacing in y-direction (wavelengths)
        scan_limit_deg: Maximum scan angle from boresight (degrees)
        max_subarray_nx: Maximum elements per sub-array in x (must be power of 2)
        max_subarray_ny: Maximum elements per sub-array in y (must be power of 2)
        enforce_subarray_constraint: Whether to enforce power-of-two sub-array constraint
    """

    geometry: Literal["rectangular", "circular", "triangular"] = "rectangular"
    nx: int = Field(ge=1, description="Number of elements in x-direction")
    ny: int = Field(ge=1, description="Number of elements in y-direction")
    dx_lambda: float = Field(default=0.5, gt=0, description="Element spacing in x (wavelengths)")
    dy_lambda: float = Field(default=0.5, gt=0, description="Element spacing in y (wavelengths)")
    scan_limit_deg: float = Field(
        default=60.0, ge=0, le=90, description="Maximum scan angle (degrees)"
    )

    # Sub-array constraints for practical RF component design (power-of-two)
    max_subarray_nx: int = Field(
        default=8, ge=2, description="Max elements per sub-array in x (must be power of 2)"
    )
    max_subarray_ny: int = Field(
        default=8, ge=2, description="Max elements per sub-array in y (must be power of 2)"
    )
    enforce_subarray_constraint: bool = Field(
        default=True, description="Enforce power-of-two sub-array constraint"
    )

    # Taper configuration
    taper_type: Literal["uniform", "taylor", "chebyshev", "hamming", "cosine", "gaussian"] = Field(
        default="uniform", description="Amplitude taper type"
    )
    taper_sll_db: float = Field(
        default=-30.0, le=-10, description="Target SLL for taper (dB, negative)"
    )

    # Element pattern configuration
    element_cos_exp: float = Field(
        default=1.5, ge=0, description="Cosine exponent for element pattern (0=isotropic)"
    )

    # Impairments
    phase_bits: int | None = Field(
        default=None, ge=1, le=16, description="Phase shifter quantization bits (None=ideal)"
    )

    @field_validator("max_subarray_nx", "max_subarray_ny")
    @classmethod
    def validate_power_of_two(cls, v: int) -> int:
        """Validate that max sub-array dimensions are powers of two."""
        if not is_power_of_two(v):
            raise ValueError(
                f"max_subarray value {v} must be a power of 2 (valid values: {VALID_POWERS_OF_TWO})"
            )
        return v

    @model_validator(mode="after")
    def validate_subarray_constraints(self) -> "ArrayConfig":
        """Validate that array dimensions result in power-of-two sub-arrays."""
        if not self.enforce_subarray_constraint:
            return self

        if self.geometry != "rectangular":
            # Sub-array constraints only apply to rectangular arrays for now
            return self

        # Check x-direction
        if self.nx > self.max_subarray_nx:
            # Must be divisible by max_subarray_nx
            if self.nx % self.max_subarray_nx != 0:
                raise ValueError(
                    f"nx={self.nx} must be divisible by max_subarray_nx={self.max_subarray_nx} "
                    f"for arrays larger than max sub-array size. "
                    f"Set enforce_subarray_constraint=False to disable."
                )
        else:
            # Small array: nx itself must be power of two
            if not is_power_of_two(self.nx):
                raise ValueError(
                    f"nx={self.nx} must be a power of 2 (2, 4, 8, 16, ...) when "
                    f"enforce_subarray_constraint=True. Valid values: {VALID_POWERS_OF_TWO}"
                )

        # Check y-direction
        if self.ny > self.max_subarray_ny:
            # Must be divisible by max_subarray_ny
            if self.ny % self.max_subarray_ny != 0:
                raise ValueError(
                    f"ny={self.ny} must be divisible by max_subarray_ny={self.max_subarray_ny} "
                    f"for arrays larger than max sub-array size. "
                    f"Set enforce_subarray_constraint=False to disable."
                )
        else:
            # Small array: ny itself must be power of two
            if not is_power_of_two(self.ny):
                raise ValueError(
                    f"ny={self.ny} must be a power of 2 (2, 4, 8, 16, ...) when "
                    f"enforce_subarray_constraint=True. Valid values: {VALID_POWERS_OF_TWO}"
                )

        return self

    @property
    def n_elements(self) -> int:
        """Total number of elements in the array."""
        return self.nx * self.ny

    @property
    def subarray_nx(self) -> int:
        """Actual elements per sub-array in x-direction."""
        if self.nx <= self.max_subarray_nx:
            return self.nx
        return self.max_subarray_nx

    @property
    def subarray_ny(self) -> int:
        """Actual elements per sub-array in y-direction."""
        if self.ny <= self.max_subarray_ny:
            return self.ny
        return self.max_subarray_ny

    @property
    def n_subarrays_x(self) -> int:
        """Number of sub-arrays in x-direction."""
        return math.ceil(self.nx / self.max_subarray_nx)

    @property
    def n_subarrays_y(self) -> int:
        """Number of sub-arrays in y-direction."""
        return math.ceil(self.ny / self.max_subarray_ny)

    @property
    def n_subarrays(self) -> int:
        """Total number of sub-arrays."""
        return self.n_subarrays_x * self.n_subarrays_y

    @property
    def elements_per_subarray(self) -> int:
        """Number of elements per sub-array."""
        return self.subarray_nx * self.subarray_ny


class RFChainConfig(BaseModel):
    """Configuration for the RF chain.

    Attributes:
        tx_power_w_per_elem: Transmit power per element (Watts)
        pa_efficiency: Power amplifier efficiency (0-1)
        noise_figure_db: Receiver noise figure (dB)
        n_tx_beams: Number of simultaneous transmit beams
        feed_loss_db: Feed network loss (dB)
        system_loss_db: Additional system losses (dB)
    """

    tx_power_w_per_elem: float = Field(gt=0, description="TX power per element (W)")
    pa_efficiency: float = Field(default=0.3, gt=0, le=1, description="PA efficiency (0-1)")
    noise_figure_db: float = Field(default=3.0, ge=0, description="Noise figure (dB)")
    n_tx_beams: int = Field(default=1, ge=1, description="Number of TX beams")
    feed_loss_db: float = Field(default=1.0, ge=0, description="Feed network loss (dB)")
    system_loss_db: float = Field(default=0.0, ge=0, description="Additional system losses (dB)")
    rx_stages: list[dict[str, float | str]] | None = Field(
        default=None,
        description="RX chain stages: list of {name, gain_db, nf_db, iip3_dbm, p1db_dbm}",
    )

    @field_validator("pa_efficiency")
    @classmethod
    def validate_efficiency(cls, v: float) -> float:
        if not 0 < v <= 1:
            raise ValueError("PA efficiency must be between 0 and 1")
        return v


class CostConfig(BaseModel):
    """Configuration for cost modeling.

    Attributes:
        cost_per_elem_usd: Recurring cost per element (USD)
        nre_usd: Non-recurring engineering cost (USD)
        integration_cost_usd: System integration cost (USD)
    """

    cost_per_elem_usd: float = Field(default=100.0, ge=0, description="Cost per element (USD)")
    nre_usd: float = Field(default=0.0, ge=0, description="NRE cost (USD)")
    integration_cost_usd: float = Field(default=0.0, ge=0, description="Integration cost (USD)")


class ReliabilityConfig(BaseModel):
    """Configuration for reliability analysis.

    Attributes:
        component_mtbfs: Component name -> MTBF hours
        operating_temp_c: Operating junction temperature (Celsius)
        mttr_hours: Mean time to repair (hours)
        mission_hours: Mission duration (hours)
    """

    component_mtbfs: dict[str, float] = Field(
        default_factory=lambda: {
            "lna": 500_000,
            "pa": 250_000,
            "phase_shifter": 2_000_000,
            "attenuator": 3_000_000,
            "switch": 1_000_000,
            "control_asic": 1_000_000,
        },
        description="Component name -> MTBF hours",
    )
    operating_temp_c: float = Field(default=85.0, description="Operating temperature (C)")
    mttr_hours: float = Field(default=8.0, ge=0, description="Mean time to repair (hours)")
    mission_hours: float = Field(default=8760.0, gt=0, description="Mission duration (hours)")


class DigitalConfig(BaseModel):
    """Configuration for digital beamformer constraints.

    Attributes:
        adc_enob: ADC effective number of bits
        oversampling_ratio: ADC oversampling ratio
        n_beams: Number of simultaneous digital beams
        fpga_throughput_gops: Available FPGA throughput (GOPS); None=skip margin calc
    """

    adc_enob: float = Field(default=12.0, ge=4, le=18, description="ADC effective number of bits")
    oversampling_ratio: float = Field(default=2.5, ge=2.0, description="ADC oversampling ratio")
    n_beams: int = Field(default=1, ge=1, description="Simultaneous digital beams")
    fpga_throughput_gops: float | None = Field(
        default=None, ge=0, description="Available FPGA throughput (GOPS); None=skip margin calc"
    )


class Architecture(BaseModel):
    """Complete system architecture configuration.

    This is the top-level configuration object that contains all
    subsystem configurations.

    Attributes:
        array: Antenna array configuration
        rf: RF chain configuration
        cost: Cost model configuration
        name: Optional name for this architecture
    """

    array: ArrayConfig
    rf: RFChainConfig
    cost: CostConfig = Field(default_factory=CostConfig)
    reliability: ReliabilityConfig | None = Field(
        default=None, description="Reliability analysis configuration"
    )
    digital: DigitalConfig | None = Field(
        default=None, description="Digital beamformer configuration"
    )
    name: str | None = Field(default=None, description="Architecture name")

    @property
    def n_elements(self) -> int:
        """Total number of elements (convenience property)."""
        return self.array.n_elements

    def model_dump_flat(self) -> dict:
        """Return a flattened dictionary of all configuration values.

        Useful for DOE case generation where we need flat parameter names.
        """
        flat = {}
        configs: list[tuple[str, BaseModel]] = [
            ("array", self.array),
            ("rf", self.rf),
            ("cost", self.cost),
        ]
        if self.reliability is not None:
            configs.append(("reliability", self.reliability))
        if self.digital is not None:
            configs.append(("digital", self.digital))
        for prefix, config in configs:
            for key, value in config.model_dump().items():
                flat[f"{prefix}.{key}"] = value
        if self.name:
            flat["name"] = self.name
        return flat

    @classmethod
    def from_flat(cls, flat_dict: dict) -> "Architecture":
        """Create an Architecture from a flattened dictionary.

        Args:
            flat_dict: Dictionary with keys like "array.nx", "rf.tx_power_w_per_elem"

        Returns:
            Architecture instance
        """
        array_dict = {}
        rf_dict = {}
        cost_dict = {}
        reliability_dict = {}
        digital_dict = {}
        name = None

        for key, value in flat_dict.items():
            if key == "name":
                name = value
            elif key.startswith("array."):
                array_dict[key.replace("array.", "")] = value
            elif key.startswith("rf."):
                rf_dict[key.replace("rf.", "")] = value
            elif key.startswith("cost."):
                cost_dict[key.replace("cost.", "")] = value
            elif key.startswith("reliability."):
                reliability_dict[key.replace("reliability.", "")] = value
            elif key.startswith("digital."):
                digital_dict[key.replace("digital.", "")] = value

        return cls(
            array=ArrayConfig(**array_dict),
            rf=RFChainConfig(**rf_dict),
            cost=CostConfig(**cost_dict) if cost_dict else CostConfig(),
            reliability=ReliabilityConfig(**reliability_dict) if reliability_dict else None,
            digital=DigitalConfig(**digital_dict) if digital_dict else None,
            name=name,
        )
