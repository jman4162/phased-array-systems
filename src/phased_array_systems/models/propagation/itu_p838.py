"""Rain specific attenuation per ITU-R P.838-3.

gamma_R = k * R^alpha (dB/km), with k and alpha from the log-Gaussian
regression sums of Tables 1-4 for linear H and V polarization. Valid
1-1000 GHz.

Reference: Recommendation ITU-R P.838-3 (03/2005).
"""

from __future__ import annotations

import math
from typing import Literal

from phased_array_systems.models.propagation.itu_p838_data import (
    AH_C,
    AH_M,
    AH_TERMS,
    AV_C,
    AV_M,
    AV_TERMS,
    KH_C,
    KH_M,
    KH_TERMS,
    KV_C,
    KV_M,
    KV_TERMS,
)

Polarization = Literal["H", "V"]


def _regression(
    log_f: float,
    terms: tuple[tuple[float, float, float], ...],
    m: float,
    c: float,
) -> float:
    total = m * log_f + c
    for a_j, b_j, c_j in terms:
        total += a_j * math.exp(-(((log_f - b_j) / c_j) ** 2))
    return total


def rain_k_alpha(freq_ghz: float, polarization: Polarization = "H") -> tuple[float, float]:
    """Regression coefficients k and alpha at a given frequency.

    Args:
        freq_ghz: Frequency in GHz (valid 1-1000)
        polarization: Linear polarization, "H" or "V"

    Returns:
        Tuple (k, alpha)

    Raises:
        ValueError: If frequency is outside 1-1000 GHz
    """
    if not 1.0 <= freq_ghz <= 1000.0:
        raise ValueError(f"P.838-3 is valid for 1-1000 GHz, got {freq_ghz} GHz")

    log_f = math.log10(freq_ghz)
    if polarization == "H":
        k = 10.0 ** _regression(log_f, KH_TERMS, KH_M, KH_C)
        alpha = _regression(log_f, AH_TERMS, AH_M, AH_C)
    else:
        k = 10.0 ** _regression(log_f, KV_TERMS, KV_M, KV_C)
        alpha = _regression(log_f, AV_TERMS, AV_M, AV_C)
    return k, alpha


def rain_specific_attenuation_db_per_km(
    freq_ghz: float,
    rain_rate_mm_hr: float,
    polarization: Polarization = "H",
) -> float:
    """Rain specific attenuation gamma_R = k * R^alpha (dB/km).

    Args:
        freq_ghz: Frequency in GHz; returns 0.0 below 1 GHz (rain
            attenuation is negligible there)
        rain_rate_mm_hr: Rain rate in mm/h
        polarization: Linear polarization, "H" or "V"

    Returns:
        Specific attenuation in dB/km
    """
    if rain_rate_mm_hr <= 0 or freq_ghz < 1.0:
        return 0.0
    k, alpha = rain_k_alpha(freq_ghz, polarization)
    return float(k * rain_rate_mm_hr**alpha)
