"""Taper loss and beamformer efficiency models.

This module provides system-level models for amplitude tapering effects:
- Taper efficiency (aperture illumination efficiency)
- Taper loss estimation from sidelobe level requirements
- Beamformer noise contribution with non-uniform weighting

These models connect antenna-level tapering to system performance metrics,
complementing the detailed taper functions in phased-array-modeling.

Key Concepts:
    - Taper efficiency: (sum of weights)^2 / (N * sum of weights^2)
    - Taper loss: Reduction in directivity due to non-uniform illumination
    - Beamformer noise: Noise contribution from combining network

References:
    - Balanis, C. "Antenna Theory: Analysis and Design"
    - Mailloux, R.J. "Phased Array Antenna Handbook"
    - Your PowerPoint: Section on amplitude tapering
"""

from __future__ import annotations

import math
import warnings
from typing import Literal

import numpy as np
from numpy.typing import NDArray
from scipy.signal import windows

TaperType = Literal["uniform", "taylor", "chebyshev", "hamming", "cosine", "gaussian"]


def generate_taper_weights(
    taper_type: TaperType,
    n: int,
    sll_db: float = -30.0,
) -> NDArray[np.floating]:
    """Generate a 1-D amplitude taper from standard window functions.

    Args:
        taper_type: Window type. "taylor" and "chebyshev" honor sll_db;
            "hamming"/"cosine"/"gaussian" have fixed shapes ("gaussian"
            uses std = n/6).
        n: Number of elements
        sll_db: Design sidelobe level (dB, negative) for taylor/chebyshev

    Returns:
        Array of n linear amplitude weights, peak-normalized

    Raises:
        ValueError: For unknown taper types
    """
    if n < 1:
        raise ValueError("n must be >= 1")

    sll = abs(sll_db)
    if taper_type == "uniform":
        w = np.ones(n)
    elif taper_type == "taylor":
        w = windows.taylor(n, nbar=max(2, int(round(0.15 * sll))), sll=sll, norm=False)
    elif taper_type == "chebyshev":
        # chebwin warns below 45 dB attenuation about spectral-analysis
        # noise bandwidth; irrelevant for aperture tapering
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            w = np.asarray(windows.chebwin(n, at=sll))
    elif taper_type == "hamming":
        w = windows.hamming(n)
    elif taper_type == "cosine":
        w = windows.cosine(n)
    elif taper_type == "gaussian":
        w = windows.gaussian(n, std=n / 6)
    else:
        raise ValueError(f"Unknown taper type: {taper_type}")

    w = np.asarray(w, dtype=float)
    return np.asarray(w / w.max())


def compute_taper_loss(taper: NDArray[np.floating]) -> float:
    """Compute directivity loss from an amplitude taper.

    The taper loss represents the reduction in peak directivity
    compared to uniform illumination due to non-uniform weighting.

    Args:
        taper: Array of amplitude weights (linear, not dB)

    Returns:
        Taper loss in dB (positive value representing loss)

    Examples:
        >>> import numpy as np
        >>> uniform = np.ones(16)
        >>> loss = compute_taper_loss(uniform)
        >>> np.isclose(loss, 0.0)  # No loss for uniform
        True

        >>> taylor = np.array([0.5, 0.7, 0.9, 1.0, 1.0, 0.9, 0.7, 0.5])
        >>> loss = compute_taper_loss(taylor)
        >>> 0 < loss < 2  # Typical Taylor loss
        True

    Notes:
        Taper efficiency = (Σw)² / (N × Σw²)
        Taper loss = -10*log10(efficiency)
    """
    taper = np.asarray(taper)
    n = len(taper)

    if n == 0:
        return 0.0

    sum_weights = np.sum(taper)
    sum_weights_sq = np.sum(taper**2)

    if sum_weights_sq == 0:
        return float("inf")

    efficiency = (sum_weights**2) / (n * sum_weights_sq)
    loss_db = -10 * math.log10(efficiency) if efficiency > 0 else float("inf")

    return max(0.0, loss_db)


def compute_taper_efficiency(taper: NDArray[np.floating]) -> float:
    """Compute aperture efficiency for an amplitude taper.

    This is the inverse calculation of taper loss.

    Args:
        taper: Array of amplitude weights (linear)

    Returns:
        Efficiency as fraction (0 to 1)

    Examples:
        >>> import numpy as np
        >>> uniform = np.ones(16)
        >>> eff = compute_taper_efficiency(uniform)
        >>> np.isclose(eff, 1.0)
        True
    """
    taper = np.asarray(taper)
    n = len(taper)

    if n == 0:
        return 1.0

    sum_weights = np.sum(taper)
    sum_weights_sq = np.sum(taper**2)

    if sum_weights_sq == 0:
        return 0.0

    return float((sum_weights**2) / (n * sum_weights_sq))


def taper_loss_from_sll(
    target_sll_db: float,
    taper_type: Literal["taylor", "chebyshev", "hamming", "cosine", "gaussian"] = "taylor",
) -> float:
    """Estimate taper loss from target sidelobe level.

    Provides approximate taper loss for common window types at
    specified sidelobe levels, useful for system-level trade studies.

    Args:
        target_sll_db: Target sidelobe level in dB (negative value)
        taper_type: Type of amplitude taper

    Returns:
        Estimated taper loss in dB

    Examples:
        >>> loss = taper_loss_from_sll(-30, 'taylor')
        >>> 0.2 < loss < 1.5  # Typical Taylor loss for -30 dB SLL
        True

        >>> loss = taper_loss_from_sll(-40, 'taylor')
        >>> loss > taper_loss_from_sll(-30, 'taylor')  # Lower SLL = more loss
        True

    Notes:
        Computed from the actual window function (n=64 representative
        length) rather than a fitted curve; taper efficiency is nearly
        length-independent for n >= 16.
    """
    weights = generate_taper_weights(taper_type, 64, target_sll_db)
    return compute_taper_loss(weights)


def beamformer_noise_factor(
    taper: NDArray[np.floating],
    component_temps_k: NDArray[np.floating] | None = None,
    reference_temp_k: float = 290.0,
) -> float:
    """Compute noise factor contribution from beamformer combining network.

    When element signals are combined with non-uniform weights, the
    effective noise from the combining network depends on the weight
    distribution.

    Args:
        taper: Array of amplitude weights (linear)
        component_temps_k: Noise temperature of each element's path (Kelvin)
            If None, assumes all equal to reference temperature
        reference_temp_k: Reference temperature for noise calculations

    Returns:
        Beamformer noise factor (linear, not dB)

    Examples:
        >>> import numpy as np
        >>> uniform = np.ones(16)
        >>> nf = beamformer_noise_factor(uniform)
        >>> np.isclose(nf, 1.0)  # Uniform = no excess noise
        True

    Notes:
        This is the temperature-inhomogeneity factor only:

            F_bf = sum(w_i^2 * T_i) / (sum(w_i^2) * T_mean)

        It equals 1.0 whenever all element noise temperatures are equal,
        regardless of taper. The SNR penalty of tapering itself is already
        carried by the taper loss on gain; including it here again would
        double-count it.
    """
    taper = np.asarray(taper)
    n = len(taper)

    if n == 0:
        return 1.0

    if component_temps_k is None:
        component_temps_k = np.full(n, reference_temp_k)
    else:
        component_temps_k = np.asarray(component_temps_k)

    sum_weights_sq = np.sum(taper**2)
    if sum_weights_sq == 0:
        return float("inf")

    t_mean = float(np.mean(component_temps_k))
    if t_mean == 0:
        return 1.0

    t_weighted = float(np.sum((taper**2) * component_temps_k)) / float(sum_weights_sq)
    return t_weighted / t_mean


def estimate_taper_parameters(
    target_sll_db: float,
    taper_type: Literal["taylor", "chebyshev"] = "taylor",
) -> dict:
    """Estimate taper parameters to achieve target sidelobe level.

    Provides recommended parameters for common taper types.

    Args:
        target_sll_db: Target sidelobe level in dB (negative value)
        taper_type: Type of taper ('taylor' or 'chebyshev')

    Returns:
        Dictionary with recommended parameters:
            - 'nbar': For Taylor, number of nearly equal sidelobes
            - 'estimated_loss_db': Expected taper loss
            - 'beamwidth_factor': Beamwidth increase factor

    Examples:
        >>> params = estimate_taper_parameters(-35, 'taylor')
        >>> params['nbar']
        5
        >>> 0 < params['estimated_loss_db'] < 2
        True
    """
    sll = abs(target_sll_db)

    if taper_type == "taylor":
        # Recommended nbar increases with SLL
        if sll <= 25:
            nbar = 3
        elif sll <= 30:
            nbar = 4
        elif sll <= 35:
            nbar = 5
        elif sll <= 40:
            nbar = 6
        else:
            nbar = 8

        # Beamwidth factor (approximate)
        bw_factor = 1.0 + 0.008 * (sll - 13.2)

        return {
            "nbar": nbar,
            "estimated_loss_db": taper_loss_from_sll(target_sll_db, "taylor"),
            "beamwidth_factor": min(bw_factor, 1.5),
        }

    elif taper_type == "chebyshev":
        # Chebyshev has no nbar parameter
        bw_factor = 1.0 + 0.007 * (sll - 13.2)

        return {
            "estimated_loss_db": taper_loss_from_sll(target_sll_db, "chebyshev"),
            "beamwidth_factor": min(bw_factor, 1.4),
        }

    else:
        raise ValueError(f"Unsupported taper type for parameter estimation: {taper_type}")


def aperture_efficiency_components(
    taper: NDArray[np.floating],
    phase_error_rms_deg: float = 0.0,
    amplitude_error_rms_db: float = 0.0,
    blockage_fraction: float = 0.0,
) -> dict:
    """Compute aperture efficiency breakdown for an array.

    Provides detailed efficiency components for system-level analysis.

    Args:
        taper: Amplitude taper weights
        phase_error_rms_deg: RMS phase error across aperture
        amplitude_error_rms_db: RMS amplitude error
        blockage_fraction: Fraction of aperture blocked (0 to 1)

    Returns:
        Dictionary with efficiency components:
            - 'illumination_efficiency': Due to amplitude taper
            - 'phase_efficiency': Due to phase errors
            - 'amplitude_error_efficiency': Due to amplitude errors
            - 'blockage_efficiency': Due to blockage
            - 'total_efficiency': Product of all components

    Examples:
        >>> import numpy as np
        >>> taper = np.ones(64)
        >>> eff = aperture_efficiency_components(taper, phase_error_rms_deg=5)
        >>> eff['total_efficiency'] < 1.0
        True
    """
    # Illumination efficiency
    eta_illum = compute_taper_efficiency(taper)

    # Phase efficiency: exp(-sigma_phi^2) where sigma in radians
    sigma_phi = math.radians(phase_error_rms_deg)
    eta_phase = math.exp(-(sigma_phi**2))

    # Amplitude error efficiency: 1/(1+sigma_a^2) with sigma_a the
    # fractional RMS amplitude error (Ruze form; Mailloux sec. 7.2).
    # dB-to-fractional conversion is a small-error approximation.
    sigma_a_linear = (10 ** (abs(amplitude_error_rms_db) / 20)) - 1
    eta_amp = 1.0 / (1.0 + sigma_a_linear**2)

    # Blockage efficiency
    eta_blockage = (1 - blockage_fraction) ** 2

    # Total
    eta_total = eta_illum * eta_phase * eta_amp * eta_blockage

    return {
        "illumination_efficiency": eta_illum,
        "phase_efficiency": eta_phase,
        "amplitude_error_efficiency": eta_amp,
        "blockage_efficiency": eta_blockage,
        "total_efficiency": eta_total,
        "total_loss_db": -10 * math.log10(eta_total) if eta_total > 0 else float("inf"),
    }
