"""MTI clutter suppression: spectral spread, canceller improvement factor, blind speeds.

The clutter model in ``models/radar/clutter.py`` treats clutter as a static RCS
in the resolution cell: it says how much clutter a geometry produces but not how
much of it a radar can remove. That leaves the detection chain broken in the
middle, because a ground-based radar facing 30 dB of subclutter visibility is
not undetectable, it is a radar with an MTI filter. This module supplies the
missing step, so the chain runs

    clutter RCS -> MTI improvement factor -> post-MTI SCNR -> detection

and, through SNR, on into the track accuracy of ``models/radar/tracking.py``.

Clutter is modeled as a zero-mean Gaussian Doppler spectrum of standard
deviation sigma_v in velocity. The spread is a property of the scatterers --
wind-blown foliage, sea surface motion -- and Skolnik notes it is independent
of radar frequency when expressed in velocity, which is why the velocity form
is the input and the frequency form is derived.

The canceller is the binomial (N-1)th-difference FIR filter with weights
w_k = (-1)^k C(N-1, k): the two-pulse canceller [1, -1] and the three-pulse
canceller [1, -2, 1] are the familiar cases. Improvement factor is computed
from the general quadratic form rather than from the published closed forms,
and reduces to them exactly (verified in the oracle tests):

    I = sum_k w_k^2 / sum_i sum_j w_i w_j rho_c[i-j]

Signal gain and clutter attenuation are reported separately because they are
not interchangeable. Improvement factor I = G * CA is the figure of merit that
belongs in a detection budget, since it accounts for both the filter's gain on
the target and its rejection of clutter; clutter attenuation alone understates
the benefit.

Sources
-------
Richards, *Fundamentals of Radar Signal Processing*: clutter attenuation
Eq. (5.43); average signal gain over Doppler, p. 246; Gaussian clutter
autocorrelation Eq. (5.53); two- and three-pulse improvement factors
Eqs. (5.52)/(5.54), p. 247.

Skolnik, *Introduction to Radar Systems*, ch. 15, for the velocity-to-frequency
spectral relation and the frequency independence of the velocity spread.

Levanon, *Radar Principles*, Wiley, 1988, for the improvement-factor definition
I = (S/C)_out / (S/C)_in.
"""

from __future__ import annotations

import math
from math import comb

from phased_array_systems.constants import C


def clutter_spectral_std_hz(clutter_velocity_std_ms: float, wavelength_m: float) -> float:
    """sigma_c = 2 sigma_v / lambda (Skolnik ch. 15).

    The velocity spread is a property of the clutter, not the radar, so the
    same wooded hillside produces a wider Doppler spectrum at higher frequency.
    """
    if clutter_velocity_std_ms < 0:
        raise ValueError("clutter_velocity_std_ms must be >= 0")
    if wavelength_m <= 0:
        raise ValueError("wavelength_m must be > 0")
    return float(2.0 * clutter_velocity_std_ms / wavelength_m)


def normalized_clutter_spread_rad(clutter_std_hz: float, prf_hz: float) -> float:
    """sigma_omega = 2 pi sigma_c / PRF, the spread in normalized angular frequency.

    This is the only clutter quantity the canceller math needs: everything
    downstream depends on the spectrum's width relative to the PRF, not on its
    absolute width.
    """
    if clutter_std_hz < 0:
        raise ValueError("clutter_std_hz must be >= 0")
    if prf_hz <= 0:
        raise ValueError("prf_hz must be > 0")
    return float(2.0 * math.pi * clutter_std_hz / prf_hz)


def clutter_autocorrelation(sigma_omega_rad: float, lag: int) -> float:
    """rho_c[k] = exp(-(sigma_omega k)^2 / 2), Richards FRSP Eq. (5.53).

    The normalized autocorrelation of a Gaussian clutter spectrum, valid for
    sigma_omega << pi. At the wide-spectrum limit the approximation breaks down
    along with the premise that the clutter is narrowband relative to the PRF.
    """
    if sigma_omega_rad < 0:
        raise ValueError("sigma_omega_rad must be >= 0")
    return float(math.exp(-((sigma_omega_rad * lag) ** 2) / 2.0))


def canceller_weights(n_pulse: int) -> list[int]:
    """Binomial (N-1)th-difference canceller weights w_k = (-1)^k C(N-1, k).

    N = 2 gives [1, -1] and N = 3 gives [1, -2, 1], the conventional two- and
    three-pulse cancellers.
    """
    if n_pulse < 2:
        raise ValueError("n_pulse must be >= 2")
    return [(-1) ** k * comb(n_pulse - 1, k) for k in range(n_pulse)]


def mti_signal_gain(n_pulse: int) -> float:
    """Average signal gain over all Doppler shifts, G = sum_k w_k^2.

    Richards FRSP p. 246 defines the gain as the mean of |H(F)|^2 over the
    unambiguous Doppler band, which for an FIR filter is the sum of the squared
    weights by Parseval. Gives G = 2 (3.0 dB) for the two-pulse canceller and
    G = 6 (7.8 dB) for the three-pulse, matching FRSP p. 247.

    The target velocity is assumed unknown a priori; a radar that knows where
    to look does better than this average.
    """
    return float(sum(w * w for w in canceller_weights(n_pulse)))


def mti_improvement_factor(n_pulse: int, sigma_omega_rad: float) -> float:
    """Improvement factor I = G * CA for an N-pulse binomial canceller.

    Computed from the general quadratic form

        I = sum_k w_k^2 / sum_i sum_j w_i w_j rho_c[i-j]

    rather than from the published closed forms, which it reproduces exactly:
    Richards FRSP Eq. (5.52) gives 1/(1 - rho[1]) for N = 2 and Eq. (5.54)
    gives 1/(1 - (4/3) rho[1] + (1/3) rho[2]) for N = 3. Both are asserted
    against this function in the oracle tests.

    Returned as a linear ratio. The value grows without bound as the clutter
    spectrum narrows, which is physical -- perfectly stationary clutter is
    perfectly cancellable -- but a design should not lean on figures far beyond
    the system's phase noise and stability limits, which this model does not
    represent.
    """
    weights = canceller_weights(n_pulse)
    gain = sum(w * w for w in weights)
    residue = sum(
        weights[i] * weights[j] * clutter_autocorrelation(sigma_omega_rad, abs(i - j))
        for i in range(n_pulse)
        for j in range(n_pulse)
    )
    if residue <= 0:
        raise ValueError("clutter residue is non-positive; sigma_omega out of valid range")
    return float(gain / residue)


def mti_clutter_attenuation(n_pulse: int, sigma_omega_rad: float) -> float:
    """CA = I / G, the clutter power ratio across the filter (FRSP Eq. 5.43).

    Distinct from the improvement factor: this is rejection alone, with no
    credit for the filter's gain on the target.
    """
    return float(mti_improvement_factor(n_pulse, sigma_omega_rad) / mti_signal_gain(n_pulse))


def required_clutter_attenuation_db(
    target_rcs_dbsm: float,
    clutter_rcs_dbsm: float,
    required_scr_db: float,
) -> float:
    """CA_req = (S/C)_required - (sigma_target - sigma_clutter), in dB.

    How much clutter power must be removed for the target to clear the required
    signal-to-clutter ratio. Positive means suppression is needed.
    """
    return float(required_scr_db - (target_rcs_dbsm - clutter_rcs_dbsm))


def blind_speed_ms(prf_hz: float, wavelength_m: float, harmonic: int = 1) -> float:
    """v_blind = n PRF lambda / 2: target speeds the canceller nulls along with clutter.

    A target at a blind speed produces the same phase advance per pulse as
    stationary clutter and is cancelled with it. The first blind speed bounds
    the useful Doppler coverage of a single-PRF MTI.
    """
    if prf_hz <= 0:
        raise ValueError("prf_hz must be > 0")
    if wavelength_m <= 0:
        raise ValueError("wavelength_m must be > 0")
    if harmonic < 1:
        raise ValueError("harmonic must be >= 1")
    return float(harmonic * prf_hz * wavelength_m / 2.0)


def doppler_shift_hz(radial_velocity_ms: float, wavelength_m: float) -> float:
    """f_d = 2 v_r / lambda, the monostatic two-way Doppler shift."""
    if wavelength_m <= 0:
        raise ValueError("wavelength_m must be > 0")
    return float(2.0 * radial_velocity_ms / wavelength_m)


def unambiguous_range_m(prf_hz: float) -> float:
    """R_ua = c / (2 PRF)."""
    if prf_hz <= 0:
        raise ValueError("prf_hz must be > 0")
    return float(C / (2.0 * prf_hz))
