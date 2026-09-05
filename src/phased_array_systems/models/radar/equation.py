"""Radar range equation model."""

from __future__ import annotations

import math
from functools import lru_cache
from typing import Any

from phased_array_systems.architecture import Architecture
from phased_array_systems.constants import C_LIGHT, K_B, W_TO_DBW
from phased_array_systems.models.radar.cfar import cfar_loss_db
from phased_array_systems.models.radar.clutter import (
    compute_resolution_cell_area,
    compute_resolution_volume,
    compute_scnr,
    compute_scr,
    ground_clutter_rcs,
    rain_clutter_rcs,
    sea_clutter_rcs,
)
from phased_array_systems.models.radar.detection import compute_pd_from_snr, compute_snr_for_pd
from phased_array_systems.models.radar.integration import coherent_integration_gain
from phased_array_systems.models.radar.propagation import (
    atmospheric_loss_db,
    rain_attenuation_db,
)
from phased_array_systems.models.radar.propagation import (
    grazing_angle_deg as compute_grazing_angle,
)
from phased_array_systems.scenarios import RadarDetectionScenario
from phased_array_systems.types import MetricsDict


@lru_cache(maxsize=256)
def _required_snr(pd: float, pfa: float, swerling: int, n_pulses: int) -> float:
    """Cached exact required per-pulse SNR (noncoherent statistics).

    The (pd, pfa, swerling, n_pulses) tuple is constant across the cases
    of a DOE study, so the brentq/quad inversion runs once per study
    rather than once per case.
    """
    return compute_snr_for_pd(
        pd=pd,
        pfa=pfa,
        swerling=swerling,  # type: ignore[arg-type]
        n_pulses=n_pulses,
        integration="noncoherent",
    )


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
                - beamwidth_az_deg: Azimuth beamwidth (for clutter cell)
                - beamwidth_el_deg: Elevation beamwidth (for clutter cell)

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
                - clutter_rcs_dbsm: Clutter RCS if applicable (dBsm)
                - scr_db: Signal-to-clutter ratio if applicable (dB)
                - scnr_db: Signal-to-clutter-plus-noise ratio (dB)
                - atmos_loss_db: Two-way atmospheric loss (dB)
                - rain_loss_db: Two-way rain attenuation (dB)
                - cfar_loss_db: CFAR processing loss (dB)
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

        # Get beamwidths from context or approximate
        beamwidth_az_deg = context.get("beamwidth_az_deg", 5.0)
        beamwidth_el_deg = context.get("beamwidth_el_deg", 5.0)

        # Transmit power (peak)
        n_elements = arch.array.n_elements
        peak_power_w = arch.rf.tx_power_w_per_elem * n_elements
        peak_power_dbw = W_TO_DBW(peak_power_w)

        # Wavelength
        wavelength_m = C_LIGHT / scenario.freq_hz
        wavelength_db = 10 * math.log10(wavelength_m)

        # Range resolution
        range_resolution_m = scenario.range_resolution_m

        # System losses (feed network + additional system losses)
        system_loss_db = arch.rf.feed_loss_db + arch.rf.system_loss_db

        # Target RCS
        rcs_dbsm = scenario.target_rcs_dbsm
        rcs_m2 = 10 ** (rcs_dbsm / 10)

        # Range
        range_m = scenario.range_m
        range_db = 10 * math.log10(range_m)

        # Compute grazing angle if not specified
        if scenario.grazing_angle_deg is not None:
            grazing_angle = scenario.grazing_angle_deg
        else:
            grazing_angle = compute_grazing_angle(
                range_m,
                scenario.antenna_height_m,
                scenario.target_height_m,
            )
            grazing_angle = max(0.5, min(90.0, grazing_angle))

        # Propagation losses
        atmos_loss = 0.0
        rain_loss = 0.0

        if scenario.include_atmos_loss:
            atmos_loss = atmospheric_loss_db(
                scenario.freq_hz,
                range_m,
                elevation_deg=grazing_angle,
                temperature_c=scenario.temperature_c,
                humidity_pct=scenario.humidity_pct,
            )

        if scenario.rain_rate_mm_hr > 0:
            rain_loss = rain_attenuation_db(
                scenario.freq_hz,
                range_m,
                scenario.rain_rate_mm_hr,
            )

        # Total propagation loss
        propagation_loss_db = atmos_loss + rain_loss

        # Noise convention: rx_noise_temp_k is the ANTENNA temperature.
        # T_sys = T_ant + T0*(F-1), N = k*T_sys*B. Cascaded NF from context
        # (RF cascade model) wins over the flat arch.rf value, matching the
        # comms link budget.
        nf_raw = context.get("cascade_nf_db", arch.rf.noise_figure_db)
        nf_db = float(nf_raw) if isinstance(nf_raw, (int, float)) else arch.rf.noise_figure_db
        noise_factor = 10.0 ** (nf_db / 10.0)
        t_sys_k = scenario.rx_noise_temp_k + 290.0 * (noise_factor - 1.0)
        noise_power_dbw = W_TO_DBW(K_B * t_sys_k * scenario.bandwidth_hz)

        # Radar equation constant: (4π)^3 in dB
        radar_constant_db = 30 * math.log10(4 * math.pi)  # ≈ 32.98 dB

        # Single-pulse SNR (monostatic radar equation in dB)
        # SNR = Pt + 2*G + 2*λ_dB + σ - 4*R_dB - L - (4π)^3_dB - N - L_prop
        snr_single_db = (
            peak_power_dbw
            + 2 * g_ant_db
            + 2 * wavelength_db
            + rcs_dbsm
            - 4 * range_db
            - system_loss_db
            - radar_constant_db
            - noise_power_dbw
            - propagation_loss_db
        )

        # Clutter calculations
        clutter_rcs_dbsm = -100.0  # Default: no clutter
        scr_db = 100.0  # Default: no clutter (infinite SCR)

        if scenario.clutter_type != "none":
            # Compute resolution cell area/volume
            cell_area = compute_resolution_cell_area(range_m, range_resolution_m, beamwidth_az_deg)
            cell_volume = compute_resolution_volume(
                range_m, range_resolution_m, beamwidth_az_deg, beamwidth_el_deg
            )

            if scenario.clutter_type == "sea":
                clutter_rcs_dbsm = sea_clutter_rcs(
                    scenario.sea_state,
                    grazing_angle,
                    scenario.freq_hz,
                    cell_area,
                    scenario.polarization,
                )
            elif scenario.clutter_type == "ground":
                clutter_rcs_dbsm = ground_clutter_rcs(
                    scenario.terrain_type,
                    grazing_angle,
                    scenario.freq_hz,
                    cell_area,
                )
            elif scenario.clutter_type == "rain":
                clutter_rcs_dbsm = rain_clutter_rcs(
                    scenario.rain_rate_mm_hr,
                    scenario.freq_hz,
                    cell_volume,
                )

            scr_db = compute_scr(rcs_dbsm, clutter_rcs_dbsm)

        # MTI clutter suppression, when a canceller is configured. Without it a
        # ground-based radar looking at clutter is judged undetectable, which
        # misrepresents every real MTI system. Improvement factor rather than
        # clutter attenuation is applied, because I = G*CA carries both the
        # filter's gain on the target and its rejection of clutter, and it is
        # the SCR that the detection budget consumes.
        mti_improvement_db = 0.0
        mti_metrics: MetricsDict = {}
        if scenario.mti_n_pulse is not None and scenario.clutter_type != "none":
            from phased_array_systems.models.radar.mti import (
                blind_speed_ms,
                clutter_spectral_std_hz,
                doppler_shift_hz,
                mti_improvement_factor,
                mti_improvement_factor_at_doppler,
                normalized_clutter_spread_rad,
                unambiguous_range_m,
            )

            # prf_hz is guaranteed by RadarDetectionScenario's model validator.
            assert scenario.prf_hz is not None
            sigma_omega = normalized_clutter_spread_rad(
                clutter_spectral_std_hz(scenario.clutter_velocity_std_ms, scenario.wavelength_m),
                scenario.prf_hz,
            )

            v_blind = blind_speed_ms(scenario.prf_hz, scenario.wavelength_m)
            mti_metrics["mti_blind_speed_ms"] = v_blind
            mti_metrics["mti_unambiguous_range_m"] = unambiguous_range_m(scenario.prf_hz)

            if scenario.target_radial_velocity_ms is None:
                # Target velocity unknown: credit the Doppler-averaged gain.
                improvement = mti_improvement_factor(scenario.mti_n_pulse, sigma_omega)
                mti_metrics["mti_target_near_blind"] = False
            else:
                # Target velocity known: credit what the filter does to *this*
                # target. The averaged figure is not merely optimistic at a
                # blind speed, it is qualitatively wrong -- the canceller nulls
                # the target along with the clutter, and the averaged model
                # still reports a detection.
                f_d = doppler_shift_hz(scenario.target_radial_velocity_ms, scenario.wavelength_m)
                omega_d = 2.0 * math.pi * f_d / scenario.prf_hz
                improvement = mti_improvement_factor_at_doppler(
                    scenario.mti_n_pulse, sigma_omega, omega_d
                )
                mti_metrics["target_doppler_hz"] = f_d
                # Distance to the nearest blind speed, as a fraction of the
                # blind-speed interval; within a tenth of it the canceller is
                # taking more than ~1 dB out of the target itself.
                v_r = abs(scenario.target_radial_velocity_ms)
                near = abs(v_r / v_blind - round(v_r / v_blind))
                mti_metrics["mti_target_near_blind"] = bool(near < 0.1)

            improvement_db = 10.0 * math.log10(improvement) if improvement > 0 else -math.inf

            # Cap at the system's stability-limited ceiling. The canceller model
            # is unbounded (infinite for perfectly stationary clutter) while real
            # MTI is held to roughly 30-60 dB by transmitter stability, phase
            # noise and converter dynamic range. Without this an inf reaches the
            # metrics dict and the exported JSON.
            limit = scenario.mti_improvement_limit_db
            if limit is not None and improvement_db > limit:
                mti_improvement_db = float(limit)
                mti_metrics["mti_improvement_limited"] = True
            else:
                mti_improvement_db = improvement_db
                mti_metrics["mti_improvement_limited"] = False

            scr_db += mti_improvement_db

        # Compute SCNR (signal-to-clutter-plus-noise ratio)
        scnr_db = compute_scnr(snr_single_db, scr_db)

        # CFAR loss
        cfar_loss = 0.0
        if scenario.cfar_type != "none":
            cfar_loss = cfar_loss_db(
                scenario.cfar_type,
                scenario.cfar_ref_cells,
                scenario.pfa,
            )

        # Integration gain and required SNR must come from the same law to
        # avoid double-counting. Both use the exact detection statistics
        # (noncentral chi-square / gamma mixtures), so target fluctuation
        # affects the margin consistently; the implied noncoherent gain is
        # the drop in required single-pulse SNR vs n=1.
        n_pulses = scenario.n_pulses
        swerling = scenario.swerling

        # An N-pulse canceller run over the dwell returns n_pulses - N + 1
        # outputs, so the integration budget cannot go on crediting all of them.
        # Without this a 1-pulse dwell through a 3-pulse canceller was accepted
        # and awarded the full three-pulse improvement (the scenario validator
        # now rejects that outright) while a 10-pulse dwell kept a full 10-pulse
        # integration gain it no longer has.
        #
        # Approximation: an MTI canceller correlates the noise between adjacent
        # outputs, so the true post-MTI integration gain is somewhat below the
        # independent-sample figure used here. Modelling that needs the output
        # covariance and is out of scope; this is the standard design-time
        # accounting and it errs on the optimistic side by well under a dB.
        n_integrated = n_pulses
        if scenario.mti_n_pulse is not None and scenario.clutter_type != "none":
            n_integrated = max(1, n_pulses - scenario.mti_n_pulse + 1)

        snr_required_db = _required_snr(
            pd=scenario.pd_required,
            pfa=scenario.pfa,
            swerling=swerling,
            n_pulses=1,
        )
        if scenario.integration_type == "coherent":
            integration_gain_db = coherent_integration_gain(n_integrated)
        else:
            snr_required_single_db = _required_snr(
                pd=scenario.pd_required,
                pfa=scenario.pfa,
                swerling=swerling,
                n_pulses=n_integrated,
            )
            integration_gain_db = snr_required_db - snr_required_single_db

        # Integrated SCNR (use SCNR when clutter is present, SNR otherwise)
        effective_snr_single = scnr_db if scenario.clutter_type != "none" else snr_single_db

        # The SNR available to a *measurement*, which is not the same quantity
        # as the SNR the detection budget works in. A CFAR loss is a threshold
        # penalty, not a reduction in received signal power, so it belongs in
        # the detection margin and nowhere near sigma = dR / sqrt(2 SNR). This
        # is the number models/radar/tracking.py consumes; see that module's
        # note on what the integration term means for a noncoherent dwell.
        snr_measurement_db = effective_snr_single + integration_gain_db

        snr_integrated_db = snr_measurement_db - cfar_loss

        # SNR margin (snr_required_db is referenced to the integrated SNR)
        snr_margin_db = snr_integrated_db - snr_required_db

        # Achieved Pd from per-pulse SNR using exact n-pulse statistics
        pd_achieved = compute_pd_from_snr(
            effective_snr_single - cfar_loss,
            scenario.pfa,
            swerling=swerling,
            n_pulses=n_integrated,
            integration=scenario.integration_type,
        )

        # Detection range (range where margin = 0)
        # From radar equation: R^4 proportional to SNR
        # R_det / R = (SNR_integrated / SNR_required)^(1/4)
        # In dB: R_det = R * 10^(margin_dB / 40)
        detection_range_m = range_m * 10 ** (snr_margin_db / 40) if snr_margin_db > -40 else 0.0

        metrics: MetricsDict = {
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
            "grazing_angle_deg": grazing_angle,
            # Noise
            "noise_power_dbw": noise_power_dbw,
            "noise_temp_system_k": t_sys_k,
            "noise_figure_used_db": nf_db,
            "system_loss_db": system_loss_db,
            # Propagation losses
            "atmos_loss_db": atmos_loss,
            "rain_loss_db": rain_loss,
            "propagation_loss_db": propagation_loss_db,
            # Clutter
            "clutter_type": scenario.clutter_type,
            "clutter_rcs_dbsm": clutter_rcs_dbsm,
            "scr_db": scr_db,
            "scnr_db": scnr_db,
            # CFAR
            "cfar_type": scenario.cfar_type,
            "cfar_loss_db": cfar_loss,
            # SNR
            "snr_single_pulse_db": snr_single_db,
            "integration_gain_db": integration_gain_db,
            "snr_measurement_db": snr_measurement_db,
            "snr_integrated_db": snr_integrated_db,
            "snr_required_db": snr_required_db,
            "snr_margin_db": snr_margin_db,
            # Detection
            "pd_achieved": pd_achieved,
            "pd_required": scenario.pd_required,
            "pfa": scenario.pfa,
            "swerling": swerling,
            "n_pulses": n_pulses,
            "n_pulses_effective": n_integrated,
            "integration_type": scenario.integration_type,
            "detection_range_m": detection_range_m,
        }

        # Emitted only when a canceller is configured, so a run without MTI
        # produces exactly the keys it did before.
        if scenario.mti_n_pulse is not None and scenario.clutter_type != "none":
            metrics["mti_improvement_db"] = mti_improvement_db
            metrics["mti_n_pulse"] = scenario.mti_n_pulse
            metrics.update(mti_metrics)

        return metrics


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
