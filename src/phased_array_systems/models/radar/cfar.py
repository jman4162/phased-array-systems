"""Constant False Alarm Rate (CFAR) detection algorithms.

Implements threshold calculation for adaptive radar detection:
- CA-CFAR: Cell-Averaging CFAR
- OS-CFAR: Order-Statistic CFAR
- GO-CFAR: Greatest-Of CFAR
- SO-CFAR: Smallest-Of CFAR

References:
    - Richards, M. "Fundamentals of Radar Signal Processing", 2nd Ed.
    - Skolnik, M. "Radar Handbook", 3rd Ed., Ch. 7
"""

from __future__ import annotations

import math
from typing import Literal

from scipy import special

CFARType = Literal["CA", "OS", "GO", "SO"]


def ca_cfar_threshold_factor(
    n_ref: int,
    pfa: float,
) -> float:
    """Compute CA-CFAR threshold multiplier.

    Cell-Averaging CFAR estimates the noise/clutter power by
    averaging reference cells around the cell under test.

    Threshold = alpha * (mean of reference cells)

    where alpha is chosen to achieve desired Pfa.

    Args:
        n_ref: Total number of reference cells (both sides)
        pfa: Desired probability of false alarm

    Returns:
        Threshold multiplier (alpha)

    Raises:
        ValueError: If n_ref < 2 or pfa not in (0, 1)
    """
    if n_ref < 2:
        raise ValueError("n_ref must be >= 2")
    if not 0 < pfa < 1:
        raise ValueError("pfa must be between 0 and 1")

    # For sum of n_ref exponential random variables (square-law detector)
    # the threshold factor is:
    # alpha = n_ref * (Pfa^(-1/n_ref) - 1)
    alpha = n_ref * (pfa ** (-1.0 / n_ref) - 1)

    return alpha


def os_cfar_threshold_factor(
    n_ref: int,
    k: int,
    pfa: float,
) -> float:
    """Compute OS-CFAR threshold multiplier.

    Order-Statistic CFAR selects the k-th largest sample from
    the reference cells as the noise estimate. This provides
    robustness against clutter edges and interfering targets.

    Typically k ≈ 3*n_ref/4 for good tradeoff.

    Args:
        n_ref: Total number of reference cells
        k: Order statistic index (1 = smallest, n_ref = largest)
        pfa: Desired probability of false alarm

    Returns:
        Threshold multiplier

    Raises:
        ValueError: If parameters invalid
    """
    if n_ref < 2:
        raise ValueError("n_ref must be >= 2")
    if not 1 <= k <= n_ref:
        raise ValueError("k must be between 1 and n_ref")
    if not 0 < pfa < 1:
        raise ValueError("pfa must be between 0 and 1")

    # OS-CFAR threshold for exponential noise
    # Uses incomplete beta function relationship

    # Approximation for threshold factor
    # alpha ≈ (n_ref - k + 1) / k * Pfa^(-1/(n_ref-k+1)) - 1
    m = n_ref - k + 1

    alpha = pfa ** (-1.0 / n_ref) - 1 if m == 1 else m / k * (pfa ** (-1.0 / m) - 1)

    return alpha


def go_cfar_threshold_factor(
    n_ref_half: int,
    pfa: float,
) -> float:
    """Compute GO-CFAR (Greatest-Of) threshold multiplier.

    GO-CFAR takes the greater of the means from leading and
    lagging reference windows. This helps at clutter edges
    but increases detection loss in homogeneous clutter.

    Args:
        n_ref_half: Number of reference cells per side
        pfa: Desired probability of false alarm

    Returns:
        Threshold multiplier

    Raises:
        ValueError: If parameters invalid
    """
    if n_ref_half < 1:
        raise ValueError("n_ref_half must be >= 1")
    if not 0 < pfa < 1:
        raise ValueError("pfa must be between 0 and 1")

    # GO-CFAR Pfa is related to CA-CFAR Pfa by:
    # Pfa_GO ≈ 2 * Pfa_CA - Pfa_CA^2
    # Solve for equivalent CA-CFAR Pfa
    pfa_ca = 1 - math.sqrt(1 - pfa)

    # Use CA-CFAR formula with equivalent Pfa
    alpha = n_ref_half * (pfa_ca ** (-1.0 / n_ref_half) - 1)

    return alpha


def so_cfar_threshold_factor(
    n_ref_half: int,
    pfa: float,
) -> float:
    """Compute SO-CFAR (Smallest-Of) threshold multiplier.

    SO-CFAR takes the smaller of the means from leading and
    lagging reference windows. This minimizes detection loss
    but is vulnerable to interfering targets.

    Args:
        n_ref_half: Number of reference cells per side
        pfa: Desired probability of false alarm

    Returns:
        Threshold multiplier

    Raises:
        ValueError: If parameters invalid
    """
    if n_ref_half < 1:
        raise ValueError("n_ref_half must be >= 1")
    if not 0 < pfa < 1:
        raise ValueError("pfa must be between 0 and 1")

    # SO-CFAR has higher Pfa than CA-CFAR for same threshold
    # Pfa_SO ≈ Pfa_CA^2
    # Solve for equivalent CA-CFAR Pfa
    pfa_ca = math.sqrt(pfa)

    # Use CA-CFAR formula with equivalent Pfa
    alpha = n_ref_half * (pfa_ca ** (-1.0 / n_ref_half) - 1)

    return alpha


def cfar_threshold_factor(
    cfar_type: CFARType,
    n_ref: int,
    pfa: float,
    os_k: int | None = None,
) -> float:
    """Compute CFAR threshold multiplier for specified type.

    Args:
        cfar_type: Type of CFAR ("CA", "OS", "GO", "SO")
        n_ref: Total number of reference cells (or per side for GO/SO)
        pfa: Desired probability of false alarm
        os_k: Order statistic index for OS-CFAR (required if cfar_type="OS")

    Returns:
        Threshold multiplier

    Raises:
        ValueError: If parameters invalid
    """
    if cfar_type == "CA":
        return ca_cfar_threshold_factor(n_ref, pfa)
    elif cfar_type == "OS":
        if os_k is None:
            # Default: 3/4 of n_ref
            os_k = max(1, int(0.75 * n_ref))
        return os_cfar_threshold_factor(n_ref, os_k, pfa)
    elif cfar_type == "GO":
        # n_ref is per side for GO
        return go_cfar_threshold_factor(n_ref, pfa)
    elif cfar_type == "SO":
        # n_ref is per side for SO
        return so_cfar_threshold_factor(n_ref, pfa)
    else:
        raise ValueError(f"Unknown CFAR type: {cfar_type}")


def cfar_loss_db(
    cfar_type: CFARType,
    n_ref: int,
    pfa: float = 1e-6,
) -> float:
    """Compute CFAR detection loss relative to ideal threshold.

    CFAR has inherent loss compared to a fixed (ideal) threshold
    due to threshold estimation noise. Loss decreases with more
    reference cells.

    Args:
        cfar_type: Type of CFAR
        n_ref: Number of reference cells
        pfa: Probability of false alarm

    Returns:
        CFAR loss in dB (always positive)
    """
    if n_ref < 2:
        return 10.0  # Very high loss with few cells

    # CA-CFAR loss (approximation)
    # Loss ≈ 10*log10(1 + 2/n_ref) for moderate n_ref
    if cfar_type == "CA":
        loss = 10 * math.log10(1 + 2.0 / n_ref)
    elif cfar_type == "OS":
        # OS-CFAR typically has 0.5-1 dB more loss than CA
        loss = 10 * math.log10(1 + 3.0 / n_ref)
    elif cfar_type == "GO":
        # GO-CFAR has ~1 dB more loss than CA in homogeneous
        loss = 10 * math.log10(1 + 4.0 / n_ref)
    elif cfar_type == "SO":
        # SO-CFAR has least loss but worst interference rejection
        loss = 10 * math.log10(1 + 1.5 / n_ref)
    else:
        loss = 10 * math.log10(1 + 2.0 / n_ref)

    return loss


def cfar_required_snr_adjustment(
    cfar_type: CFARType,
    n_ref: int,
    pd: float = 0.9,
    pfa: float = 1e-6,
) -> float:
    """Compute additional SNR required due to CFAR processing.

    This includes CFAR loss and the threshold adjustment needed
    to maintain the desired Pd/Pfa.

    Args:
        cfar_type: Type of CFAR
        n_ref: Number of reference cells
        pd: Probability of detection
        pfa: Probability of false alarm

    Returns:
        Additional SNR required in dB
    """
    # Base CFAR loss
    loss = cfar_loss_db(cfar_type, n_ref, pfa)

    # High Pd requires more margin
    if pd >= 0.99:
        pd_factor = 0.5
    elif pd >= 0.9:
        pd_factor = 0.3
    else:
        pd_factor = 0.0

    return loss + pd_factor


def optimal_reference_cells(
    range_resolution_m: float,
    clutter_extent_m: float = 1000.0,
    guard_cells: int = 2,
) -> int:
    """Suggest optimal number of reference cells.

    The number of reference cells should be:
    1. Large enough for accurate noise estimate (reduces CFAR loss)
    2. Small enough to stay within homogeneous clutter region

    Args:
        range_resolution_m: Range resolution (c/2B)
        clutter_extent_m: Expected clutter cell extent (m)
        guard_cells: Number of guard cells on each side

    Returns:
        Recommended number of reference cells per side
    """
    # Each cell spans one range resolution
    max_cells = int(clutter_extent_m / range_resolution_m / 2) - guard_cells

    # Want at least 8 cells total for reasonable CFAR loss
    min_cells = 8

    # Typical maximum is 32 cells per side
    max_recommended = 32

    n_cells = max(min_cells, min(max_cells, max_recommended))

    return n_cells


def compute_pd_with_cfar(
    snr_db: float,
    cfar_type: CFARType,
    n_ref: int,
    pfa: float = 1e-6,
) -> float:
    """Compute probability of detection including CFAR loss.

    Args:
        snr_db: Signal-to-noise ratio (dB)
        cfar_type: Type of CFAR detector
        n_ref: Number of reference cells
        pfa: Probability of false alarm

    Returns:
        Probability of detection (0-1)
    """
    # Effective SNR after CFAR loss
    loss = cfar_loss_db(cfar_type, n_ref, pfa)
    effective_snr_db = snr_db - loss

    # Convert to linear
    snr_linear = 10 ** (effective_snr_db / 10)

    # Threshold from Pfa (normalized)
    threshold = special.gammaincinv(1, 1 - pfa)

    # Marcum Q approximation for Pd
    a = math.sqrt(2 * snr_linear)
    b = math.sqrt(2 * threshold)

    pd = 0.5 * special.erfc((b - a) / math.sqrt(2))

    return max(0.0, min(1.0, pd))
