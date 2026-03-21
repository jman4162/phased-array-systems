"""Propagation loss models for communications links."""

import math

from phased_array_systems.constants import C


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
) -> float:
    """Compute one-way atmospheric absorption loss.

    Uses simplified ITU-R P.676 model for combined oxygen and
    water vapor absorption. Accurate for frequencies 1-100 GHz.

    Args:
        freq_hz: Frequency (Hz)
        range_m: Path length (m)
        elevation_deg: Elevation angle (deg), 90 = zenith
        temperature_c: Temperature (Celsius)
        humidity_pct: Relative humidity (%)

    Returns:
        One-way atmospheric loss (dB, positive value)
    """
    freq_ghz = freq_hz / 1e9

    if freq_ghz < 1:
        return 0.0  # Negligible below 1 GHz

    range_km = range_m / 1000.0

    # Temperature and pressure correction
    theta = 300.0 / (temperature_c + 273.15)
    p_ratio = 1.0  # Assume standard pressure

    # Oxygen absorption (peak near 60 GHz)
    f_o2 = 60.0
    delta_o2 = 5.0
    gamma_o2 = 0.001 * p_ratio * theta**3 * freq_ghz**2 / (1 + ((freq_ghz - f_o2) / delta_o2) ** 2)
    if freq_ghz < 60:
        gamma_o2 += 7e-4 * p_ratio * theta**2 * freq_ghz**2 / 1000

    # Water vapor absorption (peak near 22 GHz)
    e_s = 6.1121 * math.exp(17.502 * temperature_c / (240.97 + temperature_c))
    rho_w = humidity_pct / 100.0 * e_s * 0.622 / (1013.25 - e_s) * 100

    f_h2o = 22.235
    delta_h2o = 3.0
    gamma_h2o = (
        0.0001 * rho_w * theta**3.5 * freq_ghz**2 / (1 + ((freq_ghz - f_h2o) / delta_h2o) ** 2)
    )

    total_rate = gamma_o2 + gamma_h2o  # dB/km

    # Elevation scaling (less atmosphere at higher angles)
    if elevation_deg > 0:
        elev_rad = math.radians(max(0.5, elevation_deg))
        scale = min(1.0, 1.0 / math.sin(elev_rad))
    else:
        scale = 1.0

    return total_rate * range_km * scale


def compute_rain_loss(
    freq_hz: float,
    range_m: float,
    rain_rate_mmh: float,
) -> float:
    """Compute one-way rain attenuation using simplified ITU-R P.838 model.

    Args:
        freq_hz: Frequency (Hz)
        range_m: Path length (m)
        rain_rate_mmh: Rain rate (mm/hour)

    Returns:
        One-way rain loss (dB, positive value)
    """
    if rain_rate_mmh <= 0:
        return 0.0

    freq_ghz = freq_hz / 1e9
    if freq_ghz < 1:
        return 0.0

    range_km = range_m / 1000.0

    # ITU-R P.838 simplified: gamma_R = k * R^alpha
    log_f = math.log10(max(1.0, freq_ghz))
    log_k = -5.33 + 0.7 * log_f + 0.15 * log_f**2
    k = 10**log_k
    alpha = max(0.8, min(1.3, 1.2 - 0.1 * log_f))

    gamma_r = k * (rain_rate_mmh**alpha)

    # Rain cell extent (higher rain rates → smaller cells)
    rain_extent_km = max(1.0, 35.0 * math.exp(-0.02 * rain_rate_mmh))
    effective_km = min(range_km, rain_extent_km)

    return gamma_r * effective_km


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
