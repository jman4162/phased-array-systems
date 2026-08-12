"""Communications link budget model."""

import math
from typing import Any

from phased_array_systems.architecture import Architecture
from phased_array_systems.constants import K_B, W_TO_DBW
from phased_array_systems.models.comms.propagation import (
    compute_atmospheric_loss,
    compute_fspl,
    compute_log_distance_path_loss,
    compute_rain_loss,
    compute_two_ray_path_loss,
)
from phased_array_systems.scenarios import CommsLinkScenario
from phased_array_systems.types import MetricsDict


class CommsLinkModel:
    """Communications link budget calculator.

    Computes EIRP, received power, noise power, SNR, and link margin
    for a point-to-point or satellite communications link.

    Link Budget Equations:
        EIRP = P_tx_total + G_tx - L_tx
        P_rx = EIRP - L_path + G_rx
        N = 10*log10(k*T*B) + NF
        SNR = P_rx - N
        Margin = SNR - required_SNR

    Attributes:
        name: Model block name for identification
    """

    name: str = "comms_link"

    def evaluate(
        self,
        arch: Architecture,
        scenario: CommsLinkScenario,
        context: dict[str, Any],
    ) -> MetricsDict:
        """Evaluate communications link budget.

        Args:
            arch: Architecture configuration
            scenario: Communications link scenario
            context: Additional context, may include antenna metrics:
                - g_peak_db: Antenna gain (uses this if provided)
                - scan_loss_db: Scan loss (uses this if provided)

        Returns:
            Dictionary with link budget metrics:
                - tx_power_total_dbw: Total transmit power (dBW)
                - tx_power_per_elem_dbw: TX power per element (dBW)
                - g_tx_db: Transmit antenna gain (dB)
                - eirp_dbw: Effective Isotropic Radiated Power (dBW)
                - path_loss_db: Total path loss (dB)
                - g_rx_db: Receive antenna gain (dB)
                - rx_power_dbw: Received power (dBW)
                - noise_power_dbw: Noise power (dBW)
                - snr_rx_db: Received SNR (dB)
                - link_margin_db: Link margin (dB)
        """
        # Get transmit power. Commanded power backs off by the waveform's
        # tx_backoff_db, then compresses through the Rapp soft limiter when a
        # per-element PA P1dB is configured; both default off.
        n_elements = arch.array.n_elements
        tx_power_per_elem_w = arch.rf.tx_power_w_per_elem
        tx_power_per_elem_dbm = W_TO_DBW(tx_power_per_elem_w) + 30.0 - scenario.tx_backoff_db
        pa_compression_db = 0.0
        if arch.rf.pa_op1db_dbm_per_elem is not None:
            from phased_array_systems.models.rf.cascade import rapp_compression_db

            # The configured op1db is output-referred for a unity-drive
            # bookkeeping chain, so compare delivered power directly.
            pa_compression_db = rapp_compression_db(
                tx_power_per_elem_dbm,
                arch.rf.pa_op1db_dbm_per_elem,
                smoothness=arch.rf.pa_compression_smoothness,
            )
        tx_power_per_elem_dbw = tx_power_per_elem_dbm - 30.0 - pa_compression_db
        tx_power_total_dbw = tx_power_per_elem_dbw + 10.0 * math.log10(n_elements)

        # Get antenna gain from context or compute approximate
        if "g_peak_db" in context:
            g_tx_db = context["g_peak_db"]
        else:
            # Approximate gain for uniform array
            # G = 4*pi*A/lambda^2 ≈ pi * nx * dx * ny * dy * 4
            aperture_area_lambda_sq = (
                arch.array.nx * arch.array.dx_lambda * arch.array.ny * arch.array.dy_lambda
            )
            g_tx_linear = 4 * math.pi * aperture_area_lambda_sq
            g_tx_db = 10 * math.log10(g_tx_linear)

            # Apply scan loss if provided
            if "scan_loss_db" in context:
                g_tx_db -= context["scan_loss_db"]

        # Transmit losses (feed network + system)
        tx_loss_db = arch.rf.feed_loss_db + arch.rf.system_loss_db

        # EIRP
        eirp_dbw = tx_power_total_dbw + g_tx_db - tx_loss_db

        # Path loss (core propagation model)
        if scenario.path_loss_model == "fspl":
            path_loss_db = compute_fspl(scenario.freq_hz, scenario.range_m)
        elif scenario.path_loss_model == "log_distance":
            path_loss_db = compute_log_distance_path_loss(
                scenario.freq_hz,
                scenario.range_m,
                n=scenario.path_loss_exponent,
            )
        elif scenario.path_loss_model == "two_ray":
            # Two-ray requires TX/RX heights; use defaults if not available
            h_tx = getattr(scenario, "h_tx_m", 10.0)
            h_rx = getattr(scenario, "h_rx_m", 2.0)
            path_loss_db = compute_two_ray_path_loss(
                scenario.freq_hz,
                scenario.range_m,
                h_tx,
                h_rx,
            )
        else:
            raise ValueError(f"Unknown path loss model: {scenario.path_loss_model}")

        # Computed atmospheric and rain losses
        atmo_loss_db = compute_atmospheric_loss(
            scenario.freq_hz,
            scenario.range_m,
            elevation_deg=scenario.elevation_deg,
        )
        rain_computed_db = compute_rain_loss(
            scenario.freq_hz,
            scenario.range_m,
            rain_rate_mmh=scenario.rain_rate_mmh,
        )

        # Total losses: computed propagation + computed atmo/rain + manual overrides
        total_path_loss_db = (
            path_loss_db + atmo_loss_db + rain_computed_db + scenario.total_extra_loss_db
        )

        # Receive antenna gain (isotropic if not specified)
        g_rx_db = scenario.rx_antenna_gain_db if scenario.rx_antenna_gain_db is not None else 0.0

        # Received power
        rx_power_dbw = eirp_dbw - total_path_loss_db + g_rx_db

        # Noise convention: rx_noise_temp_k is the ANTENNA temperature.
        # T_sys = T_ant + T0*(F-1) with the noise figure referenced to
        # T0 = 290 K; N = k*T_sys*B. (Cascaded NF from context wins over
        # the flat arch.rf value.) At T_ant = 290 K this is numerically
        # identical to the old kTB + NF form; it differs -- correctly --
        # for low-noise-sky satcom cases.
        nf_raw = context.get("cascade_nf_db", arch.rf.noise_figure_db)
        nf_db = float(nf_raw) if isinstance(nf_raw, (int, float)) else arch.rf.noise_figure_db
        noise_factor = 10.0 ** (nf_db / 10.0)
        t_sys_k = scenario.rx_noise_temp_k + 290.0 * (noise_factor - 1.0)
        noise_power_dbw = W_TO_DBW(K_B * t_sys_k * scenario.bandwidth_hz)

        # SNR
        snr_rx_db = rx_power_dbw - noise_power_dbw

        # Optional nonlinearity: fold two-tone IM3 into an SNDR when the RX
        # cascade provided an IIP3 and the scenario asks for it. Default off,
        # so thermal-only behavior (and every recorded golden value) is
        # unchanged.
        sndr_rx_db = snr_rx_db
        imd3_dbc = float("inf")
        evm_rms_pct = 100.0 * 10 ** (-snr_rx_db / 20.0)
        cascade_iip3 = context.get("cascade_iip3_dbm")
        if scenario.nonlinear_impairments and isinstance(cascade_iip3, (int, float)):
            from phased_array_systems.models.rf.cascade import sndr_with_imd3

            rx_power_dbm = rx_power_dbw + 30.0
            nonlin = sndr_with_imd3(snr_rx_db, rx_power_dbm, float(cascade_iip3))
            sndr_rx_db = nonlin["sndr_db"]
            imd3_dbc = nonlin["imd3_dbc"]
            evm_rms_pct = nonlin["evm_rms_pct"]

        # Link margin (against SNDR when nonlinearity is enabled)
        link_margin_db = sndr_rx_db - scenario.required_snr_db

        return {
            "tx_power_total_dbw": tx_power_total_dbw,
            "tx_power_per_elem_dbw": tx_power_per_elem_dbw,
            "pa_compression_db": pa_compression_db,
            "sndr_rx_db": sndr_rx_db,
            "imd3_dbc": imd3_dbc,
            "evm_rms_pct": evm_rms_pct,
            "g_tx_db": g_tx_db,
            "eirp_dbw": eirp_dbw,
            "path_loss_db": total_path_loss_db,
            "fspl_db": path_loss_db,
            "atmospheric_loss_computed_db": atmo_loss_db,
            "rain_loss_computed_db": rain_computed_db,
            "g_rx_db": g_rx_db,
            "rx_power_dbw": rx_power_dbw,
            "noise_power_dbw": noise_power_dbw,
            "noise_temp_system_k": t_sys_k,
            "noise_figure_used_db": nf_db,
            "snr_rx_db": snr_rx_db,
            "link_margin_db": link_margin_db,
            "required_snr_db": scenario.required_snr_db,
        }


def compute_link_margin(
    eirp_dbw: float,
    path_loss_db: float,
    g_rx_db: float,
    noise_temp_k: float,
    bandwidth_hz: float,
    noise_figure_db: float,
    required_snr_db: float,
) -> dict[str, float]:
    """Standalone link margin calculation.

    Convenience function for quick link budget calculations
    without full Architecture/Scenario objects.

    Args:
        eirp_dbw: Effective Isotropic Radiated Power (dBW)
        path_loss_db: Total path loss (dB)
        g_rx_db: Receive antenna gain (dB)
        noise_temp_k: Antenna noise temperature T_ant (K); the receiver
            contribution is added via the noise figure
        bandwidth_hz: Signal bandwidth (Hz)
        noise_figure_db: Receiver noise figure (dB, referenced to 290 K)
        required_snr_db: Required SNR for demodulation (dB)

    Returns:
        Dictionary with rx_power_dbw, noise_power_dbw, noise_temp_system_k,
        snr_db, margin_db
    """
    rx_power_dbw = eirp_dbw - path_loss_db + g_rx_db
    noise_factor = 10.0 ** (noise_figure_db / 10.0)
    t_sys_k = noise_temp_k + 290.0 * (noise_factor - 1.0)
    noise_power_dbw = W_TO_DBW(K_B * t_sys_k * bandwidth_hz)
    snr_db = rx_power_dbw - noise_power_dbw
    margin_db = snr_db - required_snr_db

    return {
        "rx_power_dbw": rx_power_dbw,
        "noise_power_dbw": noise_power_dbw,
        "noise_temp_system_k": t_sys_k,
        "snr_db": snr_db,
        "margin_db": margin_db,
    }
