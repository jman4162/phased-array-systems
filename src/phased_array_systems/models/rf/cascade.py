"""Cascaded RF performance models.

This module implements cascaded analysis for multi-stage RF chains including:
- Friis noise figure cascade
- Cascaded gain
- Cascaded intercept points (IIP3/OIP3)
- Spurious-free dynamic range (SFDR)

These calculations are essential for analyzing receiver and transmitter chains
in phased array systems, particularly for digital arrays with multiple
gain/filter stages.

Key Equations:
    Friis: F_total = F1 + (F2-1)/G1 + (F3-1)/(G1*G2) + ...
    SFDR = (2/3) * (OIP3 - Noise Floor)

References:
    - Friis, H.T. "Noise Figures of Radio Receivers", 1944
    - Pozar, D. "Microwave Engineering", 4th Edition
    - Your PowerPoint: Section 6 - AESA Cascaded Performance
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

# Physical constants
T0 = 290.0  # Reference temperature in Kelvin
K_B = 1.380649e-23  # Boltzmann constant J/K


def noise_figure_to_temp(nf_db: float, t0: float = T0) -> float:
    """Convert noise figure to equivalent noise temperature.

    Te = T0 * (F - 1)

    Args:
        nf_db: Noise figure in dB
        t0: Reference temperature in Kelvin (default 290K)

    Returns:
        Equivalent noise temperature in Kelvin
    """
    f_linear = 10 ** (nf_db / 10)
    return t0 * (f_linear - 1)


def noise_temp_to_figure(te: float, t0: float = T0) -> float:
    """Convert equivalent noise temperature to noise figure.

    F = 1 + Te/T0

    Args:
        te: Equivalent noise temperature in Kelvin
        t0: Reference temperature in Kelvin (default 290K)

    Returns:
        Noise figure in dB
    """
    f_linear = 1 + te / t0
    return 10 * math.log10(f_linear)


def friis_noise_figure(
    stages: list[tuple[float, float]],
) -> dict[str, Any]:
    """Calculate cascaded noise figure using Friis equation.

    The Friis formula for cascaded noise figure:
        F_total = F1 + (F2-1)/G1 + (F3-1)/(G1*G2) + ...

    This shows why low-noise amplifiers (LNAs) are placed first -
    the first stage dominates the system noise figure.

    Args:
        stages: List of (gain_db, noise_figure_db) tuples for each stage
                Stages are in signal flow order (first = input)

    Returns:
        Dictionary with:
            - total_nf_db: Cascaded noise figure in dB
            - total_gain_db: Cascaded gain in dB
            - noise_temp_k: Equivalent noise temperature
            - stage_contribution_pct: Each stage's share of the total
              excess noise factor (F_total - 1); sums to 100
            - stage_nf_delta_db: dB of total NF saved if that stage were
              noiseless (0 dB NF, same gain)
    """
    if not stages:
        return {
            "total_nf_db": 0.0,
            "total_gain_db": 0.0,
            "noise_temp_k": 0.0,
            "stage_contribution_pct": [],
            "stage_nf_delta_db": [],
        }

    # Convert to linear
    gains_linear = [10 ** (g / 10) for g, _ in stages]
    nfs_linear = [10 ** (nf / 10) for _, nf in stages]

    # Friis equation
    f_total = nfs_linear[0]
    cumulative_gain = gains_linear[0]
    contributions = [nfs_linear[0] - 1]  # First stage contribution

    for i in range(1, len(stages)):
        contribution = (nfs_linear[i] - 1) / cumulative_gain
        contributions.append(contribution)
        f_total += contribution
        cumulative_gain *= gains_linear[i]

    # Per-stage share of the excess noise factor: sums to 100% by
    # construction (a per-stage "dB contribution" cannot sum to the total
    # NF, which is why the old stage_contributions_db key was dropped)
    excess = f_total - 1.0
    contribution_pct = [100.0 * c / excess if excess > 0 else 0.0 for c in contributions]

    # dB of total NF saved if stage i were noiseless (same gain)
    total_nf_db = 10 * math.log10(f_total)
    nf_delta_db = [total_nf_db - 10 * math.log10(f_total - c) for c in contributions]

    total_gain_db = sum(g for g, _ in stages)
    noise_temp_k = noise_figure_to_temp(total_nf_db)

    return {
        "total_nf_db": total_nf_db,
        "total_gain_db": total_gain_db,
        "noise_temp_k": noise_temp_k,
        "stage_contribution_pct": contribution_pct,
        "stage_nf_delta_db": nf_delta_db,
        "n_stages": len(stages),
    }


def system_noise_temperature(
    antenna_temp_k: float,
    receiver_nf_db: float,
    line_loss_db: float = 0.0,
    line_temp_k: float = T0,
) -> dict[str, float]:
    """Calculate system noise temperature including antenna and losses.

    T_sys = T_ant + T_line + T_rx

    Where T_line accounts for loss between antenna and receiver.

    Args:
        antenna_temp_k: Antenna noise temperature in Kelvin
        receiver_nf_db: Receiver noise figure in dB
        line_loss_db: Transmission line loss in dB (default 0)
        line_temp_k: Physical temperature of line in Kelvin

    Returns:
        Dictionary with:
            - system_temp_k: Total system noise temperature
            - antenna_contribution_k: Antenna noise contribution
            - line_contribution_k: Line loss contribution
            - receiver_contribution_k: Receiver contribution
            - system_nf_db: Effective system noise figure
    """
    # Receiver noise temperature
    t_rx = noise_figure_to_temp(receiver_nf_db)

    # Line loss contribution
    # T_line = (L - 1) * T_physical where L is loss factor
    l_linear = 10 ** (line_loss_db / 10)
    t_line = (l_linear - 1) * line_temp_k

    # Antenna temperature after line loss
    t_ant_after_loss = antenna_temp_k / l_linear

    # Total system temperature
    t_sys = t_ant_after_loss + t_line + t_rx

    # Effective system NF (referenced to antenna)
    system_nf_db = noise_temp_to_figure(t_sys - T0) if t_sys > T0 else 0.0

    return {
        "system_temp_k": t_sys,
        "antenna_contribution_k": t_ant_after_loss,
        "line_contribution_k": t_line,
        "receiver_contribution_k": t_rx,
        "system_nf_db": system_nf_db,
    }


def cascade_gain(gains_db: list[float]) -> float:
    """Calculate total cascaded gain.

    Simply sums gains in dB (multiplies in linear).

    Args:
        gains_db: List of stage gains in dB (negative for loss)

    Returns:
        Total gain in dB
    """
    return sum(gains_db)


def cascade_gain_db(stages: list[tuple[float, float]]) -> float:
    """Calculate total cascaded gain from stage tuples.

    Args:
        stages: List of (gain_db, noise_figure_db) tuples

    Returns:
        Total gain in dB
    """
    return sum(g for g, _ in stages)


def cascade_iip3(
    stages: list[tuple[float, float]],
) -> dict[str, float]:
    """Calculate cascaded input third-order intercept point.

    For cascaded stages:
        1/IIP3_total = 1/IIP3_1 + G1/IIP3_2 + G1*G2/IIP3_3 + ...

    (All values in linear power, not dB)

    Args:
        stages: List of (gain_db, iip3_dbm) tuples for each stage

    Returns:
        Dictionary with:
            - iip3_dbm: Cascaded input IP3 in dBm
            - oip3_dbm: Cascaded output IP3 in dBm
            - total_gain_db: Cascaded gain
    """
    if not stages:
        return {"iip3_dbm": float("inf"), "oip3_dbm": float("inf"), "total_gain_db": 0}

    # Convert to linear (mW)
    gains_linear = [10 ** (g / 10) for g, _ in stages]
    iip3s_linear = [10 ** (iip3 / 10) for _, iip3 in stages]

    # Cascade formula
    inv_iip3_total = 1 / iip3s_linear[0]
    cumulative_gain = gains_linear[0]

    for i in range(1, len(stages)):
        inv_iip3_total += cumulative_gain / iip3s_linear[i]
        cumulative_gain *= gains_linear[i]

    iip3_total_linear = 1 / inv_iip3_total
    iip3_dbm = 10 * math.log10(iip3_total_linear)

    total_gain_db = sum(g for g, _ in stages)
    oip3_dbm = iip3_dbm + total_gain_db

    return {
        "iip3_dbm": iip3_dbm,
        "oip3_dbm": oip3_dbm,
        "total_gain_db": total_gain_db,
    }


def cascade_oip3(
    stages: list[tuple[float, float]],
) -> dict[str, float]:
    """Calculate cascaded output third-order intercept point.

    Same as cascade_iip3 but with OIP3 inputs.

    Args:
        stages: List of (gain_db, oip3_dbm) tuples for each stage

    Returns:
        Dictionary with iip3_dbm, oip3_dbm, total_gain_db
    """
    # Convert OIP3 to IIP3 for each stage
    iip3_stages = [(g, oip3 - g) for g, oip3 in stages]
    result = cascade_iip3(iip3_stages)
    return result


def cascade_p1db(
    stages: list[tuple[float, float]],
) -> dict[str, float]:
    """Calculate cascaded input-referred 1 dB compression point.

    Uses the reciprocal-sum approximation, the same form as the IIP3 cascade:

        1/P1dB_in,total = 1/P1dB_in,1 + G1/P1dB_in,2 + G1*G2/P1dB_in,3 + ...

    (linear power). This assumes stage compressions combine independently,
    which is the standard first-order bookkeeping approximation; a driven
    stage near saturation compresses slightly earlier than this predicts.

    Args:
        stages: List of (gain_db, p1db_in_dbm) tuples for each stage

    Returns:
        Dictionary with:
            - ip1db_dbm: Cascaded input-referred P1dB in dBm
            - op1db_dbm: Cascaded output-referred P1dB (input P1dB + gain - 1)
            - total_gain_db: Cascaded gain
    """
    if not stages:
        return {"ip1db_dbm": float("inf"), "op1db_dbm": float("inf"), "total_gain_db": 0}

    gains_linear = [10 ** (g / 10) for g, _ in stages]
    p1dbs_linear = [10 ** (p / 10) for _, p in stages]

    inv_total = 1 / p1dbs_linear[0]
    cumulative_gain = gains_linear[0]
    for i in range(1, len(stages)):
        inv_total += cumulative_gain / p1dbs_linear[i]
        cumulative_gain *= gains_linear[i]

    ip1db_dbm = 10 * math.log10(1 / inv_total)
    total_gain_db = sum(g for g, _ in stages)
    return {
        "ip1db_dbm": ip1db_dbm,
        # At the 1 dB compression point the chain delivers gain - 1 dB.
        "op1db_dbm": ip1db_dbm + total_gain_db - 1.0,
        "total_gain_db": total_gain_db,
    }


def rapp_compression_db(
    input_power_dbm: float,
    ip1db_dbm: float,
    smoothness: float = 2.0,
) -> float:
    """Gain compression (dB, >= 0) at an operating point, Rapp soft limiter.

    The Rapp AM/AM model on power quantities:

        P_out = G * P_in / (1 + (G * P_in / P_sat)^p)^(1/p)

    with P_sat chosen in closed form so that the 1 dB compression point sits
    exactly at *ip1db_dbm*: r = (10^(0.1 p) - 1)^(1/p) and
    P_sat = linear(op1db) / r. At input backoffs of 10 dB or more the
    compression is negligible; at the P1dB point it is exactly 1 dB by
    construction.

    Args:
        input_power_dbm: Operating input power (dBm)
        ip1db_dbm: Input-referred 1 dB compression point (dBm)
        smoothness: Rapp smoothness parameter p (2.0 is a typical solid-state
            PA knee; larger is sharper)

    Returns:
        Compression in dB (subtract from the linear-gain output power).
    """
    p = smoothness
    # Ratio of drive to saturation drive that yields exactly 1 dB compression.
    r_1db = (10 ** (0.1 * p) - 1.0) ** (1.0 / p)
    # Drive relative to the 1 dB point, then relative to saturation.
    drive_rel_sat = r_1db * 10 ** ((input_power_dbm - ip1db_dbm) / 10.0)
    return 10.0 / p * math.log10(1.0 + drive_rel_sat**p)


def compression_check(
    stages: list[RFStage],
    input_power_dbm: float,
) -> dict[str, float | str | list[float]]:
    """Check each stage's drive level against its output P1dB.

    Tracks linear levels through the chain (the same walk cascade_analysis
    does) and reports per-stage headroom to op1db_dbm and the binding stage.

    Args:
        stages: RFStage list in signal-flow order
        input_power_dbm: Operating input power (dBm)

    Returns:
        Dictionary with:
            - stage_headroom_db: output-P1dB headroom per stage (list)
            - min_headroom_db: the worst headroom
            - binding_stage: name of the stage with least headroom
            - compressed: True when any stage output exceeds its op1db
    """
    level = input_power_dbm
    headrooms: list[float] = []
    names: list[str] = []
    for stage in stages:
        level += stage.gain_db
        headrooms.append(stage.op1db_dbm - level)
        names.append(stage.name)
    if not headrooms:
        return {
            "stage_headroom_db": [],
            "min_headroom_db": float("inf"),
            "binding_stage": "",
            "compressed": False,
        }
    idx = int(min(range(len(headrooms)), key=headrooms.__getitem__))
    return {
        "stage_headroom_db": headrooms,
        "min_headroom_db": headrooms[idx],
        "binding_stage": names[idx],
        "compressed": headrooms[idx] < 0.0,
    }


def sndr_with_imd3(
    snr_db: float,
    carrier_power_dbm: float,
    iip3_dbm: float,
) -> dict[str, float]:
    """Combine thermal SNR with two-tone third-order distortion.

    IM3 products sit 2*(IIP3 - P_in) below the carrier (per-tone two-tone
    approximation), so:

        imd3_dbc = 2 * (iip3_dbm - carrier_power_dbm)
        sndr = -10 log10(10^(-snr/10) + 10^(-imd3_dbc/10))

    EVM follows as the RMS error-vector fraction of an ideal constellation
    limited by that SNDR: evm_rms = 10^(-sndr/20).

    Args:
        snr_db: Thermal signal-to-noise ratio (dB)
        carrier_power_dbm: Operating carrier power at the chain input (dBm)
        iip3_dbm: Cascaded input-referred IP3 (dBm)

    Returns:
        Dictionary with sndr_db, imd3_dbc, evm_rms_pct.
    """
    imd3_dbc = 2.0 * (iip3_dbm - carrier_power_dbm)
    sndr_db = -10.0 * math.log10(10 ** (-snr_db / 10.0) + 10 ** (-imd3_dbc / 10.0))
    return {
        "sndr_db": sndr_db,
        "imd3_dbc": imd3_dbc,
        "evm_rms_pct": 100.0 * 10 ** (-sndr_db / 20.0),
    }


def sfdr_from_iip3(
    iip3_dbm: float,
    noise_floor_dbm_hz: float,
    bandwidth_hz: float,
) -> dict[str, float]:
    """Calculate spurious-free dynamic range from IIP3.

    SFDR is the range between the noise floor and the signal level
    where third-order intermodulation products equal the noise.

    SFDR = (2/3) * (IIP3 - Noise Floor)

    Args:
        iip3_dbm: Input third-order intercept point in dBm
        noise_floor_dbm_hz: Noise floor spectral density in dBm/Hz
        bandwidth_hz: Signal bandwidth for integrated noise

    Returns:
        Dictionary with:
            - sfdr_db: Spurious-free dynamic range in dB
            - noise_floor_dbm: Integrated noise floor
            - max_signal_dbm: Maximum signal before spurs exceed noise
    """
    noise_floor_dbm = noise_floor_dbm_hz + 10 * math.log10(bandwidth_hz)
    sfdr_db = (2 / 3) * (iip3_dbm - noise_floor_dbm)
    max_signal_dbm = noise_floor_dbm + sfdr_db

    return {
        "sfdr_db": sfdr_db,
        "noise_floor_dbm": noise_floor_dbm,
        "max_signal_dbm": max_signal_dbm,
        "iip3_dbm": iip3_dbm,
    }


def sfdr_from_oip3(
    oip3_dbm: float,
    noise_floor_dbm_hz: float,
    bandwidth_hz: float,
    gain_db: float,
) -> dict[str, float]:
    """Calculate spurious-free dynamic range from OIP3.

    Args:
        oip3_dbm: Output third-order intercept point in dBm
        noise_floor_dbm_hz: Noise floor spectral density in dBm/Hz
        bandwidth_hz: Signal bandwidth for integrated noise
        gain_db: Total system gain in dB

    Returns:
        Dictionary with sfdr_db, noise_floor_dbm, max_signal_dbm
    """
    iip3_dbm = oip3_dbm - gain_db
    return sfdr_from_iip3(iip3_dbm, noise_floor_dbm_hz, bandwidth_hz)


def mds_from_noise_figure(
    noise_figure_db: float,
    bandwidth_hz: float,
    snr_required_db: float = 0.0,
    t0: float = T0,
) -> dict[str, float]:
    """Calculate minimum detectable signal from noise figure.

    MDS = kTB + NF + SNR_required

    Args:
        noise_figure_db: System noise figure in dB
        bandwidth_hz: Receiver bandwidth in Hz
        snr_required_db: Required SNR for detection (default 0 dB)
        t0: Reference temperature in Kelvin

    Returns:
        Dictionary with:
            - mds_dbm: Minimum detectable signal in dBm
            - noise_floor_dbm: Noise floor in dBm
            - ktb_dbm: Thermal noise power
    """
    # kT in dBm/Hz at T0
    kt_dbm_hz = 10 * math.log10(K_B * t0 * 1000)  # *1000 for mW

    # kTB
    ktb_dbm = kt_dbm_hz + 10 * math.log10(bandwidth_hz)

    # Noise floor = kTB + NF
    noise_floor_dbm = ktb_dbm + noise_figure_db

    # MDS
    mds_dbm = noise_floor_dbm + snr_required_db

    return {
        "mds_dbm": mds_dbm,
        "noise_floor_dbm": noise_floor_dbm,
        "ktb_dbm": ktb_dbm,
        "kt_dbm_hz": kt_dbm_hz,
    }


@dataclass
class RFStage:
    """A single stage in an RF chain.

    Attributes:
        name: Descriptive name for the stage
        gain_db: Stage gain in dB (negative for loss)
        noise_figure_db: Stage noise figure in dB
        iip3_dbm: Input third-order intercept point in dBm
        p1db_dbm: Input 1dB compression point in dBm (optional)
    """

    name: str
    gain_db: float
    noise_figure_db: float
    iip3_dbm: float = 100.0  # Default very high (ideal)
    p1db_dbm: float = 100.0  # Default very high (ideal)

    @property
    def oip3_dbm(self) -> float:
        """Output IP3."""
        return self.iip3_dbm + self.gain_db

    @property
    def op1db_dbm(self) -> float:
        """Output P1dB."""
        return self.p1db_dbm + self.gain_db


def cascade_analysis(
    stages: list[RFStage],
    bandwidth_hz: float = 1e6,
    input_power_dbm: float = -60.0,
) -> dict[str, float | list]:
    """Perform complete cascaded analysis of an RF chain.

    This is the main function for analyzing a complete receiver or
    transmitter chain, computing noise figure, gain, linearity, and
    dynamic range.

    Args:
        stages: List of RFStage objects in signal flow order
        bandwidth_hz: Analysis bandwidth in Hz
        input_power_dbm: Reference input power for level tracking

    Returns:
        Dictionary with comprehensive cascade results:
            - total_gain_db: Cascaded gain
            - total_nf_db: Cascaded noise figure
            - noise_temp_k: Equivalent noise temperature
            - iip3_dbm: Cascaded input IP3
            - oip3_dbm: Cascaded output IP3
            - sfdr_db: Spurious-free dynamic range
            - mds_dbm: Minimum detectable signal
            - stage_levels_dbm: Signal level at each stage output
            - stage_names: Names of each stage
    """
    if not stages:
        return {}

    # Build tuples for existing functions
    nf_stages = [(s.gain_db, s.noise_figure_db) for s in stages]
    iip3_stages = [(s.gain_db, s.iip3_dbm) for s in stages]

    # Cascade calculations
    nf_result = friis_noise_figure(nf_stages)
    iip3_result = cascade_iip3(iip3_stages)
    p1db_result = cascade_p1db([(s.gain_db, s.p1db_dbm) for s in stages])
    compression = compression_check(stages, input_power_dbm)

    # MDS
    mds_result = mds_from_noise_figure(
        nf_result["total_nf_db"],
        bandwidth_hz,
        snr_required_db=0,
    )

    # SFDR
    sfdr_result = sfdr_from_iip3(
        iip3_result["iip3_dbm"],
        mds_result["kt_dbm_hz"] + nf_result["total_nf_db"],
        bandwidth_hz,
    )

    # Track signal level through chain
    level = input_power_dbm
    levels = [level]
    for stage in stages:
        level += stage.gain_db
        levels.append(level)

    return {
        # Gain
        "total_gain_db": nf_result["total_gain_db"],
        # Noise
        "total_nf_db": nf_result["total_nf_db"],
        "noise_temp_k": nf_result["noise_temp_k"],
        "stage_nf_contribution_pct": nf_result["stage_contribution_pct"],
        "stage_nf_delta_db": nf_result["stage_nf_delta_db"],
        # Linearity
        "iip3_dbm": iip3_result["iip3_dbm"],
        "oip3_dbm": iip3_result["oip3_dbm"],
        "ip1db_dbm": p1db_result["ip1db_dbm"],
        "op1db_dbm": p1db_result["op1db_dbm"],
        "min_p1db_headroom_db": compression["min_headroom_db"],
        "p1db_binding_stage": compression["binding_stage"],
        "compressed": compression["compressed"],
        # Dynamic range
        "sfdr_db": sfdr_result["sfdr_db"],
        "mds_dbm": mds_result["mds_dbm"],
        "noise_floor_dbm": mds_result["noise_floor_dbm"],
        # Signal tracking
        "input_power_dbm": input_power_dbm,
        "output_power_dbm": levels[-1],
        "stage_levels_dbm": levels,
        "stage_names": ["Input"] + [s.name for s in stages],
        # Metadata
        "bandwidth_hz": bandwidth_hz,
        "n_stages": len(stages),
    }
