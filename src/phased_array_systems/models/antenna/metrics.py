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
    peak_idx = int(np.argmax(pattern_db))

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

    if left_idx == peak_idx and right_idx == peak_idx:
        # Pattern never drops below the threshold on either side.
        return float("nan")

    # Linear interpolation for more accurate crossing points. When the
    # peak sits at (or the pattern never crosses on) one edge of the cut —
    # routine for principal-plane cuts of a steered beam — mirror the side
    # that was found instead of reporting NaN.
    peak_angle = float(angles_deg[peak_idx])
    left_angle: float | None = None
    right_angle: float | None = None
    if left_idx != peak_idx:
        left_angle = float(
            np.interp(
                threshold,
                [pattern_db[left_idx], pattern_db[left_idx + 1]],
                [angles_deg[left_idx], angles_deg[left_idx + 1]],
            )
        )
    if right_idx != peak_idx:
        right_angle = float(
            np.interp(
                threshold,
                [pattern_db[right_idx], pattern_db[right_idx - 1]],
                [angles_deg[right_idx], angles_deg[right_idx - 1]],
            )
        )
    if left_angle is None:
        assert right_angle is not None
        return float(2.0 * abs(right_angle - peak_angle))
    if right_angle is None:
        return float(2.0 * abs(peak_angle - left_angle))
    return float(abs(right_angle - left_angle))


def _first_null_index(
    pattern_db: NDArray[np.floating],
    peak_idx: int,
    step: int,
) -> int | None:
    """Walk outward from the peak to the first null on one side.

    Args:
        pattern_db: Pattern magnitude in dB
        peak_idx: Index of the main-beam peak
        step: -1 to walk left, +1 to walk right

    Returns:
        Index of the first local minimum encountered, or None if the pattern
        decays monotonically to the end of the array on that side.
    """
    n = len(pattern_db)
    i = peak_idx
    # A rise of more than this counts as leaving the null, which keeps
    # floating-point wobble at the bottom of a deep null from stopping the walk.
    rise_tol = 1e-9
    while 0 <= i + step < n:
        if pattern_db[i + step] > pattern_db[i] + rise_tol:
            return i
        i += step
    return None


def compute_sidelobe_level(
    pattern_db: NDArray[np.floating],
    angles_deg: NDArray[np.floating],
    main_lobe_width_deg: float | None = None,
) -> float:
    """Compute peak sidelobe level relative to main beam.

    The main lobe is excluded out to its first null on each side. A mask
    derived from the half-power beamwidth is not wide enough: the first null
    of a tapered aperture sits at roughly 1.3 to 1.8 times the HPBW from the
    peak, and further as the taper deepens, so a beamwidth-derived mask leaves
    the main-lobe skirt in the search region and reports a point on that skirt
    as the sidelobe. That reading is both far too high and non-monotonic in
    taper depth.

    Args:
        pattern_db: Pattern magnitude in dB
        angles_deg: Corresponding angles in degrees
        main_lobe_width_deg: Explicit main-lobe width to exclude, in degrees,
            centered on the peak. Overrides first-null detection.

    Returns:
        Peak sidelobe level in dB (negative value), or -inf if the pattern has
        no sidelobe outside the main beam.
    """
    pattern_db = np.asarray(pattern_db, dtype=float)
    angles_deg = np.asarray(angles_deg, dtype=float)

    peak_db = float(np.max(pattern_db))
    peak_idx = int(np.argmax(pattern_db))

    if main_lobe_width_deg is not None:
        peak_angle = float(angles_deg[peak_idx])
        half_width = main_lobe_width_deg / 2
        mask = np.abs(angles_deg - peak_angle) > half_width
    else:
        left_null = _first_null_index(pattern_db, peak_idx, -1)
        right_null = _first_null_index(pattern_db, peak_idx, +1)
        # A side with no null has no sidelobe on it, so mask it out entirely.
        lo = 0 if left_null is None else left_null
        hi = len(pattern_db) - 1 if right_null is None else right_null
        mask = np.ones(len(pattern_db), dtype=bool)
        mask[lo : hi + 1] = False

    if not np.any(mask):
        return float("-inf")

    peak_sidelobe_db = float(np.max(pattern_db[mask]))

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


def compute_directivity_rectangular(nx: int, ny: int, dx_lambda: float, dy_lambda: float) -> float:
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
