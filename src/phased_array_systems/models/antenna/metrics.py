"""Antenna pattern metric extraction utilities."""

import math

import numpy as np
from numpy.typing import NDArray


def compute_beamwidth(
    pattern_db: NDArray[np.floating],
    angles_deg: NDArray[np.floating],
    level_db: float = -3.0,
) -> float:
    """Compute beamwidth at specified level below peak.

    Args:
        pattern_db: Pattern magnitude in dB
        angles_deg: Corresponding angles in degrees
        level_db: Level below peak to measure (default -3 dB)

    Returns:
        Beamwidth in degrees, or NaN if not found
    """
    peak_db = np.max(pattern_db)
    threshold = peak_db + level_db  # level_db is negative

    # Find peak index
    peak_idx = np.argmax(pattern_db)

    # Search left from peak
    left_idx = peak_idx
    for i in range(peak_idx, -1, -1):
        if pattern_db[i] < threshold:
            left_idx = i
            break

    # Search right from peak
    right_idx = peak_idx
    for i in range(peak_idx, len(pattern_db)):
        if pattern_db[i] < threshold:
            right_idx = i
            break

    if left_idx == peak_idx or right_idx == peak_idx:
        return float("nan")

    # Linear interpolation for more accurate crossing points
    left_angle = np.interp(threshold, [pattern_db[left_idx], pattern_db[left_idx + 1]],
                           [angles_deg[left_idx], angles_deg[left_idx + 1]])
    right_angle = np.interp(threshold, [pattern_db[right_idx], pattern_db[right_idx - 1]],
                            [angles_deg[right_idx], angles_deg[right_idx - 1]])

    return abs(right_angle - left_angle)


def compute_sidelobe_level(
    pattern_db: NDArray[np.floating],
    angles_deg: NDArray[np.floating],
    main_lobe_width_deg: float | None = None,
) -> float:
    """Compute peak sidelobe level relative to main beam.

    Args:
        pattern_db: Pattern magnitude in dB
        angles_deg: Corresponding angles in degrees
        main_lobe_width_deg: Width of main lobe to exclude (auto-detected if None)

    Returns:
        Peak sidelobe level in dB (negative value)
    """
    peak_db = np.max(pattern_db)
    peak_idx = np.argmax(pattern_db)
    peak_angle = angles_deg[peak_idx]

    # Auto-detect main lobe width if not provided
    if main_lobe_width_deg is None:
        bw = compute_beamwidth(pattern_db, angles_deg, -3.0)
        if np.isnan(bw):
            bw = 10.0  # Default fallback
        main_lobe_width_deg = bw * 2  # Use 2x beamwidth as exclusion zone

    # Mask out main lobe region
    half_width = main_lobe_width_deg / 2
    mask = np.abs(angles_deg - peak_angle) > half_width

    if not np.any(mask):
        return float("-inf")

    sidelobe_pattern = pattern_db[mask]
    peak_sidelobe_db = np.max(sidelobe_pattern)

    return peak_sidelobe_db - peak_db


def compute_scan_loss(scan_angle_deg: float, model: str = "cosine") -> float:
    """Compute scan loss for a phased array at given scan angle.

    Args:
        scan_angle_deg: Scan angle from boresight (degrees)
        model: Scan loss model ("cosine" or "cosine_squared")

    Returns:
        Scan loss in dB (positive value representing loss)
    """
    if scan_angle_deg >= 90:
        return float("inf")

    scan_rad = math.radians(scan_angle_deg)

    if model == "cosine":
        # Standard cos(theta) scan loss
        loss_linear = math.cos(scan_rad)
    elif model == "cosine_squared":
        # More aggressive cos^2(theta) model
        loss_linear = math.cos(scan_rad) ** 2
    else:
        raise ValueError(f"Unknown scan loss model: {model}")

    if loss_linear <= 0:
        return float("inf")

    loss_db = -10 * math.log10(loss_linear)
    return abs(loss_db) if abs(loss_db) < 1e-10 else loss_db  # Avoid -0.0 display


def compute_array_gain(n_elements: int, element_gain_db: float = 0.0) -> float:
    """Compute ideal array gain.

    Args:
        n_elements: Number of array elements
        element_gain_db: Individual element gain (dB)

    Returns:
        Array gain in dB
    """
    if n_elements < 1:
        raise ValueError("n_elements must be >= 1")

    array_factor_db = 10 * math.log10(n_elements)
    return element_gain_db + array_factor_db


def compute_directivity_rectangular(
    nx: int, ny: int, dx_lambda: float, dy_lambda: float
) -> float:
    """Estimate directivity for a rectangular array.

    Uses the approximation: D = pi * (2*nx*dx) * (2*ny*dy) for large arrays.

    Args:
        nx: Number of elements in x
        ny: Number of elements in y
        dx_lambda: Element spacing in x (wavelengths)
        dy_lambda: Element spacing in y (wavelengths)

    Returns:
        Directivity in dB
    """
    # Aperture dimensions in wavelengths
    lx = nx * dx_lambda
    ly = ny * dy_lambda

    # Directivity approximation for uniform aperture
    # D ≈ 4*pi*A/lambda^2 = 4*pi*Lx*Ly (when Lx, Ly in wavelengths)
    directivity_linear = 4 * math.pi * lx * ly

    return 10 * math.log10(directivity_linear)
