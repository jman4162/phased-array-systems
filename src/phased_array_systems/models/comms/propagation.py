"""Propagation loss models for communications links."""

import math
from typing import Literal

from phased_array_systems.constants import C
from phased_array_systems.models.propagation import (
    H2O_EQUIVALENT_HEIGHT_KM,
    O2_EQUIVALENT_HEIGHT_KM,
    effective_rain_path_km,
    gaseous_attenuation_components_db_per_km,
    gaseous_slant_path_km,
    rain_k_alpha,
    water_vapor_density_g_m3,
)


def compute_fspl(freq_hz: float, range_m: float) -> float:
    """Compute Free Space Path Loss (FSPL).

    FSPL = 20*log10(4*pi*d*f/c)
         = 20*log10(d) + 20*log10(f) + 20*log10(4*pi/c)
         = 20*log10(d) + 20*log10(f) - 147.55 (with d in m, f in Hz)

    Args:
        freq_hz: Frequency in Hz
        range_m: Range/distance in meters

    Returns:
        Free space path loss in dB (positive value)
    """
    if freq_hz <= 0:
        raise ValueError("Frequency must be positive")
    if range_m <= 0:
        raise ValueError("Range must be positive")

    wavelength = C / freq_hz
    fspl_linear = (4 * math.pi * range_m / wavelength) ** 2
    return 10 * math.log10(fspl_linear)


def compute_fspl_wavelength(wavelength_m: float, range_m: float) -> float:
    """Compute FSPL given wavelength directly.

    Args:
        wavelength_m: Wavelength in meters
        range_m: Range/distance in meters

    Returns:
        Free space path loss in dB (positive value)
    """
    if wavelength_m <= 0:
        raise ValueError("Wavelength must be positive")
    if range_m <= 0:
        raise ValueError("Range must be positive")

    fspl_linear = (4 * math.pi * range_m / wavelength_m) ** 2
    return 10 * math.log10(fspl_linear)


def compute_log_distance_path_loss(
    freq_hz: float,
    range_m: float,
    n: float = 2.0,
    d0: float = 1.0,
) -> float:
    """Compute log-distance path loss model.

    PL(d) = FSPL(d0) + 10*n*log10(d/d0)

    This generalizes FSPL (n=2) to various environments:
    n=2.0 free space, n=2.7-3.5 urban, n=4.0-6.0 indoor/obstructed.

    Args:
        freq_hz: Frequency in Hz
        range_m: Range/distance in meters
        n: Path loss exponent (2.0=free space, 3.0=urban, 4.0=indoor)
        d0: Reference distance in meters (default 1.0 m)

    Returns:
        Path loss in dB (positive value)
    """
    if freq_hz <= 0:
        raise ValueError("Frequency must be positive")
    if range_m <= 0:
        raise ValueError("Range must be positive")
    if d0 <= 0:
        raise ValueError("Reference distance must be positive")

    pl_d0 = compute_fspl(freq_hz, d0)

    if range_m <= d0:
        return compute_fspl(freq_hz, range_m)

    return pl_d0 + 10.0 * n * math.log10(range_m / d0)


def compute_atmospheric_loss(
    freq_hz: float,
    range_m: float,
    elevation_deg: float = 90.0,
    temperature_c: float = 15.0,
    humidity_pct: float = 50.0,
    pressure_hpa: float = 1013.25,
) -> float:
    """Compute one-way atmospheric absorption loss.

    Specific attenuation from the ITU-R P.676-13 Annex 1 line-by-line
    model. Each gas attenuates over min(range, equivalent-height slant
    column), so terrestrial paths attenuate over their full length and
    space paths only through the absorbing layer.

    Args:
        freq_hz: Frequency (Hz)
        range_m: Path length (m)
        elevation_deg: Elevation angle (deg), 90 = zenith; <= 0 treated as
            a horizontal path
        temperature_c: Surface temperature (Celsius)
        humidity_pct: Relative humidity (%)
        pressure_hpa: Total surface pressure (hPa)

    Returns:
        One-way atmospheric loss (dB, positive value)
    """
    freq_ghz = freq_hz / 1e9

    if freq_ghz < 1:
        return 0.0  # Negligible below 1 GHz

    range_km = range_m / 1000.0

    rho = water_vapor_density_g_m3(temperature_c, humidity_pct, pressure_hpa)
    gamma_o, gamma_w = gaseous_attenuation_components_db_per_km(
        freq_ghz, temperature_c, pressure_hpa, rho
    )

    loss_o = gamma_o * gaseous_slant_path_km(range_km, elevation_deg, O2_EQUIVALENT_HEIGHT_KM)
    loss_w = gamma_w * gaseous_slant_path_km(range_km, elevation_deg, H2O_EQUIVALENT_HEIGHT_KM)

    return loss_o + loss_w


def compute_rain_loss(
    freq_hz: float,
    range_m: float,
    rain_rate_mmh: float,
    polarization: Literal["H", "V"] = "H",
) -> float:
    """Compute one-way rain attenuation per ITU-R P.838-3.

    gamma_R = k * R^alpha with the published Table 1-4 coefficients,
    applied over the ITU-R P.530 effective rain path length.

    Terrestrial paths only: P.530's effective path assumes the whole link
    sits in rain. For earth-space (slant) paths use an ITU-R P.618
    implementation and pass the result in via the scenario's
    ``rain_loss_db`` override; applying this model to a slant range
    overpredicts rain loss by an order of magnitude at Ka-band.

    Args:
        freq_hz: Frequency (Hz)
        range_m: Path length (m)
        rain_rate_mmh: Rain rate (mm/hour)
        polarization: Linear polarization, "H" or "V"

    Returns:
        One-way rain loss (dB, positive value)
    """
    if rain_rate_mmh <= 0:
        return 0.0

    freq_ghz = freq_hz / 1e9
    if freq_ghz < 1:
        return 0.0

    range_km = range_m / 1000.0

    k, alpha = rain_k_alpha(freq_ghz, polarization)
    gamma_r = k * (rain_rate_mmh**alpha)
    effective_km = effective_rain_path_km(range_km, rain_rate_mmh, freq_ghz, alpha)

    return float(gamma_r * effective_km)


def compute_two_ray_path_loss(
    freq_hz: float,
    range_m: float,
    h_tx_m: float,
    h_rx_m: float,
) -> float:
    """Compute two-ray ground reflection path loss.

    At short ranges, behaves like FSPL. At long ranges (beyond crossover
    distance), follows d^4 attenuation.

    Args:
        freq_hz: Frequency in Hz
        range_m: Horizontal range in meters
        h_tx_m: Transmitter height in meters
        h_rx_m: Receiver height in meters

    Returns:
        Path loss in dB (positive value)
    """
    wavelength = C / freq_hz

    # Crossover distance
    d_cross = 4 * h_tx_m * h_rx_m / wavelength

    if range_m < d_cross:
        # Use FSPL in near region
        return compute_fspl(freq_hz, range_m)
    else:
        # Two-ray model: PL = 40*log10(d) - 20*log10(ht*hr)
        # Normalized to match FSPL at crossover
        pl_cross = compute_fspl(freq_hz, d_cross)
        pl_two_ray = pl_cross + 40 * math.log10(range_m / d_cross)
        return pl_two_ray
