"""Pulse integration gain calculations."""

from __future__ import annotations

import math


def coherent_integration_gain(n_pulses: int) -> float:
    """Coherent integration gain in dB.

    Coherent integration (phase-preserving) provides full N-times
    improvement in SNR because signals add coherently while noise
    adds incoherently.

    Args:
        n_pulses: Number of pulses integrated (must be >= 1)

    Returns:
        Integration gain in dB: 10 * log10(n_pulses)

    Raises:
        ValueError: If n_pulses < 1
    """
    if n_pulses < 1:
        raise ValueError("n_pulses must be >= 1")

    if n_pulses == 1:
        return 0.0

    return 10 * math.log10(n_pulses)


def noncoherent_integration_gain(
    n_pulses: int,
    pd: float = 0.9,
    pfa: float = 1e-6,
) -> float:
    """Non-coherent integration gain in dB.

    Non-coherent integration (magnitude-only) provides less than
    full N-times gain because both signal and noise magnitudes
    are combined. The efficiency depends on SNR and Pd/Pfa.

    Uses empirical approximation: gain ≈ 10 * log10(n^efficiency)
    where efficiency ≈ 0.8 for typical radar parameters.

    Args:
        n_pulses: Number of pulses integrated (must be >= 1)
        pd: Probability of detection (affects efficiency)
        pfa: Probability of false alarm (affects efficiency)

    Returns:
        Integration gain in dB (always <= coherent gain)

    Raises:
        ValueError: If n_pulses < 1
    """
    if n_pulses < 1:
        raise ValueError("n_pulses must be >= 1")

    if n_pulses == 1:
        return 0.0

    # Efficiency factor depends on operating point
    # Higher Pd requires higher SNR, reducing integration efficiency
    if pd >= 0.99:
        efficiency = 0.7
    elif pd >= 0.9:
        efficiency = 0.8
    elif pd >= 0.5:
        efficiency = 0.85
    else:
        efficiency = 0.9

    # Non-coherent gain: approximately n^efficiency
    return 10 * efficiency * math.log10(n_pulses)


def integration_loss(
    n_pulses: int,
    integration_type: str = "noncoherent",
    pd: float = 0.9,
    pfa: float = 1e-6,
) -> float:
    """Integration efficiency loss relative to coherent integration.

    Computes how much SNR is "lost" by using non-coherent instead
    of coherent integration.

    Args:
        n_pulses: Number of pulses integrated
        integration_type: "coherent" or "noncoherent"
        pd: Probability of detection (for non-coherent efficiency)
        pfa: Probability of false alarm (for non-coherent efficiency)

    Returns:
        Integration loss in dB (0 for coherent, > 0 for non-coherent)
    """
    if integration_type == "coherent":
        return 0.0

    coherent = coherent_integration_gain(n_pulses)
    noncoherent = noncoherent_integration_gain(n_pulses, pd, pfa)

    return coherent - noncoherent


def binary_integration_gain(
    n_pulses: int,
    m_of_n: int,
) -> float:
    """Binary (M-of-N) integration gain in dB.

    Binary integration declares detection if at least M pulses
    out of N exceed the threshold. Less efficient than non-coherent
    but simpler to implement.

    Args:
        n_pulses: Total number of pulses (N)
        m_of_n: Required number of detections (M)

    Returns:
        Approximate integration gain in dB
    """
    if m_of_n > n_pulses:
        raise ValueError("m_of_n must be <= n_pulses")
    if m_of_n < 1:
        raise ValueError("m_of_n must be >= 1")
    if n_pulses < 1:
        raise ValueError("n_pulses must be >= 1")

    if n_pulses == 1:
        return 0.0

    # Empirical approximation
    # Efficiency is approximately m/n * non-coherent efficiency
    ratio = m_of_n / n_pulses
    efficiency = 0.7 * ratio + 0.1  # Ranges from ~0.1 to ~0.8

    return 10 * efficiency * math.log10(n_pulses)
