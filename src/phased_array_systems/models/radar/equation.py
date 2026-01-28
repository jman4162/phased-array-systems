"""Radar range equation model."""

from __future__ import annotations

import math
from typing import Any

from phased_array_systems.architecture import Architecture
from phased_array_systems.constants import C_LIGHT, K_B, W_TO_DBW
from phased_array_systems.models.radar.detection import albersheim_snr, compute_pd_from_snr
from phased_array_systems.models.radar.integration import (
    coherent_integration_gain,
    noncoherent_integration_gain,
)
from phased_array_systems.scenarios import RadarDetectionScenario
from phased_array_systems.types import MetricsDict


class RadarModel:
    """Radar range equation calculator.

    Implements the monostatic radar range equation:

        P_r = (P_t * G^2 * λ^2 * σ) / ((4π)^3 * R^4 * L_sys)

    Or in dB form:
        SNR = P_t + 2*G + 2*λ_dB + σ_dBsm - 4*R_dB - L_sys - (4π)^3_dB - N_dB

    Where:
        P_t = Peak transmit power (W)
        G = Antenna gain (same for Tx/Rx in monostatic)
        λ = Wavelength (m)
        σ = Target radar cross section (m^2)
        R = Range to target (m)
        L_sys = System losses
        N = Noise power = kTB

    Attributes:
        name: Model block name for identification
    """

    name: str = "radar"

    def evaluate(
        self,
        arch: Architecture,
        scenario: RadarDetectionScenario,
        context: dict[str, Any],
    ) -> MetricsDict:
        """Evaluate radar detection performance.

        Args:
            arch: Architecture configuration
            scenario: Radar detection scenario
            context: Additional context (may include antenna metrics):
                - g_peak_db: Antenna gain (uses this if provided)
                - scan_loss_db: Scan loss (uses this if provided)

        Returns:
            Dictionary with radar metrics:
                - peak_power_w: Peak transmit power (W)
                - peak_power_dbw: Peak transmit power (dBW)
                - g_ant_db: Antenna gain (dB)
                - wavelength_m: Wavelength (m)
                - target_rcs_dbsm: Target RCS (dBsm)
                - target_rcs_m2: Target RCS (m^2)
                - range_m: Target range (m)
                - noise_power_dbw: Noise power (dBW)
                - snr_single_pulse_db: Single-pulse SNR (dB)
                - integration_gain_db: Integration gain (dB)
                - snr_integrated_db: Integrated SNR (dB)
                - snr_required_db: Required SNR for Pd/Pfa (dB)
                - snr_margin_db: SNR margin (dB)
                - pd_achieved: Achieved probability of detection
                - detection_range_m: Max detection range for required Pd (m)
        """
        # Get antenna gain from context or compute approximate
        if "g_peak_db" in context:
            g_ant_db = context["g_peak_db"]
            # Apply scan loss if provided
            if "scan_loss_db" in context:
                g_ant_db -= context["scan_loss_db"]
        else:
            # Approximate gain for uniform rectangular array
            # G ≈ 4*pi*A/λ^2 = 4*pi * (nx*dx) * (ny*dy) when spacing in wavelengths
            aperture_lambda_sq = (
                arch.array.nx * arch.array.dx_lambda * arch.array.ny * arch.array.dy_lambda
            )
            g_ant_linear = 4 * math.pi * aperture_lambda_sq
            g_ant_db = 10 * math.log10(g_ant_linear)

        # Transmit power (peak)
        n_elements = arch.array.n_elements
        peak_power_w = arch.rf.tx_power_w_per_elem * n_elements
        peak_power_dbw = W_TO_DBW(peak_power_w)

        # Wavelength
        wavelength_m = C_LIGHT / scenario.freq_hz
        wavelength_db = 10 * math.log10(wavelength_m)

        # System losses (feed network + additional system losses)
        system_loss_db = arch.rf.feed_loss_db + arch.rf.system_loss_db

        # Target RCS
        rcs_dbsm = scenario.target_rcs_dbsm
        rcs_m2 = 10 ** (rcs_dbsm / 10)

        # Range
        range_m = scenario.range_m
        range_db = 10 * math.log10(range_m)

        # Noise power: N = kTB
        noise_temp_k = scenario.rx_noise_temp_k
        noise_power_w = K_B * noise_temp_k * scenario.bandwidth_hz
        noise_power_dbw = W_TO_DBW(noise_power_w) + arch.rf.noise_figure_db

        # Radar equation constant: (4π)^3 in dB
        radar_constant_db = 30 * math.log10(4 * math.pi)  # ≈ 32.98 dB

        # Single-pulse SNR (monostatic radar equation in dB)
        # SNR = Pt + 2*G + 2*λ_dB + σ - 4*R_dB - L - (4π)^3_dB - N
        snr_single_db = (
            peak_power_dbw
            + 2 * g_ant_db
            + 2 * wavelength_db
            + rcs_dbsm
            - 4 * range_db
            - system_loss_db
            - radar_constant_db
            - noise_power_dbw
        )

        # Integration gain
        n_pulses = scenario.n_pulses
        if scenario.integration_type == "coherent":
            integration_gain_db = coherent_integration_gain(n_pulses)
        else:
            integration_gain_db = noncoherent_integration_gain(
                n_pulses, pd=scenario.pd_required, pfa=scenario.pfa
            )

        # Integrated SNR
        snr_integrated_db = snr_single_db + integration_gain_db

        # Required SNR for Pd/Pfa using Albersheim's equation
        snr_required_db = albersheim_snr(
            pd=scenario.pd_required,
            pfa=scenario.pfa,
            n_pulses=1,  # Integration gain already applied
        )

        # SNR margin
        snr_margin_db = snr_integrated_db - snr_required_db

        # Achieved Pd at the given range
        pd_achieved = compute_pd_from_snr(
            snr_integrated_db,
            scenario.pfa,
            swerling=0,  # Non-fluctuating
            n_pulses=1,  # Already integrated
            integration="coherent",  # SNR already includes integration
        )

        # Detection range (range where margin = 0)
        # From radar equation: R^4 proportional to SNR
        # R_det / R = (SNR_integrated / SNR_required)^(1/4)
        # In dB: R_det = R * 10^(margin_dB / 40)
        detection_range_m = range_m * 10 ** (snr_margin_db / 40) if snr_margin_db > -40 else 0.0

        return {
            # Power
            "peak_power_w": peak_power_w,
            "peak_power_dbw": peak_power_dbw,
            # Antenna
            "g_ant_db": g_ant_db,
            # Target/Environment
            "wavelength_m": wavelength_m,
            "target_rcs_dbsm": rcs_dbsm,
            "target_rcs_m2": rcs_m2,
            "range_m": range_m,
            # Noise
            "noise_power_dbw": noise_power_dbw,
            "system_loss_db": system_loss_db,
            # SNR
            "snr_single_pulse_db": snr_single_db,
            "integration_gain_db": integration_gain_db,
            "snr_integrated_db": snr_integrated_db,
            "snr_required_db": snr_required_db,
            "snr_margin_db": snr_margin_db,
            # Detection
            "pd_achieved": pd_achieved,
            "pd_required": scenario.pd_required,
            "pfa": scenario.pfa,
            "n_pulses": n_pulses,
            "integration_type": scenario.integration_type,
            "detection_range_m": detection_range_m,
        }


def compute_detection_range(
    peak_power_w: float,
    g_ant_db: float,
    freq_hz: float,
    rcs_dbsm: float,
    noise_temp_k: float,
    bandwidth_hz: float,
    noise_figure_db: float,
    system_loss_db: float,
    snr_required_db: float,
) -> float:
    """Compute maximum detection range from radar parameters.

    Standalone function for quick range calculations without
    full Architecture/Scenario objects.

    Args:
        peak_power_w: Peak transmit power (W)
        g_ant_db: Antenna gain (dB)
        freq_hz: Operating frequency (Hz)
        rcs_dbsm: Target RCS (dBsm)
        noise_temp_k: System noise temperature (K)
        bandwidth_hz: Receiver bandwidth (Hz)
        noise_figure_db: Receiver noise figure (dB)
        system_loss_db: Total system losses (dB)
        snr_required_db: Required SNR for detection (dB)

    Returns:
        Maximum detection range in meters
    """
    # Convert to dB
    pt_dbw = W_TO_DBW(peak_power_w)
    wavelength_m = C_LIGHT / freq_hz
    wavelength_db = 10 * math.log10(wavelength_m)
    noise_power_w = K_B * noise_temp_k * bandwidth_hz
    noise_power_dbw = W_TO_DBW(noise_power_w) + noise_figure_db
    radar_constant_db = 30 * math.log10(4 * math.pi)

    # Solve for range: 4*R_dB = Pt + 2*G + 2*λ_dB + σ - L - const - N - SNR_req
    four_r_db = (
        pt_dbw
        + 2 * g_ant_db
        + 2 * wavelength_db
        + rcs_dbsm
        - system_loss_db
        - radar_constant_db
        - noise_power_dbw
        - snr_required_db
    )

    r_db = four_r_db / 4
    range_m = 10 ** (r_db / 10)

    return range_m
