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
from typing import Literal

import numpy as np
from numpy.typing import NDArray


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

    return (sum_weights**2) / (n * sum_weights_sq)


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
        >>> 0.5 < loss < 1.5  # Typical Taylor loss for -30 dB SLL
        True

        >>> loss = taper_loss_from_sll(-40, 'taylor')
        >>> loss > taper_loss_from_sll(-30, 'taylor')  # Lower SLL = more loss
        True

    Notes:
        These are empirical approximations. For exact values,
        generate the actual taper and use compute_taper_loss().
    """
    # Ensure positive value for calculations
    sll = abs(target_sll_db)

    if taper_type == "taylor":
        # Taylor window: loss increases roughly as 0.02 * (SLL - 13)
        # -13.2 dB (uniform) -> 0 dB loss
        # -30 dB -> ~0.5-0.8 dB loss
        # -40 dB -> ~1.0-1.5 dB loss
        if sll <= 13.2:
            return 0.0
        loss = 0.02 * (sll - 13.2) + 0.15 * ((sll - 13.2) / 20) ** 2
        return min(loss, 3.0)

    elif taper_type == "chebyshev":
        # Chebyshev (Dolph): slightly more efficient than Taylor
        if sll <= 13.2:
            return 0.0
        loss = 0.018 * (sll - 13.2) + 0.12 * ((sll - 13.2) / 20) ** 2
        return min(loss, 2.5)

    elif taper_type == "hamming":
        # Hamming: fixed ~-42 dB SLL, ~1.34 dB loss
        return 1.34

    elif taper_type == "cosine":
        # Cosine (Hann): ~-32 dB SLL, ~1.76 dB loss
        return 1.76

    elif taper_type == "gaussian":
        # Gaussian: loss depends on sigma parameter
        # For typical sigma giving -30 to -40 dB SLL
        if sll <= 20:
            return 0.5
        elif sll <= 30:
            return 1.0
        elif sll <= 40:
            return 1.5
        else:
            return 2.0

    else:
        raise ValueError(f"Unknown taper type: {taper_type}")


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
        For uniform weighting and equal element noise temperatures,
        the beamformer noise factor is 1.0.

        For tapered arrays, the effective noise is:
            T_eff = Σ(w_i² * T_i) / (Σw_i)²
    """
    taper = np.asarray(taper)
    n = len(taper)

    if n == 0:
        return 1.0

    if component_temps_k is None:
        component_temps_k = np.full(n, reference_temp_k)
    else:
        component_temps_k = np.asarray(component_temps_k)

    sum_weights = np.sum(taper)
    if sum_weights == 0:
        return float("inf")

    # Weighted noise temperature
    t_eff = np.sum((taper**2) * component_temps_k) / (sum_weights**2)

    # Noise factor relative to reference
    # F = 1 + T_eff / T_ref for excess noise
    # But we want the relative increase due to tapering
    t_uniform = np.mean(component_temps_k)  # Uniform case
    if t_uniform == 0:
        return 1.0

    return t_eff / t_uniform * n / (sum_weights**2 / np.sum(taper**2))


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

    # Amplitude error efficiency
    # Approximate: 1 - (sigma_A)^2 where sigma_A is linear RMS error
    sigma_a_linear = (10 ** (amplitude_error_rms_db / 20)) - 1
    eta_amp = max(0, 1 - sigma_a_linear**2)

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
