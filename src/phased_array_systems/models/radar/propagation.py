"""Atmospheric propagation models for radar.

Implements:
- Atmospheric attenuation (oxygen and water vapor absorption)
- Rain attenuation
- Earth curvature and refraction effects

References:
    - ITU-R P.676-12: Attenuation by atmospheric gases
    - ITU-R P.838-3: Rain attenuation model
    - Skolnik, M. "Radar Handbook", 3rd Ed., Ch. 26
"""

from __future__ import annotations

import math

# Earth radius (km)
EARTH_RADIUS_KM = 6371.0


def atmospheric_attenuation_db_per_km(
    freq_hz: float,
    temperature_c: float = 15.0,
    pressure_hpa: float = 1013.25,
    humidity_pct: float = 50.0,
) -> float:
    """Compute one-way atmospheric attenuation rate.

    Uses simplified ITU-R P.676 model for combined oxygen and
    water vapor absorption. Accurate for frequencies 1-100 GHz.

    Args:
        freq_hz: Frequency (Hz)
        temperature_c: Temperature (Celsius), default 15°C
        pressure_hpa: Atmospheric pressure (hPa), default 1013.25
        humidity_pct: Relative humidity (%), default 50%

    Returns:
        Attenuation rate (dB/km), one-way
    """
    freq_ghz = freq_hz / 1e9

    if freq_ghz < 1:
        return 0.0  # Negligible below 1 GHz

    # Simplified model coefficients
    # Oxygen has resonances at ~60 GHz and ~118 GHz
    # Water vapor has resonances at ~22 GHz and ~183 GHz

    # Temperature and pressure correction factors
    theta = 300.0 / (temperature_c + 273.15)
    p_ratio = pressure_hpa / 1013.25

    # Oxygen absorption (simplified Liebe model)
    # Peak around 60 GHz
    f_o2 = 60.0
    delta_o2 = 5.0  # Approximate linewidth
    gamma_o2 = 0.001 * p_ratio * theta**3 * freq_ghz**2 / (1 + ((freq_ghz - f_o2) / delta_o2) ** 2)

    # Add low-frequency oxygen contribution
    if freq_ghz < 60:
        gamma_o2 += 7e-4 * p_ratio * theta**2 * freq_ghz**2 / 1000

    # Water vapor absorption (simplified)
    # Convert humidity to water vapor density
    # Saturation vapor pressure (simplified)
    e_s = 6.1121 * math.exp(17.502 * temperature_c / (240.97 + temperature_c))
    rho_w = humidity_pct / 100.0 * e_s * 0.622 / (pressure_hpa - e_s) * 100

    # Peak around 22 GHz
    f_h2o = 22.235
    delta_h2o = 3.0
    gamma_h2o = (
        0.0001 * rho_w * theta**3.5 * freq_ghz**2 / (1 + ((freq_ghz - f_h2o) / delta_h2o) ** 2)
    )

    # Second water vapor line at 183 GHz
    if freq_ghz > 100:
        f_h2o_2 = 183.31
        delta_h2o_2 = 5.0
        gamma_h2o += (
            0.001 * rho_w * theta**3 * freq_ghz**2 / (1 + ((freq_ghz - f_h2o_2) / delta_h2o_2) ** 2)
        )

    total_attenuation = gamma_o2 + gamma_h2o

    return float(total_attenuation)


def atmospheric_loss_db(
    freq_hz: float,
    range_m: float,
    elevation_deg: float = 0.0,
    temperature_c: float = 15.0,
    humidity_pct: float = 50.0,
) -> float:
    """Compute total two-way atmospheric loss.

    For radar, this is the round-trip loss through the atmosphere.
    Accounts for path elevation (less atmosphere at higher angles).

    Args:
        freq_hz: Frequency (Hz)
        range_m: Slant range (m)
        elevation_deg: Elevation angle (deg), 0 = horizon
        temperature_c: Temperature (Celsius)
        humidity_pct: Relative humidity (%)

    Returns:
        Two-way atmospheric loss (dB)
    """
    range_km = range_m / 1000.0

    # Get attenuation rate
    atten_rate = atmospheric_attenuation_db_per_km(
        freq_hz, temperature_c, humidity_pct=humidity_pct
    )

    # Scale by elevation - less atmosphere at higher angles
    # Effective path through atmosphere decreases with elevation
    if elevation_deg > 0:
        # Simple model: assume uniform atmosphere to 10 km altitude
        # Path length scales approximately as 1/sin(elevation) near horizon
        # but is limited by atmosphere height at high angles
        elev_rad = math.radians(max(0.5, elevation_deg))
        scale_factor = min(1.0, 1.0 / math.sin(elev_rad))
    else:
        scale_factor = 1.0

    # Two-way loss (radar sees both directions)
    one_way_loss = atten_rate * range_km * scale_factor
    two_way_loss = 2.0 * one_way_loss

    return two_way_loss


def rain_attenuation_rate(
    freq_hz: float,
    rain_rate_mm_hr: float,
) -> float:
    """Compute rain attenuation rate using ITU-R P.838.

    Args:
        freq_hz: Frequency (Hz)
        rain_rate_mm_hr: Rain rate (mm/hour)

    Returns:
        Attenuation rate (dB/km), one-way
    """
    if rain_rate_mm_hr <= 0:
        return 0.0

    freq_ghz = freq_hz / 1e9

    if freq_ghz < 1:
        return 0.0  # Negligible rain attenuation below 1 GHz

    # ITU-R P.838-3 coefficients (simplified, horizontal polarization)
    # gamma_R = k * R^alpha
    # Coefficients are frequency-dependent

    # Approximate k and alpha from ITU-R tables
    # Valid for 1-100 GHz
    log_f = math.log10(max(1.0, freq_ghz))

    # Polynomial fit for k (log scale)
    log_k = -5.33 + 0.7 * log_f + 0.15 * log_f**2
    k = 10**log_k

    # Polynomial fit for alpha
    alpha = 1.2 - 0.1 * log_f

    # Clamp alpha to reasonable range
    alpha = max(0.8, min(1.3, alpha))

    # Rain attenuation rate
    gamma_r = k * (rain_rate_mm_hr**alpha)

    return float(gamma_r)


def rain_attenuation_db(
    freq_hz: float,
    range_m: float,
    rain_rate_mm_hr: float,
    rain_extent_km: float | None = None,
) -> float:
    """Compute total two-way rain attenuation.

    Args:
        freq_hz: Frequency (Hz)
        range_m: Slant range through rain (m)
        rain_rate_mm_hr: Rain rate (mm/hour)
        rain_extent_km: Extent of rain cell (km). If None, uses
            an empirical model based on rain rate.

    Returns:
        Two-way rain attenuation (dB)
    """
    if rain_rate_mm_hr <= 0:
        return 0.0

    range_km = range_m / 1000.0

    # Attenuation rate
    gamma_r = rain_attenuation_rate(freq_hz, rain_rate_mm_hr)

    # Rain cell extent model (if not specified)
    # Higher rain rates typically come from smaller cells
    if rain_extent_km is None:
        # Empirical model: extent decreases with rain rate
        # Based on ITU-R P.530 reduction factor concept
        rain_extent_km = max(1.0, 35.0 * math.exp(-0.02 * rain_rate_mm_hr))

    # Path through rain is minimum of range and rain extent
    effective_path_km = min(range_km, rain_extent_km)

    # Two-way loss
    one_way_loss = gamma_r * effective_path_km
    two_way_loss = 2.0 * one_way_loss

    return two_way_loss


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
