"""Atmospheric propagation models for radar.

Implements:
- Atmospheric attenuation (oxygen and water vapor absorption)
- Rain attenuation
- Earth curvature and refraction effects

Gaseous and rain attenuation delegate to the shared line-by-line ITU
implementations in `phased_array_systems.models.propagation`.

References:
    - ITU-R P.676-13: Attenuation by atmospheric gases
    - ITU-R P.838-3: Rain attenuation model
    - Skolnik, M. "Radar Handbook", 3rd Ed., Ch. 26
"""

from __future__ import annotations

import math
from typing import Literal

from phased_array_systems.models.propagation import (
    H2O_EQUIVALENT_HEIGHT_KM,
    O2_EQUIVALENT_HEIGHT_KM,
    effective_rain_path_km,
    gaseous_attenuation_components_db_per_km,
    gaseous_attenuation_from_humidity,
    gaseous_slant_path_km,
    rain_k_alpha,
    water_vapor_density_g_m3,
)

# Earth radius (km)
EARTH_RADIUS_KM = 6371.0


def atmospheric_attenuation_db_per_km(
    freq_hz: float,
    temperature_c: float = 15.0,
    pressure_hpa: float = 1013.25,
    humidity_pct: float = 50.0,
) -> float:
    """Compute one-way atmospheric attenuation rate.

    Line-by-line ITU-R P.676-13 model for combined oxygen and water vapor
    absorption, valid 1-1000 GHz.

    Args:
        freq_hz: Frequency (Hz)
        temperature_c: Temperature (Celsius), default 15°C
        pressure_hpa: Atmospheric pressure (hPa), default 1013.25
        humidity_pct: Relative humidity (%), default 50%

    Returns:
        Attenuation rate (dB/km), one-way
    """
    return gaseous_attenuation_from_humidity(
        freq_hz / 1e9, temperature_c, pressure_hpa, humidity_pct
    )


def atmospheric_loss_db(
    freq_hz: float,
    range_m: float,
    elevation_deg: float = 0.0,
    temperature_c: float = 15.0,
    humidity_pct: float = 50.0,
    pressure_hpa: float = 1013.25,
) -> float:
    """Compute total two-way atmospheric loss.

    For radar, this is the round-trip loss through the atmosphere. Each gas
    attenuates over min(range, equivalent-height slant column), so
    low-elevation surveillance paths attenuate over the full range while
    high-elevation paths only cross the absorbing layer.

    Args:
        freq_hz: Frequency (Hz)
        range_m: Slant range (m)
        elevation_deg: Elevation angle (deg), 0 = horizon
        temperature_c: Temperature (Celsius)
        humidity_pct: Relative humidity (%)
        pressure_hpa: Total surface pressure (hPa)

    Returns:
        Two-way atmospheric loss (dB)
    """
    freq_ghz = freq_hz / 1e9
    if freq_ghz < 1:
        return 0.0

    range_km = range_m / 1000.0

    rho = water_vapor_density_g_m3(temperature_c, humidity_pct, pressure_hpa)
    gamma_o, gamma_w = gaseous_attenuation_components_db_per_km(
        freq_ghz, temperature_c, pressure_hpa, rho
    )

    one_way_loss = gamma_o * gaseous_slant_path_km(
        range_km, elevation_deg, O2_EQUIVALENT_HEIGHT_KM
    ) + gamma_w * gaseous_slant_path_km(range_km, elevation_deg, H2O_EQUIVALENT_HEIGHT_KM)

    return 2.0 * one_way_loss


def rain_attenuation_rate(
    freq_hz: float,
    rain_rate_mm_hr: float,
    polarization: Literal["H", "V"] = "H",
) -> float:
    """Compute rain attenuation rate per ITU-R P.838-3.

    gamma_R = k * R^alpha with the published Table 1-4 coefficients.

    Args:
        freq_hz: Frequency (Hz)
        rain_rate_mm_hr: Rain rate (mm/hour)
        polarization: Linear polarization, "H" or "V"

    Returns:
        Attenuation rate (dB/km), one-way
    """
    if rain_rate_mm_hr <= 0:
        return 0.0

    freq_ghz = freq_hz / 1e9

    if freq_ghz < 1:
        return 0.0  # Negligible rain attenuation below 1 GHz

    k, alpha = rain_k_alpha(freq_ghz, polarization)
    return float(k * (rain_rate_mm_hr**alpha))


def rain_attenuation_db(
    freq_hz: float,
    range_m: float,
    rain_rate_mm_hr: float,
    rain_extent_km: float | None = None,
    polarization: Literal["H", "V"] = "H",
) -> float:
    """Compute total two-way rain attenuation.

    Args:
        freq_hz: Frequency (Hz)
        range_m: Slant range through rain (m)
        rain_rate_mm_hr: Rain rate (mm/hour)
        rain_extent_km: Extent of rain cell (km). If None, uses the
            ITU-R P.530 effective-path distance factor.
        polarization: Linear polarization, "H" or "V"

    Returns:
        Two-way rain attenuation (dB)
    """
    if rain_rate_mm_hr <= 0:
        return 0.0

    freq_ghz = freq_hz / 1e9
    if freq_ghz < 1:
        return 0.0

    range_km = range_m / 1000.0

    k, alpha = rain_k_alpha(freq_ghz, polarization)
    gamma_r = k * (rain_rate_mm_hr**alpha)

    if rain_extent_km is not None:
        effective_path_km = min(range_km, rain_extent_km)
    else:
        effective_path_km = effective_rain_path_km(range_km, rain_rate_mm_hr, freq_ghz, alpha)

    return float(2.0 * gamma_r * effective_path_km)


def effective_earth_radius_factor(
    refractivity_gradient: float = -40.0,
) -> float:
    """Compute effective Earth radius factor.

    Standard atmosphere has refractivity gradient of -40 N-units/km,
    giving the classic "4/3 Earth" model for radar propagation.

    Args:
        refractivity_gradient: dN/dh in N-units/km (typically -40)

    Returns:
        Effective Earth radius factor (k), typically ~1.33
    """
    # k = 1 / (1 + a * dN/dh * 1e-6)
    # where a = 6371 km (Earth radius)
    k = 1.0 / (1.0 + EARTH_RADIUS_KM * refractivity_gradient * 1e-6)
    return k


def radar_horizon_km(
    antenna_height_m: float,
    target_height_m: float = 0.0,
    k_factor: float = 4.0 / 3.0,
) -> float:
    """Compute radar horizon range.

    The radar horizon is the maximum range at which a target
    can be detected due to Earth curvature, accounting for
    atmospheric refraction.

    Args:
        antenna_height_m: Antenna height above surface (m)
        target_height_m: Target height above surface (m)
        k_factor: Effective Earth radius factor (default 4/3)

    Returns:
        Radar horizon range (km)
    """
    # Horizon distance for antenna
    h_ant_km = antenna_height_m / 1000.0
    d_ant = math.sqrt(2.0 * k_factor * EARTH_RADIUS_KM * h_ant_km)

    # Horizon distance for target
    h_tgt_km = target_height_m / 1000.0
    d_tgt = math.sqrt(2.0 * k_factor * EARTH_RADIUS_KM * h_tgt_km)

    # Total radar horizon
    total_horizon = d_ant + d_tgt

    return total_horizon


def grazing_angle_deg(
    range_m: float,
    antenna_height_m: float,
    target_height_m: float = 0.0,
    k_factor: float = 4.0 / 3.0,
) -> float:
    """Compute grazing angle for surface targets.

    The grazing angle is the angle between the radar beam and
    the local horizontal at the target (or surface).

    Args:
        range_m: Slant range to target (m)
        antenna_height_m: Antenna height (m)
        target_height_m: Target height (m)
        k_factor: Effective Earth radius factor

    Returns:
        Grazing angle (degrees)
    """
    range_km = range_m / 1000.0
    h_ant = antenna_height_m / 1000.0
    h_tgt = target_height_m / 1000.0

    # Effective Earth radius
    r_e = k_factor * EARTH_RADIUS_KM

    # Height difference
    delta_h = h_ant - h_tgt

    # For flat Earth approximation (valid for ranges << Earth radius)
    if range_km < 50:
        psi = math.atan(delta_h / range_km)
        return math.degrees(psi)

    # For longer ranges, account for Earth curvature
    # Depression angle from antenna to target
    # Using spherical geometry approximation
    d = range_km

    # Earth curvature correction
    curvature = d**2 / (2 * r_e)
    effective_delta_h = delta_h + curvature

    psi = math.atan(effective_delta_h / d)

    return math.degrees(psi)


def multipath_fading_factor(
    grazing_angle_deg: float,
    surface_roughness: float = 0.0,
) -> float:
    """Estimate multipath fading factor for low-angle targets.

    At low grazing angles, interference between direct and
    surface-reflected signals causes pattern lobing (multipath).

    Args:
        grazing_angle_deg: Grazing angle (degrees)
        surface_roughness: RMS surface roughness relative to wavelength
            (0 = smooth, >0.1 = rough)

    Returns:
        Multipath fading factor in dB (negative = loss)
    """
    if grazing_angle_deg > 10:
        # Multipath effects negligible above ~10 degrees
        return 0.0

    # For smooth surfaces, reflection coefficient approaches -1
    # This causes deep nulls in the pattern

    # Rough surface reduces reflection coherence
    roughness_factor = math.exp(-2.0 * (2 * math.pi * surface_roughness) ** 2)

    # At very low angles, worst-case fading can be 6 dB or more
    # (due to pattern nulls between lobes)
    psi = math.radians(max(0.1, grazing_angle_deg))

    # Simplified model: fading increases as grazing angle decreases
    fading_db = -3.0 * roughness_factor / psi if psi < 0.1 else 0.0

    # Limit to reasonable range
    return max(-12.0, fading_db)
