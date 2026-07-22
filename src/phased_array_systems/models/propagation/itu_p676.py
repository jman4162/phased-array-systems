"""Gaseous specific attenuation per ITU-R P.676-13, Annex 1 (line-by-line).

Implements the full line-by-line summation over the 44 oxygen and 35 water
vapour spectroscopic lines of Tables 1 and 2, plus the dry-air continuum
(Debye spectrum and pressure-induced nitrogen absorption). Valid 1-1000 GHz.

Scope: specific attenuation gamma (dB/km) at a single set of surface
conditions. Slant paths use the cosecant scaling in
`phased_array_systems.models.propagation.path`; the layered-atmosphere
integration of Annex 1 section 2 is not implemented.

Reference: Recommendation ITU-R P.676-13 (08/2022), Annex 1, equations 1-9.
"""

from __future__ import annotations

import math

from phased_array_systems.models.propagation.itu_p676_data import (
    OXYGEN_LINES,
    WATER_VAPOUR_LINES,
)


def saturation_vapor_pressure_hpa(temperature_c: float) -> float:
    """Saturation water vapour pressure over water (hPa).

    Buck-type formula per ITU-R P.453 (coefficients a=6.1121, b=17.502,
    c=240.97), valid -40 to +50 C.

    Args:
        temperature_c: Air temperature (Celsius)

    Returns:
        Saturation vapour pressure in hPa
    """
    return 6.1121 * math.exp(17.502 * temperature_c / (temperature_c + 240.97))


def water_vapor_density_g_m3(
    temperature_c: float,
    humidity_pct: float,
    pressure_hpa: float = 1013.25,
) -> float:
    """Water vapour density from relative humidity.

    rho = 216.7 * e / T (g/m^3), with e the partial pressure of water
    vapour in hPa and T in kelvin (ITU-R P.453).

    Args:
        temperature_c: Air temperature (Celsius)
        humidity_pct: Relative humidity (0-100)
        pressure_hpa: Total air pressure (hPa); unused in the conversion but
            accepted so callers can pass full surface conditions

    Returns:
        Water vapour density in g/m^3
    """
    e_hpa = (humidity_pct / 100.0) * saturation_vapor_pressure_hpa(temperature_c)
    t_k = temperature_c + 273.15
    return 216.7 * e_hpa / t_k


def gaseous_attenuation_components_db_per_km(
    freq_ghz: float,
    temperature_c: float = 15.0,
    pressure_hpa: float = 1013.25,
    water_vapor_g_m3: float = 7.5,
) -> tuple[float, float]:
    """Oxygen and water-vapour specific attenuation (dB/km), separately.

    Full line-by-line model of ITU-R P.676-13 Annex 1: gamma = 0.1820 * f *
    N'', where N'' is the imaginary part of the complex refractivity from
    the line summation (plus the dry continuum for oxygen). The split is
    needed for slant paths, where the two gases have different equivalent
    heights.

    Args:
        freq_ghz: Frequency in GHz (valid 1-1000)
        temperature_c: Surface air temperature (Celsius)
        pressure_hpa: Total air pressure (hPa)
        water_vapor_g_m3: Water vapour density (g/m^3); 7.5 is the ITU
            reference surface value

    Returns:
        Tuple (gamma_oxygen, gamma_water) in dB/km ((0, 0) below 1 GHz)
    """
    f = freq_ghz
    if f < 1.0:
        return 0.0, 0.0

    t_k = temperature_c + 273.15
    theta = 300.0 / t_k
    # Water vapour partial pressure (hPa) from density: e = rho * T / 216.7
    e = water_vapor_g_m3 * t_k / 216.7
    # Dry air pressure
    p = pressure_hpa - e

    # Oxygen line summation (eq. 3-7 with Table 1 coefficients)
    n_ox = 0.0
    for f0, a1, a2, a3, a4, a5, a6 in OXYGEN_LINES:
        strength = a1 * 1e-7 * p * theta**3 * math.exp(a2 * (1.0 - theta))
        width = a3 * 1e-4 * (p * theta ** (0.8 - a4) + 1.1 * e * theta)
        width = math.sqrt(width * width + 2.25e-6)  # Zeeman splitting
        delta = (a5 + a6 * theta) * 1e-4 * (p + e) * theta**0.8
        shape = (f / f0) * (
            (width - delta * (f0 - f)) / ((f0 - f) ** 2 + width * width)
            + (width - delta * (f0 + f)) / ((f0 + f) ** 2 + width * width)
        )
        n_ox += strength * shape

    # Dry continuum: Debye spectrum + pressure-induced N2 absorption (eq. 8-9)
    d = 5.6e-4 * (p + e) * theta**0.8
    n_d = (
        f
        * p
        * theta**2
        * (
            6.14e-5 / (d * (1.0 + (f / d) ** 2))
            + 1.4e-12 * p * theta**1.5 / (1.0 + 1.9e-5 * f**1.5)
        )
    )
    n_ox += n_d

    # Water vapour line summation (eq. 3-7 with Table 2 coefficients)
    n_wv = 0.0
    for f0, b1, b2, b3, b4, b5, b6 in WATER_VAPOUR_LINES:
        strength = b1 * 1e-1 * e * theta**3.5 * math.exp(b2 * (1.0 - theta))
        width = b3 * 1e-4 * (p * theta**b4 + b5 * e * theta**b6)
        # Doppler broadening correction
        width = 0.535 * width + math.sqrt(0.217 * width * width + 2.1316e-12 * f0 * f0 / theta)
        shape = (f / f0) * (
            width / ((f0 - f) ** 2 + width * width) + width / ((f0 + f) ** 2 + width * width)
        )
        n_wv += strength * shape

    return 0.1820 * f * n_ox, 0.1820 * f * n_wv


def gaseous_attenuation_db_per_km(
    freq_ghz: float,
    temperature_c: float = 15.0,
    pressure_hpa: float = 1013.25,
    water_vapor_g_m3: float = 7.5,
) -> float:
    """Total specific gaseous attenuation gamma = gamma_o + gamma_w (dB/km).

    See `gaseous_attenuation_components_db_per_km`.

    Args:
        freq_ghz: Frequency in GHz (valid 1-1000)
        temperature_c: Surface air temperature (Celsius)
        pressure_hpa: Total air pressure (hPa)
        water_vapor_g_m3: Water vapour density (g/m^3)

    Returns:
        Specific attenuation in dB/km (0.0 below 1 GHz)
    """
    gamma_o, gamma_w = gaseous_attenuation_components_db_per_km(
        freq_ghz, temperature_c, pressure_hpa, water_vapor_g_m3
    )
    return gamma_o + gamma_w


def gaseous_attenuation_from_humidity(
    freq_ghz: float,
    temperature_c: float = 15.0,
    pressure_hpa: float = 1013.25,
    humidity_pct: float = 50.0,
) -> float:
    """Specific gaseous attenuation with humidity given as RH%.

    Convenience wrapper converting relative humidity to water vapour
    density before calling `gaseous_attenuation_db_per_km`.

    Args:
        freq_ghz: Frequency in GHz
        temperature_c: Surface air temperature (Celsius)
        pressure_hpa: Total air pressure (hPa)
        humidity_pct: Relative humidity (0-100)

    Returns:
        Specific attenuation in dB/km
    """
    rho = water_vapor_density_g_m3(temperature_c, humidity_pct, pressure_hpa)
    return gaseous_attenuation_db_per_km(freq_ghz, temperature_c, pressure_hpa, rho)
