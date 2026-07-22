"""Path-geometry helpers shared by the comms and radar propagation models."""

from __future__ import annotations

import math

# Away-from-line equivalent heights of the absorbing layers, ITU-R P.676-13
# Annex 2 section 2.2 (h_o grows near 60/118 GHz and h_w near the water
# lines; these constants are the flat, away-from-line values)
O2_EQUIVALENT_HEIGHT_KM = 6.1
H2O_EQUIVALENT_HEIGHT_KM = 2.4


def gaseous_slant_path_km(
    range_km: float,
    elevation_deg: float,
    equivalent_height_km: float,
    floor_deg: float = 0.5,
) -> float:
    """Path length through an absorbing gas layer of given equivalent height.

    The gas attenuates over min(physical range, h_eq / sin(el)): a
    terrestrial path (low elevation, range shorter than the slant limit)
    attenuates over its full length, while a space path attenuates only
    over the equivalent-height slant column. First-order stand-in for the
    layered integration of ITU-R P.676 Annex 1 section 2.

    Args:
        range_km: Physical path length (km)
        elevation_deg: Path elevation angle above horizontal (degrees);
            values <= 0 are treated as horizontal (full range attenuates)
        equivalent_height_km: Equivalent height of the absorbing layer (km)
        floor_deg: Minimum elevation used in the cosecant (degrees)

    Returns:
        Attenuating path length in km (<= range_km)
    """
    if range_km <= 0:
        return 0.0
    if elevation_deg <= 0:
        return range_km
    el = max(floor_deg, min(90.0, elevation_deg))
    slant_km = equivalent_height_km / math.sin(math.radians(el))
    return min(range_km, slant_km)


def effective_rain_path_km(
    path_km: float,
    rain_rate_mm_hr: float,
    freq_ghz: float,
    alpha: float,
) -> float:
    """Effective rain path length via the ITU-R P.530-17 distance factor.

    r = 1 / (0.477 d^0.633 R^(0.073 alpha) f^0.123
             - 10.579 (1 - exp(-0.024 d))), capped at 2.5;
    effective path = r * d. Replaces ad-hoc rain-cell extent models.

    Note: P.530 defines R as the rate exceeded 0.01% of the time; here the
    scenario rain rate is used directly, i.e. the study's rain rate is
    treated as the design point.

    Args:
        path_km: Physical path length d (km)
        rain_rate_mm_hr: Rain rate R (mm/h)
        freq_ghz: Frequency f (GHz)
        alpha: P.838 exponent alpha at this frequency/polarization

    Returns:
        Effective path length in km (0 for non-positive inputs)
    """
    if path_km <= 0 or rain_rate_mm_hr <= 0:
        return 0.0

    denom = 0.477 * path_km**0.633 * rain_rate_mm_hr ** (
        0.073 * alpha
    ) * freq_ghz**0.123 - 10.579 * (1.0 - math.exp(-0.024 * path_km))
    r = 2.5 if denom <= 0 or 1.0 / denom > 2.5 else 1.0 / denom
    return r * path_km
