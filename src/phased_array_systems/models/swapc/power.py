"""Power consumption models for phased array systems."""

from typing import Any

from phased_array_systems.architecture import Architecture
from phased_array_systems.types import MetricsDict, Scenario


class PowerModel:
    """Power consumption calculator for phased array systems.

    Computes DC power, RF power, and prime power based on
    architecture parameters and efficiency factors.

    Power Equations:
        RF_peak = n_elements * tx_power_per_elem
        RF_avg = RF_peak * duty_cycle
        PA_DC = RF_avg / pa_efficiency
        RX_DC = n_elements * rx_power_w_per_elem
        ADC = n_digital_channels * FOM * 2^ENOB * fs
        DSP = beamformer_GOPS / dsp_efficiency
        DC_power = PA_DC + RX_DC + ADC + DSP
        Prime_power = DC_power * (1 + overhead_factor)

    Attributes:
        name: Model block name for identification
        overhead_factor: Additional power overhead (cooling, control, etc.)
    """

    name: str = "power"

    def __init__(self, overhead_factor: float = 0.2):
        """Initialize power model.

        Args:
            overhead_factor: Fraction of DC power for overhead (default 20%)
        """
        self.overhead_factor = overhead_factor

    def evaluate(
        self,
        arch: Architecture,
        scenario: Scenario,
        context: dict[str, Any],
    ) -> MetricsDict:
        """Evaluate power metrics.

        Args:
            arch: Architecture configuration
            scenario: Scenario (duty_cycle and bandwidth_hz are read if present)
            context: Additional context (unused)

        Returns:
            Dictionary with power metrics:
                - rf_power_w: Peak RF output power (W)
                - rf_avg_power_w: Average RF output power (W)
                - pa_dc_power_w: PA DC power (W)
                - rx_dc_power_w: Receive chain DC power (W)
                - adc_power_w: Total ADC power (W)
                - dsp_power_w: Digital beamformer power (W)
                - dc_power_w: Total DC power consumption (W)
                - prime_power_w: Prime/wall power (W)
                - duty_cycle: Transmit duty cycle
                - pa_efficiency: Power amplifier efficiency
                - n_elements: Number of array elements
        """
        n_elements = arch.array.n_elements
        tx_power_per_elem = arch.rf.tx_power_w_per_elem
        pa_efficiency = arch.rf.pa_efficiency
        duty_cycle = getattr(scenario, "duty_cycle", 1.0)

        # RF power: peak for the radar equation, average for the DC budget
        rf_power_w = n_elements * tx_power_per_elem
        rf_avg_power_w = rf_power_w * duty_cycle

        # PA DC power (accounting for PA efficiency)
        pa_dc_power_w = rf_avg_power_w / pa_efficiency

        # Receive chain DC power (LNA, phase shifter, control per element)
        rx_dc_power_w = n_elements * arch.rf.rx_power_w_per_elem

        # Digital section power (ADCs + beamformer compute)
        adc_power = 0.0
        dsp_power = 0.0
        if arch.digital is not None:
            from phased_array_systems.models.digital.bandwidth import beamformer_operations
            from phased_array_systems.models.digital.converters import adc_power_w

            bandwidth_hz = getattr(scenario, "bandwidth_hz", 1e6)
            sample_rate_hz = bandwidth_hz * arch.digital.oversampling_ratio
            n_channels = arch.n_digital_channels

            adc_power = n_channels * adc_power_w(
                arch.digital.adc_enob, sample_rate_hz, arch.digital.adc_fom_fj
            )
            ops = beamformer_operations(n_channels, arch.digital.n_beams, sample_rate_hz)
            dsp_power = ops["total_gops"] / arch.digital.dsp_efficiency_gops_per_w

        dc_power_w = pa_dc_power_w + rx_dc_power_w + adc_power + dsp_power

        # Prime power (including overhead)
        prime_power_w = dc_power_w * (1 + self.overhead_factor)

        return {
            "rf_power_w": rf_power_w,
            "rf_avg_power_w": rf_avg_power_w,
            "pa_dc_power_w": pa_dc_power_w,
            "rx_dc_power_w": rx_dc_power_w,
            "adc_power_w": adc_power,
            "dsp_power_w": dsp_power,
            "dc_power_w": dc_power_w,
            "prime_power_w": prime_power_w,
            "duty_cycle": duty_cycle,
            "pa_efficiency": pa_efficiency,
            "n_elements": n_elements,
        }


def compute_thermal_load(
    dc_power_w: float,
    rf_power_w: float,
    additional_dissipation_w: float = 0.0,
) -> dict[str, float]:
    """Compute thermal dissipation for heat management.

    Args:
        dc_power_w: Total DC power consumption (W)
        rf_power_w: RF power radiated (W)
        additional_dissipation_w: Other heat sources (W)

    Returns:
        Dictionary with thermal metrics:
            - heat_dissipation_w: Total heat to remove (W)
            - rf_efficiency: Fraction of DC converted to RF
    """
    # Heat = DC input - RF output + additional sources
    heat_dissipation_w = dc_power_w - rf_power_w + additional_dissipation_w
    rf_efficiency = rf_power_w / dc_power_w if dc_power_w > 0 else 0.0

    return {
        "heat_dissipation_w": heat_dissipation_w,
        "rf_efficiency": rf_efficiency,
    }
