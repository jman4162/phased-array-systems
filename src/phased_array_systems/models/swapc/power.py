"""Power consumption and aperture power-density models for phased arrays."""

from typing import Any

from phased_array_systems.architecture import Architecture
from phased_array_systems.constants import C
from phased_array_systems.types import MetricsDict, Scenario


def aperture_geometry(arch: Architecture, scenario: Scenario) -> dict[str, float]:
    """Physical unit-cell and aperture areas from the lambda-normalized lattice.

    ``ArrayConfig`` stores spacing in wavelengths and carries no frequency, so
    the physical scale comes from the scenario. The radiating aperture is
    N*d per axis (each element owns a full cell), not the (N-1)*d tip-to-tip
    extent of the element centres.

    At half-wave spacing the cell is (lambda/2)^2, so cell area falls as
    1/f^2: at fixed per-element dissipation, aperture heat flux rises as f^2.
    That scaling is the reason these quantities matter, and it is asserted in
    tests/test_aperture_density.py.

    Returns:
        Dictionary with cell_area_m2, cell_area_cm2, aperture_area_m2,
        aperture_area_cm2, wavelength_m.
    """
    freq_hz = float(getattr(scenario, "freq_hz", 0.0))
    if freq_hz <= 0:
        raise ValueError("scenario must define a positive freq_hz for aperture geometry")
    wavelength_m = C / freq_hz
    cell_area_m2 = arch.array.dx_lambda * arch.array.dy_lambda * wavelength_m**2
    aperture_area_m2 = cell_area_m2 * arch.array.n_elements
    return {
        "wavelength_m": wavelength_m,
        "cell_area_m2": cell_area_m2,
        "cell_area_cm2": cell_area_m2 * 1e4,
        "aperture_area_m2": aperture_area_m2,
        "aperture_area_cm2": aperture_area_m2 * 1e4,
    }


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
                - heat_dissipation_w: Heat to remove (DC in minus RF out)
            When the scenario carries a frequency, also:
                - wavelength_m, cell_area_cm2, aperture_area_m2
                - heat_flux_w_per_cm2: dissipation per aperture area (average)
                - radiated_power_density_peak_w_per_cm2
                - radiated_power_density_avg_w_per_cm2
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

        # Digital section power (ADCs + DACs + beamformer compute)
        adc_power = 0.0
        dac_power = 0.0
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
            if arch.digital.dac_enob is not None:
                # Walden-form estimate applied to the DAC; same caveats as
                # for the ADC (survey-level scaling, not a datasheet number)
                dac_power = n_channels * adc_power_w(
                    arch.digital.dac_enob, sample_rate_hz, arch.digital.dac_fom_fj
                )
            ops = beamformer_operations(n_channels, arch.digital.n_beams, sample_rate_hz)
            dsp_power = ops["total_gops"] / arch.digital.dsp_efficiency_gops_per_w

        dc_power_w = pa_dc_power_w + rx_dc_power_w + adc_power + dac_power + dsp_power

        # Prime power (including overhead)
        prime_power_w = dc_power_w * (1 + self.overhead_factor)

        # Heat to remove, from the single shared energy balance. The average
        # RF term is the right one here: what leaves as radiation over a
        # duty cycle does not heat the array.
        thermal = compute_thermal_load(dc_power_w, rf_avg_power_w)

        # Aperture power densities. Heat flux uses AVERAGE power because the
        # cold plate's time constant (seconds) is far longer than the PRI
        # (microseconds), so the plate sees the duty-cycle-averaged load.
        # The junction does not average that way; PAS has no thermal
        # transient model and does not claim a peak junction flux.
        density: dict[str, float] = {}
        try:
            geom = aperture_geometry(arch, scenario)
        except ValueError:
            geom = {}
        if geom:
            aperture_cm2 = geom["aperture_area_cm2"]
            density = {
                "wavelength_m": geom["wavelength_m"],
                "cell_area_cm2": geom["cell_area_cm2"],
                "aperture_area_m2": geom["aperture_area_m2"],
                "heat_flux_w_per_cm2": thermal["heat_dissipation_w"] / aperture_cm2,
                "radiated_power_density_peak_w_per_cm2": rf_power_w / aperture_cm2,
                "radiated_power_density_avg_w_per_cm2": rf_avg_power_w / aperture_cm2,
            }

        return {
            "rf_power_w": rf_power_w,
            "rf_avg_power_w": rf_avg_power_w,
            "pa_dc_power_w": pa_dc_power_w,
            "rx_dc_power_w": rx_dc_power_w,
            "adc_power_w": adc_power,
            "dac_power_w": dac_power,
            "dsp_power_w": dsp_power,
            "dc_power_w": dc_power_w,
            "prime_power_w": prime_power_w,
            "duty_cycle": duty_cycle,
            "pa_efficiency": pa_efficiency,
            "n_elements": n_elements,
            "heat_dissipation_w": thermal["heat_dissipation_w"],
            **density,
        }


def compute_thermal_load(
    dc_power_w: float,
    rf_power_w: float,
    additional_dissipation_w: float = 0.0,
) -> dict[str, float]:
    """Compute thermal dissipation for heat management.

    The single energy balance in the package: ``PowerModel`` calls it for
    ``heat_dissipation_w``, and the junction-temperature feed-forward in
    ``evaluate`` consumes that metric rather than recomputing it.

    Args:
        dc_power_w: Total DC power consumption (W)
        rf_power_w: RF power leaving as radiation (W). Pass the duty-cycle
            average for a thermal budget; passing peak overstates the
            radiated fraction and understates the heat.
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
