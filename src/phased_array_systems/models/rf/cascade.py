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

    Example:
        >>> noise_figure_to_temp(3.0)  # 3 dB NF
        288.6  # Approximately
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

    Example:
        >>> noise_temp_to_figure(290)
        3.01  # Approximately
    """
    f_linear = 1 + te / t0
    return 10 * math.log10(f_linear)


def friis_noise_figure(
    stages: list[tuple[float, float]],
) -> dict[str, float]:
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
            - stage_contributions_db: NF contribution from each stage

    Example:
        >>> # LNA (15 dB gain, 2 dB NF) -> Mixer (10 dB loss, 10 dB NF)
        >>> result = friis_noise_figure([
        ...     (15, 2),    # LNA
        ...     (-10, 10),  # Mixer (loss = negative gain)
        ... ])
        >>> print(f"System NF: {result['total_nf_db']:.2f} dB")
    """
    if not stages:
        return {
            "total_nf_db": 0.0,
            "total_gain_db": 0.0,
            "noise_temp_k": 0.0,
            "stage_contributions_db": [],
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

    # Convert contributions to dB (referenced to total)
    contributions_db = [10 * math.log10(1 + c) for c in contributions]

    total_nf_db = 10 * math.log10(f_total)
    total_gain_db = sum(g for g, _ in stages)
    noise_temp_k = noise_figure_to_temp(total_nf_db)

    return {
        "total_nf_db": total_nf_db,
        "total_gain_db": total_gain_db,
        "noise_temp_k": noise_temp_k,
        "stage_contributions_db": contributions_db,
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

    Example:
        >>> result = system_noise_temperature(
        ...     antenna_temp_k=50,  # Cold sky
        ...     receiver_nf_db=2.0,
        ...     line_loss_db=0.5
        ... )
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

    Example:
        >>> cascade_gain([20, -3, 15, -6])  # LNA, filter, amp, cable
        26
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

    Example:
        >>> # LNA (15dB, +5dBm IIP3) -> Mixer (-10dB, +10dBm IIP3)
        >>> result = cascade_iip3([
        ...     (15, 5),
        ...     (-10, 10),
        ... ])
    """
    if not stages:
        return {"iip3_dbm": float('inf'), "oip3_dbm": float('inf'), "total_gain_db": 0}

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

    Example:
        >>> result = sfdr_from_iip3(
        ...     iip3_dbm=5,
        ...     noise_floor_dbm_hz=-170,
        ...     bandwidth_hz=1e6
        ... )
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

    Example:
        >>> result = mds_from_noise_figure(
        ...     noise_figure_db=3,
        ...     bandwidth_hz=1e6,
        ...     snr_required_db=10
        ... )
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

    Example:
        >>> stages = [
        ...     RFStage("LNA", gain_db=20, noise_figure_db=1.5, iip3_dbm=-5),
        ...     RFStage("Filter", gain_db=-2, noise_figure_db=2, iip3_dbm=30),
        ...     RFStage("Mixer", gain_db=-8, noise_figure_db=8, iip3_dbm=15),
        ...     RFStage("IF Amp", gain_db=30, noise_figure_db=4, iip3_dbm=10),
        ... ]
        >>> result = cascade_analysis(stages, bandwidth_hz=10e6)
        >>> print(f"System NF: {result['total_nf_db']:.2f} dB")
        >>> print(f"SFDR: {result['sfdr_db']:.1f} dB")
    """
    if not stages:
        return {}

    # Build tuples for existing functions
    nf_stages = [(s.gain_db, s.noise_figure_db) for s in stages]
    iip3_stages = [(s.gain_db, s.iip3_dbm) for s in stages]

    # Cascade calculations
    nf_result = friis_noise_figure(nf_stages)
    iip3_result = cascade_iip3(iip3_stages)

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
        "stage_nf_contributions_db": nf_result["stage_contributions_db"],
        # Linearity
        "iip3_dbm": iip3_result["iip3_dbm"],
        "oip3_dbm": iip3_result["oip3_dbm"],
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
