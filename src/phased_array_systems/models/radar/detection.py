"""Radar detection probability and threshold calculations."""

from __future__ import annotations

import math
from typing import Literal

from scipy import integrate, optimize, special, stats

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
    return float(threshold)


def compute_pd_from_snr(
    snr_db: float,
    pfa: float,
    swerling: SwerlingModel = 0,
    n_pulses: int = 1,
    integration: Literal["coherent", "noncoherent"] = "noncoherent",
) -> float:
    """Compute probability of detection for given per-pulse SNR.

    Square-law detector statistics. Conditioned on the total received signal
    power s (in noise-power units), the normalized detector output follows a
    noncentral chi-square distribution with 2n degrees of freedom and
    noncentrality 2s, so Pd = Q_chi2'(2T; 2n, 2s) where T is the normalized
    threshold. Swerling fluctuation is the gamma-distributed mixture of s:

        Swerling 0: s = n*SNR (deterministic; Pd is the Marcum Q result)
        Swerling 1: s ~ Gamma(1, n*SNR)   (scan-to-scan Rayleigh)
        Swerling 2: s ~ Gamma(n, SNR)     (pulse-to-pulse Rayleigh; closed form)
        Swerling 3: s ~ Gamma(2, n*SNR/2) (scan-to-scan chi-4)
        Swerling 4: s ~ Gamma(2n, SNR/2)  (pulse-to-pulse chi-4)

    Coherent integration multiplies SNR by n and detects on a single sample;
    noncoherent integration uses the n-sample statistics directly (no separate
    empirical gain factor).

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
    if n_pulses < 1:
        raise ValueError("n_pulses must be >= 1")

    snr_linear = 10 ** (snr_db / 10)

    if integration == "coherent":
        # Coherent integration: full n-times SNR gain, single detection sample
        snr_linear *= n_pulses
        n = 1
    else:
        n = n_pulses

    threshold = compute_detection_threshold(pfa, n_samples=n)

    if swerling == 0:
        s = n * snr_linear
        pd = stats.ncx2.sf(2 * threshold, 2 * n, 2 * s)
    elif swerling == 2:
        # Sum of n independent exponential pulses with mean (1 + SNR)
        pd = special.gammaincc(n, threshold / (1 + snr_linear))
    elif swerling in (1, 3, 4):
        if swerling == 1:
            shape, scale = 1.0, n * snr_linear
        elif swerling == 3:
            shape, scale = 2.0, n * snr_linear / 2
        else:  # swerling == 4
            shape, scale = 2.0 * n, snr_linear / 2

        def integrand(s: float) -> float:
            return float(
                stats.ncx2.sf(2 * threshold, 2 * n, 2 * s) * stats.gamma.pdf(s, shape, scale=scale)
            )

        pd, _ = integrate.quad(integrand, 0, stats.gamma.ppf(1 - 1e-10, shape, scale=scale))
    else:
        raise ValueError(f"Unknown Swerling model: {swerling}")

    return max(0.0, min(1.0, float(pd)))


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
        return float(result)
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
