"""Surface and volume clutter models for radar.

Implements empirical clutter RCS models for:
- Sea surface clutter (NRL empirical model, fitted to the Nathanson tables)
- Ground/terrain clutter (constant-gamma model with published gamma values)
- Rain volume clutter (Marshall-Palmer reflectivity)

References:
    - Gregers-Hansen, V. and Mittal, R., "An Improved Empirical Model for
      Radar Sea Clutter Reflectivity", NRL/MR/5310-12-9346 (2012); also
      IEEE Trans. AES 48(4), 2012
    - Barton, D., "Radar System Analysis and Modeling" (constant-gamma)
    - Skolnik, M. "Radar Handbook", 3rd Ed., Ch. 7
    - Nathanson, F. "Radar Design Principles", 2nd Ed.
    - Long, M. "Radar Reflectivity of Land and Sea", 3rd Ed.
"""

from __future__ import annotations

import math
from typing import Literal

from phased_array_systems.constants import C_LIGHT

# Sea state parameters (Douglas scale approximation)
# Maps sea state (0-6) to approximate significant wave height (m)
SEA_STATE_TO_WAVE_HEIGHT = {
    0: 0.0,  # Calm (glassy)
    1: 0.1,  # Calm (rippled)
    2: 0.3,  # Smooth
    3: 0.9,  # Slight
    4: 1.5,  # Moderate
    5: 2.5,  # Rough
    6: 4.0,  # Very rough
}

TerrainType = Literal["rural", "urban", "forest", "desert", "wetland"]


def sea_clutter_sigma0(
    sea_state: int,
    grazing_angle_deg: float,
    freq_hz: float,
    polarization: Literal["HH", "VV", "HV"] = "HH",
) -> float:
    """Compute sea surface normalized radar cross section (sigma-0).

    Uses the GIT (Georgia Institute of Technology) model for sea
    clutter backscatter. Valid for frequencies 1-100 GHz.

    The GIT model provides sigma-0 in dB as a function of:
    - Grazing angle
    - Sea state (wave height)
    - Frequency
    - Polarization

    Args:
        sea_state: Sea state (0-6, Douglas scale)
        grazing_angle_deg: Grazing angle from horizon (deg), 0.1 to 90
        freq_hz: Radar frequency (Hz)
        polarization: Antenna polarization (HH, VV, or HV)

    Returns:
        Normalized RCS (sigma-0) in dB (dBsm/m^2)

    Raises:
        ValueError: If sea_state not in 0-6 or grazing angle invalid
    """
    if not 0 <= sea_state <= 6:
        raise ValueError("sea_state must be between 0 and 6")
    if not 0.1 <= grazing_angle_deg <= 90:
        raise ValueError("grazing_angle_deg must be between 0.1 and 90")

    psi_deg = grazing_angle_deg
    psi_rad = math.radians(psi_deg)

    # NRL model validity: 0.5-35 GHz, grazing 0.1-60 deg
    freq_ghz = max(0.5, min(35.0, freq_hz / 1e9))
    psi_deg = min(psi_deg, 60.0)

    # NRL empirical model coefficients (Gregers-Hansen & Mittal 2012),
    # fitted to the Nathanson tables within ~2.3 dB for 0.1-10 deg grazing
    if polarization == "VV":
        c1, c2, c3, c4, c5 = -50.796, 25.93, 0.7093, 21.588, 0.00211
        crosspol_offset = 0.0
    else:
        # HH coefficients; HV uses HH minus a fixed offset (cross-pol sea
        # clutter runs 5-15 dB below copol; Long, ch. 6)
        c1, c2, c3, c4, c5 = -73.0, 20.781, 7.351, 25.65, 0.0054
        crosspol_offset = -10.0 if polarization == "HV" else 0.0

    sigma0_db = (
        c1
        + c2 * math.log10(math.sin(psi_rad))
        + (27.5 + c3 * psi_deg) * math.log10(freq_ghz) / (1.0 + 0.95 * psi_deg)
        + c4 * (sea_state + 1.0) ** (1.0 / (2.0 + 0.085 * psi_deg + 0.033 * sea_state))
        + c5 * psi_deg**2
    )

    return float(sigma0_db + crosspol_offset)


def sea_clutter_rcs(
    sea_state: int,
    grazing_angle_deg: float,
    freq_hz: float,
    resolution_cell_m2: float,
    polarization: Literal["HH", "VV", "HV"] = "HH",
) -> float:
    """Compute sea surface clutter RCS for a resolution cell.

    Args:
        sea_state: Sea state (0-6, Douglas scale)
        grazing_angle_deg: Grazing angle from horizon (deg)
        freq_hz: Radar frequency (Hz)
        resolution_cell_m2: Resolution cell area (m^2)
        polarization: Antenna polarization

    Returns:
        Clutter RCS in dBsm
    """
    sigma0_db = sea_clutter_sigma0(sea_state, grazing_angle_deg, freq_hz, polarization)

    # Clutter RCS = sigma_0 * cell_area
    cell_area_db = 10 * math.log10(max(1.0, resolution_cell_m2))
    clutter_rcs_dbsm = sigma0_db + cell_area_db

    return clutter_rcs_dbsm


def ground_clutter_sigma0(
    terrain_type: TerrainType,
    grazing_angle_deg: float,
    freq_hz: float,
) -> float:
    """Compute ground surface normalized RCS (sigma-0).

    Constant-gamma model: sigma0 = gamma * sin(psi), i.e.
    sigma0_dB = gamma_dB + 10*log10(sin psi). Gamma values are published
    medians (Barton, "Radar System Analysis and Modeling"; Nathanson);
    actual terrain scatters several dB about these. Constant-gamma is
    frequency-independent to first order; the freq_hz argument is kept
    for API compatibility and validity checks only.

    Args:
        terrain_type: Type of terrain surface
        grazing_angle_deg: Grazing angle from horizon (deg), 0.1 to 90
        freq_hz: Radar frequency (Hz); unused (constant-gamma model)

    Returns:
        Normalized RCS (sigma-0) in dB (dBsm/m^2)

    Raises:
        ValueError: If grazing angle invalid
    """
    if not 0.1 <= grazing_angle_deg <= 90:
        raise ValueError("grazing_angle_deg must be between 0.1 and 90")

    psi = math.radians(grazing_angle_deg)

    # Published median gamma values (dB): Barton constant-gamma model
    terrain_gamma_db = {
        "rural": -15.0,  # farmland/open country
        "urban": -5.0,  # built-up areas
        "forest": -10.0,  # wooded terrain
        "desert": -20.0,  # desert/flatland
        "wetland": -17.0,  # marsh/wetland (between farmland and desert)
    }

    gamma_db = terrain_gamma_db.get(terrain_type, terrain_gamma_db["rural"])

    return gamma_db + 10 * math.log10(math.sin(psi))


def ground_clutter_rcs(
    terrain_type: TerrainType,
    grazing_angle_deg: float,
    freq_hz: float,
    resolution_cell_m2: float,
) -> float:
    """Compute ground clutter RCS for a resolution cell.

    Args:
        terrain_type: Type of terrain surface
        grazing_angle_deg: Grazing angle from horizon (deg)
        freq_hz: Radar frequency (Hz)
        resolution_cell_m2: Resolution cell area (m^2)

    Returns:
        Clutter RCS in dBsm
    """
    sigma0_db = ground_clutter_sigma0(terrain_type, grazing_angle_deg, freq_hz)

    cell_area_db = 10 * math.log10(max(1.0, resolution_cell_m2))
    clutter_rcs_dbsm = sigma0_db + cell_area_db

    return clutter_rcs_dbsm


def rain_reflectivity(
    rain_rate_mm_hr: float,
    freq_hz: float,
) -> float:
    """Compute rain volume reflectivity (eta) in dB.

    Uses the Z-R relationship and Rayleigh scattering.
    Z = 200 * R^1.6 (Marshall-Palmer relation)

    Args:
        rain_rate_mm_hr: Rain rate (mm/hour)
        freq_hz: Radar frequency (Hz)

    Returns:
        Volume reflectivity (eta) in dB (dBsm/m^3)
    """
    if rain_rate_mm_hr <= 0:
        return -100.0  # Essentially no rain clutter

    # Marshall-Palmer Z-R relationship
    # Z (mm^6/m^3) = 200 * R^1.6
    z = 200 * (rain_rate_mm_hr**1.6)

    # Convert Z to reflectivity factor
    wavelength_m = C_LIGHT / freq_hz
    wavelength_cm = wavelength_m * 100

    # Rayleigh scattering: eta = (pi^5 / lambda^4) * |K|^2 * Z
    # |K|^2 ≈ 0.93 for water at microwave frequencies
    k_squared = 0.93

    # eta in m^-1 (linear)
    eta_linear = (
        (math.pi**5) / (wavelength_cm**4) * k_squared * z * 1e-18  # Convert mm^6 to m^6
    )

    # Convert to dB (dBsm/m^3)
    eta_db = 10 * math.log10(max(1e-20, eta_linear))

    return eta_db


def rain_clutter_rcs(
    rain_rate_mm_hr: float,
    freq_hz: float,
    resolution_volume_m3: float,
) -> float:
    """Compute rain volume clutter RCS.

    Args:
        rain_rate_mm_hr: Rain rate (mm/hour)
        freq_hz: Radar frequency (Hz)
        resolution_volume_m3: Resolution cell volume (m^3)

    Returns:
        Rain clutter RCS in dBsm
    """
    eta_db = rain_reflectivity(rain_rate_mm_hr, freq_hz)

    volume_db = 10 * math.log10(max(1.0, resolution_volume_m3))
    clutter_rcs_dbsm = eta_db + volume_db

    return clutter_rcs_dbsm


def compute_resolution_cell_area(
    range_m: float,
    range_resolution_m: float,
    azimuth_beamwidth_deg: float,
) -> float:
    """Compute resolution cell area for surface clutter.

    Area = range_resolution * range * azimuth_beamwidth (in radians)

    Args:
        range_m: Range to cell center (m)
        range_resolution_m: Range resolution (m), typically c/(2*B)
        azimuth_beamwidth_deg: Azimuth beamwidth (deg)

    Returns:
        Resolution cell area (m^2)
    """
    azimuth_rad = math.radians(azimuth_beamwidth_deg)
    cross_range_m = range_m * azimuth_rad
    area_m2 = range_resolution_m * cross_range_m
    return area_m2


def compute_resolution_volume(
    range_m: float,
    range_resolution_m: float,
    azimuth_beamwidth_deg: float,
    elevation_beamwidth_deg: float,
) -> float:
    """Compute resolution cell volume for volume clutter.

    Volume = range_resolution * (range * az_bw) * (range * el_bw)

    Args:
        range_m: Range to cell center (m)
        range_resolution_m: Range resolution (m)
        azimuth_beamwidth_deg: Azimuth beamwidth (deg)
        elevation_beamwidth_deg: Elevation beamwidth (deg)

    Returns:
        Resolution cell volume (m^3)
    """
    az_rad = math.radians(azimuth_beamwidth_deg)
    el_rad = math.radians(elevation_beamwidth_deg)

    cross_range_az = range_m * az_rad
    cross_range_el = range_m * el_rad

    volume_m3 = range_resolution_m * cross_range_az * cross_range_el
    return volume_m3


def compute_scr(
    target_rcs_dbsm: float,
    clutter_rcs_dbsm: float,
) -> float:
    """Compute signal-to-clutter ratio.

    Args:
        target_rcs_dbsm: Target RCS (dBsm)
        clutter_rcs_dbsm: Clutter RCS (dBsm)

    Returns:
        Signal-to-clutter ratio (dB)
    """
    return target_rcs_dbsm - clutter_rcs_dbsm


def compute_scnr(
    snr_db: float,
    scr_db: float,
) -> float:
    """Compute signal-to-clutter-plus-noise ratio.

    SCNR = 1 / (1/SNR + 1/SCR)

    In dB form, this requires conversion to linear.

    Args:
        snr_db: Signal-to-noise ratio (dB)
        scr_db: Signal-to-clutter ratio (dB)

    Returns:
        Signal-to-clutter-plus-noise ratio (dB)
    """
    snr_linear = 10 ** (snr_db / 10)
    scr_linear = 10 ** (scr_db / 10)

    # SCNR = S / (C + N) = 1 / (1/SNR + 1/SCR)
    if snr_linear <= 0 or scr_linear <= 0:
        return min(snr_db, scr_db)

    scnr_linear = 1.0 / (1.0 / snr_linear + 1.0 / scr_linear)
    scnr_db = 10 * math.log10(scnr_linear)

    return scnr_db
