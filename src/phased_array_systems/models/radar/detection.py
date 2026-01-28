"""Radar detection probability and threshold calculations."""

from __future__ import annotations

import math
from typing import Literal

from scipy import optimize, special

SwerlingModel = Literal[0, 1, 2, 3, 4]


def compute_detection_threshold(
    pfa: float,
    n_samples: int = 1,
) -> float:
    """Compute detection threshold for given Pfa (CFAR).

    For non-fluctuating target (Swerling 0) with square-law detector.
    Uses the inverse incomplete gamma function.

    Args:
        pfa: Probability of false alarm (0 < pfa < 1)
        n_samples: Number of samples integrated (n >= 1)

    Returns:
        Normalized threshold (threshold / noise_power)
    """
    if not 0 < pfa < 1:
        raise ValueError("pfa must be between 0 and 1")
    if n_samples < 1:
        raise ValueError("n_samples must be >= 1")

    # For chi-squared distribution with 2*n degrees of freedom
    # P(X > threshold) = pfa
    # threshold = gammaincinv(n, 1 - pfa)
    threshold = special.gammaincinv(n_samples, 1 - pfa)
    return threshold


def compute_pd_from_snr(
    snr_db: float,
    pfa: float,
    swerling: SwerlingModel = 0,
    n_pulses: int = 1,
    integration: Literal["coherent", "noncoherent"] = "noncoherent",
) -> float:
    """Compute probability of detection for given SNR.

    Uses Marcum Q-function for Swerling 0 (non-fluctuating) targets.

    Args:
        snr_db: Signal-to-noise ratio per pulse (dB)
        pfa: Probability of false alarm
        swerling: Swerling target model (0 = non-fluctuating)
        n_pulses: Number of pulses integrated
        integration: Integration type ("coherent" or "noncoherent")

    Returns:
        Probability of detection (0-1)
    """
    if not 0 < pfa < 1:
        raise ValueError("pfa must be between 0 and 1")

    snr_linear = 10 ** (snr_db / 10)

    # Apply integration gain
    if integration == "coherent":
        # Coherent integration: SNR scales linearly with n
        snr_integrated = snr_linear * n_pulses
    else:
        # Non-coherent integration: approximate gain
        # Using empirical formula: effective SNR ≈ snr * n^0.8
        snr_integrated = snr_linear * (n_pulses ** 0.8)

    # Compute threshold from Pfa
    threshold = compute_detection_threshold(pfa, n_samples=1)

    # For Swerling 0 (non-fluctuating), use Marcum Q-function approximation
    # Pd = Q(sqrt(2*SNR), sqrt(2*threshold))
    # Using Rice distribution approximation
    if swerling == 0:
        # Marcum Q-function: Q_1(a, b) where a = sqrt(2*SNR), b = sqrt(threshold)
        a = math.sqrt(2 * snr_integrated)
        b = math.sqrt(2 * threshold)

        # Approximate Marcum Q using modified Bessel function
        # For high SNR, Pd ≈ 1 - 0.5 * erfc((a - b) / sqrt(2))
        if a > b:
            pd = 0.5 * special.erfc((b - a) / math.sqrt(2))
        else:
            pd = 0.5 * special.erfc((b - a) / math.sqrt(2))

        # Clamp to valid range
        return max(0.0, min(1.0, pd))

    elif swerling in (1, 2, 3, 4):
        # Swerling models with fluctuating RCS
        # Use empirical adjustment factors
        if swerling == 1:
            # Slow fluctuation, Rayleigh
            factor = 1.0 + 1.0 / snr_integrated if snr_integrated > 0 else 0
        elif swerling == 2:
            # Fast fluctuation, Rayleigh
            factor = 1.0 + 0.5 / snr_integrated if snr_integrated > 0 else 0
        elif swerling == 3:
            # Slow fluctuation, chi-squared (4 DOF)
            factor = 1.0 + 2.0 / snr_integrated if snr_integrated > 0 else 0
        else:  # swerling == 4
            # Fast fluctuation, chi-squared (4 DOF)
            factor = 1.0 + 1.0 / snr_integrated if snr_integrated > 0 else 0

        # Adjusted threshold
        adj_snr = snr_integrated / factor if factor > 0 else snr_integrated
        a = math.sqrt(2 * adj_snr)
        b = math.sqrt(2 * threshold)
        pd = 0.5 * special.erfc((b - a) / math.sqrt(2))
        return max(0.0, min(1.0, pd))

    else:
        raise ValueError(f"Unknown Swerling model: {swerling}")


def compute_snr_for_pd(
    pd: float,
    pfa: float,
    swerling: SwerlingModel = 0,
    n_pulses: int = 1,
    integration: Literal["coherent", "noncoherent"] = "noncoherent",
) -> float:
    """Compute required SNR for given Pd and Pfa.

    Inverse of compute_pd_from_snr using numerical root finding.

    Args:
        pd: Required probability of detection (0 < pd < 1)
        pfa: Probability of false alarm (0 < pfa < 1)
        swerling: Swerling target model (0-4)
        n_pulses: Number of pulses integrated
        integration: Integration type

    Returns:
        Required single-pulse SNR in dB
    """
    if not 0 < pd < 1:
        raise ValueError("pd must be between 0 and 1")
    if not 0 < pfa < 1:
        raise ValueError("pfa must be between 0 and 1")

    def objective(snr_db: float) -> float:
        pd_calc = compute_pd_from_snr(snr_db, pfa, swerling, n_pulses, integration)
        return pd_calc - pd

    # Use Albersheim as initial guess
    snr_guess = albersheim_snr(pd, pfa, n_pulses)

    try:
        result = optimize.brentq(objective, snr_guess - 20, snr_guess + 20)
        return result
    except ValueError:
        # If brentq fails, return Albersheim estimate
        return snr_guess


def albersheim_snr(
    pd: float,
    pfa: float,
    n_pulses: int = 1,
) -> float:
    """Albersheim's equation for required SNR (Swerling 0).

    Empirical approximation valid for:
    - 0.1 <= Pd <= 0.99
    - 1e-9 <= Pfa <= 1e-3
    - 1 <= n_pulses <= 8096

    Args:
        pd: Probability of detection
        pfa: Probability of false alarm
        n_pulses: Number of pulses (non-coherent integration)

    Returns:
        Required single-pulse SNR in dB
    """
    if not 0.1 <= pd <= 0.9999:
        raise ValueError("pd must be between 0.1 and 0.9999 for Albersheim")
    if not 1e-10 <= pfa <= 0.1:
        raise ValueError("pfa must be between 1e-10 and 0.1 for Albersheim")
    if n_pulses < 1:
        raise ValueError("n_pulses must be >= 1")

    # Albersheim's equation
    A = math.log(0.62 / pfa)
    B = math.log(pd / (1 - pd))

    # SNR required for n pulses (non-coherent integration)
    snr_n_db = -5 * math.log10(n_pulses) + (6.2 + 4.54 / math.sqrt(n_pulses + 0.44)) * math.log10(
        A + 0.12 * A * B + 1.7 * B
    )

    return snr_n_db


def swerling_snr_adjustment(
    swerling: SwerlingModel,
    pd: float,
    n_pulses: int = 1,
) -> float:
    """SNR adjustment factor for Swerling fluctuating targets.

    Returns additional SNR (in dB) needed relative to Swerling 0.

    Args:
        swerling: Swerling model (0-4)
        pd: Probability of detection
        n_pulses: Number of pulses

    Returns:
        SNR adjustment in dB (add to Swerling 0 requirement)
    """
    if swerling == 0:
        return 0.0

    # Empirical adjustments based on typical curves
    # These are approximate and depend on Pd
    if swerling == 1:
        # Slow Rayleigh - worst case
        if pd >= 0.9:
            return 8.0
        elif pd >= 0.5:
            return 4.0
        else:
            return 1.0
    elif swerling == 2:
        # Fast Rayleigh - better than Swerling 1
        if pd >= 0.9:
            return 6.0
        elif pd >= 0.5:
            return 2.0
        else:
            return 0.5
    elif swerling == 3:
        # Slow chi-squared - moderate
        if pd >= 0.9:
            return 4.0
        elif pd >= 0.5:
            return 2.0
        else:
            return 0.5
    elif swerling == 4:
        # Fast chi-squared - best fluctuating case
        if pd >= 0.9:
            return 2.0
        elif pd >= 0.5:
            return 1.0
        else:
            return 0.0

    return 0.0
