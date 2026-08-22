"""Design-time track accuracy: measurement error, tracking index, steady-state covariance.

This is not a tracker. It runs no recursion, holds no state, and processes no
detections; the package's non-goals bar a real-time DSP tracker and that line
stays. What it computes is the *steady-state* result, which is algebra rather
than recursion: under stationary noise and a constant revisit interval the
Kalman filter settles to gains and a covariance available in closed form. A
designer wants that number before any filter exists.

The chain runs

    SNR + bandwidth  ->  sigma_range
    SNR + beamwidth  ->  sigma_angle  ->  sigma_crossrange = R * sigma_angle
    sigma_w, revisit T, target maneuver  ->  tracking index  ->  alpha, beta
                                          ->  steady-state sigma_pos, sigma_vel

Every input already exists in this package, which is the reason the model
belongs here rather than in a tracking library: the array sets the beamwidth,
the radar equation sets the SNR, and the scheduler sets the revisit interval.
Tracking libraries take the measurement covariance as *given*; nothing in them
derives it from an aperture.

Cross-range is the metric that makes the aperture trade visible. At X-band,
100 km, 20 dB SNR, 10 MHz bandwidth and a 1 degree beam, sigma_range is 1.5 m
while cross-range error is 77 m -- fifty times worse, and improvable only by
growing the aperture.

SNR convention
--------------
Two conventions appear in the literature and they differ by a factor of two:

    POMR Eq. (18.33)   sigma_R = dR / sqrt(SNR)      with SNR = 2E/N0
    Curry Eq. (8.6)    sigma_R = dR / sqrt(2 * S/N)  with S/N = E/N0

They are algebraically identical. This package's range equation
(``models/radar/equation.py``) produces the Curry/Barton S/N, so every function
here takes that S/N and uses the ``sqrt(2 * SNR)`` form. POMR's angle relation
Eq. (18.63) already carries the factor of two, so range, angle, and Doppler end
up on one convention -- the same discipline commit 990045c applied to noise
temperature.

Sources
-------
Richards, Scheer & Holm, *Principles of Modern Radar: Basic Principles*,
SciTech, 2010 (ISBN 9781891121524). Ch. 18 "Radar Measurements"; Ch. 19 "Radar
Tracking Algorithms" (W. D. Blair). Read locally, 2026-08-18.

Curry, *Radar System Performance Modeling*, 2nd ed., Artech House, 2005
(ISBN 1-58053-816-9), Ch. 8 "Radar Measurement and Tracking", pp. 165-193.

Kalata, "The Tracking Index: A Generalized Parameter for alpha-beta and
alpha-beta-gamma Target Trackers", IEEE Trans. AES-20(2), pp. 174-182, 1984,
doi:10.1109/TAES.1984.310438.

Mahafza, *Radar Systems Analysis and Design Using MATLAB*, Chapman & Hall/CRC,
Ch. 11, Eq. (11.94) for the sensor-noise-only variance reduction ratio.
"""

from __future__ import annotations

import math

from phased_array_systems.constants import C

# Monopulse difference-pattern slope. Curry p. 170 gives 1.6 as typical and
# notes the same value approximates non-monopulse multipulse measurement of
# non-fluctuating targets. POMR p. 708 uses k_m = 1.6 in its worked comparison.
DEFAULT_MONOPULSE_SLOPE = 1.6

# POMR Eq. (18.63) is derived for SNR > 13 dB. Below that the monopulse ratio
# is a notably biased estimate of the angle (Eq. 18.64) and the variance form
# is optimistic. Reported, not enforced: the caller decides.
MONOPULSE_SNR_FLOOR_DB = 13.0


def _snr_linear(snr_db: float) -> float:
    return float(10.0 ** (snr_db / 10.0))


# ---------------------------------------------------------------------------
# Measurement accuracy (POMR ch. 18 / Curry ch. 8)
# ---------------------------------------------------------------------------


def range_resolution_m(bandwidth_hz: float, resolution_alpha: float = 1.0) -> float:
    """dR = alpha * c / (2 B), POMR Eq. (18.34).

    ``resolution_alpha`` is POMR's 1 < alpha < 2 degradation factor covering
    windowing and system error; alpha = 1 is the matched-filter ideal.
    """
    if bandwidth_hz <= 0:
        raise ValueError("bandwidth_hz must be > 0")
    if resolution_alpha <= 0:
        raise ValueError("resolution_alpha must be > 0")
    return float(resolution_alpha * C / (2.0 * bandwidth_hz))


def range_sigma_m(
    snr_db: float,
    bandwidth_hz: float,
    resolution_alpha: float = 1.0,
) -> float:
    """sigma_R = dR / sqrt(2 * SNR), Curry Eq. (8.6) / POMR Eq. (18.33).

    Thermal (SNR-driven) term only. Curry Eq. (8.5) adds fixed-random and bias
    terms in quadrature; those are hardware assertions, not consequences of the
    design, so they are left to the caller.
    """
    snr = _snr_linear(snr_db)
    if snr <= 0:
        raise ValueError("snr_db must give positive linear SNR")
    return float(range_resolution_m(bandwidth_hz, resolution_alpha) / math.sqrt(2.0 * snr))


def angle_sigma_deg(
    snr_db: float,
    beamwidth_deg: float,
    monopulse_slope: float = DEFAULT_MONOPULSE_SLOPE,
) -> float:
    """sigma_theta = theta_3dB / (k_m * sqrt(2 * SNR)), POMR Eq. (18.63) / Curry Eq. (8.8).

    Valid above ``MONOPULSE_SNR_FLOOR_DB``; see the module note.

    Thermal (SNR-driven) term only, as with :func:`range_sigma_m`. Curry
    Eq. (8.7) adds fixed-random and bias terms in quadrature, and target glint
    can dominate angular error at short range (Curry p. 170). None of those are
    consequences of the array design, so they are left to the caller.
    """
    if beamwidth_deg <= 0:
        raise ValueError("beamwidth_deg must be > 0")
    if monopulse_slope <= 0:
        raise ValueError("monopulse_slope must be > 0")
    snr = _snr_linear(snr_db)
    return float(beamwidth_deg / (monopulse_slope * math.sqrt(2.0 * snr)))


def scan_broadened_beamwidth_deg(beamwidth_deg: float, scan_angle_deg: float) -> float:
    """theta_phi = theta_B / cos(phi), Curry Eq. (8.9).

    A phased array's beam broadens off broadside, so angle accuracy degrades
    with scan angle even at constant SNR.
    """
    if abs(scan_angle_deg) >= 90.0:
        raise ValueError("scan_angle_deg must be within +/-90 degrees")
    return float(beamwidth_deg / math.cos(math.radians(scan_angle_deg)))


def crossrange_sigma_m(range_m: float, angle_sigma_deg_value: float) -> float:
    """sigma_D = R * sigma_A, Curry Eq. (8.10). Angle in degrees, result in metres."""
    if range_m < 0:
        raise ValueError("range_m must be >= 0")
    return float(range_m * math.radians(angle_sigma_deg_value))


def velocity_sigma_ms(
    snr_db: float,
    coherent_dwell_s: float,
    wavelength_m: float,
) -> float:
    """sigma_V = lambda / (2 tau sqrt(2 SNR)), Curry Eq. (8.13).

    Curry attributes the form to Barton & Ward, *Handbook of Radar
    Measurement*, pp. 101-103. Equivalent to POMR Eq. (18.31) under the
    convention noted in the module docstring.
    """
    if coherent_dwell_s <= 0:
        raise ValueError("coherent_dwell_s must be > 0")
    if wavelength_m <= 0:
        raise ValueError("wavelength_m must be > 0")
    snr = _snr_linear(snr_db)
    return float(wavelength_m / (2.0 * coherent_dwell_s * math.sqrt(2.0 * snr)))


def combine_angle_errors_deg(*sigma_deg: float) -> float:
    """Root-sum-square of independent angle error terms.

    The seam that lets a thermal-noise angle error combine with the hardware
    pointing error from ``models/antenna/errors.py``: phase-shifter bits and
    calibration residue then propagate all the way to track accuracy, which is
    the connection no tracking library can make.
    """
    total_sq = 0.0
    for term in sigma_deg:
        if term < 0:
            raise ValueError("angle error terms must be >= 0")
        total_sq += term * term
    return float(math.sqrt(total_sq))


# ---------------------------------------------------------------------------
# Track filtering, steady state (POMR ch. 19 sec. 19.2)
# ---------------------------------------------------------------------------


def tracking_index(sigma_v: float, sigma_w: float, revisit_s: float) -> float:
    """Random tracking index Gamma = sigma_v T^2 / sigma_w, POMR Eq. (19.47).

    Kalata's parameter: the ratio of position uncertainty from target
    maneuverability to that from the sensor measurement. It is the single
    number that sets the steady-state filter.
    """
    if sigma_v < 0:
        raise ValueError("sigma_v must be >= 0")
    if sigma_w <= 0:
        raise ValueError("sigma_w must be > 0")
    if revisit_s <= 0:
        raise ValueError("revisit_s must be > 0")
    return float(sigma_v * revisit_s**2 / sigma_w)


def alpha_beta_gains(gamma: float) -> tuple[float, float]:
    """Steady-state alpha-beta gains from the tracking index, POMR Eqs. (19.54)/(19.55).

    Satisfies the Kalata relation beta = 2(2 - alpha) - 4 sqrt(1 - alpha)
    (Eq. 19.56) and inverts exactly through Gamma = beta / sqrt(1 - alpha).

    Computed through a rearrangement rather than from Eqs. (19.54)/(19.55)
    literally, because those forms lose precision as alpha approaches 1: they
    build alpha from a difference of large terms and the caller then needs
    1 - alpha, so the relative error in beta reaches 4e-5 by Gamma = 1e5.
    Substituting r = sqrt(1 - alpha) into Eq. (19.47) with Eq. (19.56) gives

        Gamma = 2 (1 - r)^2 / r   ->   2 r^2 - (4 + Gamma) r + 2 = 0
        r = (4 + Gamma - sqrt(Gamma^2 + 8 Gamma)) / 4      (smaller root)
        alpha = 1 - r^2,   beta = 2 (1 - r)^2

    which is the same solution with 1 - alpha carried exactly as r^2. It holds
    the identity to ~1e-12 at Gamma = 1e5. Both forms are pinned against each
    other in the oracle tests; this is presentation, not a different model.
    """
    if gamma < 0:
        raise ValueError("gamma must be >= 0")
    if gamma == 0:
        return 0.0, 0.0
    r = (4.0 + gamma - math.sqrt(gamma**2 + 8.0 * gamma)) / 4.0
    return float(1.0 - r * r), float(2.0 * (1.0 - r) ** 2)


def steady_state_sigmas(
    sigma_w: float,
    alpha: float,
    beta: float,
    revisit_s: float,
) -> tuple[float, float]:
    """Steady-state position and velocity RMS error, POMR Eq. (19.53).

    P = sigma_w^2 * [[alpha,            beta/T                     ],
                     [beta/T,  beta(2 alpha - beta)/(2(1-alpha)T^2)]]

    so sigma_pos = sigma_w sqrt(alpha) and
    sigma_vel = (sigma_w/T) sqrt(beta(2 alpha - beta)/(2(1 - alpha))).

    This is the *total* steady-state error, process noise included: it matches
    the fixed-gain covariance recursion iterated to convergence with Q present.
    For the no-maneuver figure use :func:`variance_reduction_position`.
    """
    if sigma_w <= 0:
        raise ValueError("sigma_w must be > 0")
    if revisit_s <= 0:
        raise ValueError("revisit_s must be > 0")
    if not 0.0 <= alpha < 1.0:
        raise ValueError("alpha must satisfy 0 <= alpha < 1")
    if beta < 0:
        raise ValueError("beta must be >= 0")
    sigma_pos = sigma_w * math.sqrt(alpha)
    vel_var = beta * (2.0 * alpha - beta) / (2.0 * (1.0 - alpha) * revisit_s**2)
    sigma_vel = sigma_w * math.sqrt(max(0.0, vel_var))
    return float(sigma_pos), float(sigma_vel)


def variance_reduction_position(alpha: float, beta: float) -> float:
    """Sensor-noise-only VRR, Mahafza Eq. (11.94).

    (VRR)_x = (2 alpha^2 - 3 alpha beta + 2 beta) / (alpha (4 - 2 alpha - beta))

    Distinct from :func:`steady_state_sigmas`, and both are correct: this is
    the variance ratio with the process noise removed (no maneuver), verified
    against the Q = 0 covariance recursion. It answers "how much does filtering
    reduce measurement noise", while Eq. (19.53) answers "how well is the
    target actually located". A third form circulating in the literature,
    (2 alpha^2 + 2 beta + alpha beta)/(alpha(4 - 2 alpha - beta)), is wrong: it
    exceeds unity, i.e. claims filtering amplifies noise.
    """
    denom = alpha * (4.0 - 2.0 * alpha - beta)
    if denom <= 0:
        raise ValueError("alpha, beta outside the stable region")
    return float((2.0 * alpha**2 - 3.0 * alpha * beta + 2.0 * beta) / denom)


def deterministic_tracking_index(
    accel_max_ms2: float,
    revisit_s: float,
    sigma_w: float,
) -> float:
    """Gamma_D = A_max T^2 / sigma_w, POMR Eq. (19.59)."""
    if accel_max_ms2 < 0:
        raise ValueError("accel_max_ms2 must be >= 0")
    if revisit_s <= 0:
        raise ValueError("revisit_s must be > 0")
    if sigma_w <= 0:
        raise ValueError("sigma_w must be > 0")
    return float(accel_max_ms2 * revisit_s**2 / sigma_w)


def process_noise_from_maneuver(gamma_d: float, accel_max_ms2: float) -> float:
    """sigma_v = kappa_1_min(Gamma_D) * A_max, POMR Eqs. (19.63)/(19.66).

    kappa_1_min = 0.87 - 0.09 log10(Gamma_D) - 0.02 [log10(Gamma_D)]^2

    Lets the caller state a physical maneuver ("the target pulls 4 g") instead
    of tuning a process-noise variance. POMR fits the curve over
    0.01 <= Gamma_D <= 10; outside that band the fit is extrapolated and the
    caller should treat the result as indicative.
    """
    if gamma_d <= 0:
        raise ValueError("gamma_d must be > 0")
    if accel_max_ms2 < 0:
        raise ValueError("accel_max_ms2 must be >= 0")
    log_gd = math.log10(gamma_d)
    kappa = 0.87 - 0.09 * log_gd - 0.02 * log_gd**2
    return float(kappa * accel_max_ms2)


def maneuver_lag_m(
    sigma_w: float,
    alpha: float,
    beta: float,
    gamma_d: float,
) -> float:
    """Maximum position MSE under a sustained maneuver, POMR Eq. (19.60).

    MMSE_p = sigma_w^2 [ (2 alpha^2 + beta(2 - 3 alpha))/(alpha(4 - 2 alpha - beta))
                         + (1 - alpha)^2 Gamma_D^2 / beta^2 ]

    Returned as an RMS distance. The second term is the deterministic lag: a
    filter tuned for a quiet target falls progressively behind a maneuvering
    one, and no amount of SNR fixes it.
    """
    if beta <= 0:
        raise ValueError("beta must be > 0")
    denom = alpha * (4.0 - 2.0 * alpha - beta)
    if denom <= 0:
        raise ValueError("alpha, beta outside the stable region")
    noise_term = (2.0 * alpha**2 + beta * (2.0 - 3.0 * alpha)) / denom
    lag_term = (1.0 - alpha) ** 2 * gamma_d**2 / beta**2
    return float(sigma_w * math.sqrt(noise_term + lag_term))
