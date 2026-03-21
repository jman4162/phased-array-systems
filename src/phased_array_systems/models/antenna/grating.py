"""Grating lobe detection for phased array antennas."""

import numpy as np


def check_grating_lobes(
    dx_lambda: float,
    dy_lambda: float,
    scan_limit_deg: float,
) -> dict:
    """Check for grating lobe risk based on element spacing and scan angle.

    Grating lobes appear when d/lambda >= 1 / (1 + sin(theta_max)).
    For half-wavelength spacing (d=0.5 lambda), grating lobes only
    appear at 90 deg scan. For wider spacing, they appear at lower angles.

    Args:
        dx_lambda: Element spacing in x (wavelengths)
        dy_lambda: Element spacing in y (wavelengths)
        scan_limit_deg: Maximum scan angle from boresight (degrees)

    Returns:
        Dictionary with:
            - grating_lobe_risk: True if grating lobes possible
            - max_safe_spacing_lambda: Maximum safe spacing for this scan limit
    """
    sin_theta_max = np.sin(np.radians(scan_limit_deg))
    max_safe = 1.0 / (1.0 + sin_theta_max)

    grating_risk = dx_lambda > max_safe or dy_lambda > max_safe

    return {
        "grating_lobe_risk": bool(grating_risk),
        "max_safe_spacing_lambda": float(max_safe),
    }
