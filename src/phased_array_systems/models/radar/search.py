"""Power-aperture product: the mission figure of merit for volume search.

Note the dimensions carefully, because the name invites confusion with the
aperture power *density* in ``models/swapc/power.py``:

    power-aperture product   P_avg * A_e     [W * m^2]
    aperture power density   P / A_ap        [W / m^2]

They are dimensional inverses and they pull in opposite directions. The
power-aperture product says how much power and aperture the search mission
demands; the heat flux constrains how tightly that power may be packaged.
Neither alone produces a sensible design.

The classic search relation (Barton, *Radar Equations for Modern Radar*, 2013;
Skolnik, *Introduction to Radar Systems*, 3rd ed., 2001) is

    P_avg * A_e  =  4*pi * k * T_s * L * (S/N) * R^4 * Omega / (sigma * t_s)

Frequency and antenna gain do not appear: search performance depends on the
product of average power and effective aperture, not on how the aperture is
partitioned into beams. Required power-aperture scales as R^4 and as
Omega/t_s, so halving the revisit time doubles what the mission demands.
"""

from __future__ import annotations

import math

from phased_array_systems.constants import K_B, C


def effective_aperture_m2(gain_db: float, freq_hz: float) -> float:
    """A_e = G lambda^2 / (4 pi).

    The direction this package never computed: it converts area to gain in
    wavelength units (``compute_directivity_rectangular``) but never gain back
    to a physical capture area.
    """
    wavelength_m = C / freq_hz
    return float((10.0 ** (gain_db / 10.0)) * wavelength_m**2 / (4.0 * math.pi))


def power_aperture_product_w_m2(rf_avg_power_w: float, effective_aperture_m2: float) -> float:
    """P_avg * A_e in W*m^2."""
    return rf_avg_power_w * effective_aperture_m2


def required_power_aperture_w_m2(
    range_m: float,
    target_rcs_m2: float,
    search_solid_angle_sr: float,
    frame_time_s: float,
    snr_required_db: float,
    system_noise_temp_k: float,
    loss_db: float = 0.0,
) -> float:
    """Power-aperture product a volume-search task demands.

    Args:
        range_m: Required detection range
        target_rcs_m2: Target radar cross section
        search_solid_angle_sr: Solid angle to be searched each frame
        frame_time_s: Time allowed to search that volume once
        snr_required_db: Detectability factor for the required Pd/Pfa
        system_noise_temp_k: System noise temperature
        loss_db: Total search losses (beam shape, scan, processing)

    Returns:
        Required P_avg * A_e in W*m^2.
    """
    if min(range_m, target_rcs_m2, search_solid_angle_sr, frame_time_s) <= 0:
        raise ValueError("range, RCS, solid angle and frame time must be positive")
    snr_linear = 10.0 ** (snr_required_db / 10.0)
    loss_linear = 10.0 ** (loss_db / 10.0)
    return float(
        4.0
        * math.pi
        * K_B
        * system_noise_temp_k
        * loss_linear
        * snr_linear
        * range_m**4
        * search_solid_angle_sr
        / (target_rcs_m2 * frame_time_s)
    )


def search_solid_angle_sr(az_extent_deg: float, el_extent_deg: float) -> float:
    """Solid angle of a rectangular search sector, small-angle form."""
    return float(math.radians(az_extent_deg) * math.radians(el_extent_deg))
