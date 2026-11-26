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

That denominator is where the difficulty is. Written literally it is a
difference of terms of magnitude C(2N-2, N-1) whose true value is
O(sigma_omega^(2N-2)), so it loses every significant digit for a narrow clutter
spectrum -- 100% error at a 1 mm/s spread for N = 3, and a negative residue
raised as a spurious "out of valid range" for N >= 4. :func:`_clutter_residue`
evaluates it through two exact rearrangements instead, machine-accurate over
N = 2..8 and sigma_omega = 1e-8..5, with the small-spread limit

    I -> (2 / sigma_omega^2)^(N-1) / (N-1)!

Signal gain and clutter attenuation are reported separately because they are
not interchangeable. Improvement factor I = G * CA is the figure of merit that
belongs in a detection budget, since it accounts for both the filter's gain on
the target and its rejection of clutter; clutter attenuation alone understates
the benefit, and so does a *required* figure quoted against CA -- see
:func:`required_improvement_factor_db`.

G is the gain averaged over an unknown target Doppler. Where the target's
radial velocity is known, :func:`mti_target_gain` gives what the filter does to
that target specifically, which is zero at the blind speeds of
:func:`blind_speed_ms` -- there the canceller nulls the target along with the
clutter, and the averaged figure of merit is not merely optimistic but
qualitatively wrong.

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
import warnings
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


def canceller_autocorrelation(n_pulse: int) -> list[int]:
    """a_d = sum_i w_i w_{i+d}, the canceller weights' autocorrelation at lag d >= 0.

    ``a_0`` is the signal gain G. Derived from :func:`canceller_weights` rather
    than from the closed form a_d = (-1)^d C(2N-2, N-1-d) so that the two cannot
    drift apart, and kept in exact integer arithmetic.
    """
    weights = canceller_weights(n_pulse)
    return [sum(weights[i] * weights[i + d] for i in range(n_pulse - d)) for d in range(n_pulse)]


# Branch point between the two residue forms below, in units of the largest lag
# argument u = sigma_omega * (N - 1). Below it the power series' terms peak at
# m ~ u^2/2 <= 2, so at most one bit is lost to its alternating signs; above it
# the lag sum's own cancellation is O(1). The two agree to ~1e-12 at the
# boundary for N = 2..8, which is asserted in the oracle tests -- the constant
# is measured, not tuned.
SERIES_MAX_U = 2.0


def _clutter_residue(n_pulse: int, sigma_omega_rad: float) -> float:
    """sum_i sum_j w_i w_j rho_c[i-j], evaluated without catastrophic cancellation.

    Written over the weight autocorrelation as ``sum_d a_d rho_c[d]``. Because
    sum_d a_d = (sum_k w_k)^2 = 0 for any binomial canceller, that sum is a
    difference of terms of magnitude C(2N-2, N-1) whose true value is
    O(sigma_omega^(2N-2)) -- for a three-pulse canceller at a 1 mm/s clutter
    spread the result is 1e-15 assembled from terms of magnitude 6, i.e. pure
    rounding noise, and for N >= 4 it goes negative and the function used to
    reject the caller's perfectly valid input.

    Two exact rearrangements remove it, one for each end of the range.

    Narrow spectra: expand rho and exchange the sums,

        residue = sum_{m >= N-1} (-1)^m / m! * (sigma_omega^2/2)^m * S_m,
        S_m = sum_d a_d d^(2m)

    An N-pulse binomial canceller has an (N-1)-order zero at DC, so S_m is
    identically zero for every m < N-1: all of the cancellation *is* those
    leading terms, and the series simply does not compute them. They must be
    skipped rather than evaluated -- they are exactly zero in integer
    arithmetic but not in floating point, and adding them back injects an error
    that grows like eps/sigma_omega^2 relative to the answer.

    Wide spectra: use sum_d a_d = 0 to write residue = sum_d a_d (rho_c[d] - 1)
    and evaluate the bracket with ``expm1``.

    Worst case over N = 2..8 and sigma_omega = 1e-8..5 is a relative error of
    ~1e-13, against 100% error (or a spurious raise) from the quadratic form.
    """
    a = canceller_autocorrelation(n_pulse)

    if sigma_omega_rad * (n_pulse - 1) > SERIES_MAX_U:
        return 2.0 * math.fsum(
            a[d] * math.expm1(-((sigma_omega_rad * d) ** 2) / 2.0) for d in range(1, n_pulse)
        )

    # powers[d] carries (-x/2)^m d^(2m) / m! updated recursively, which keeps
    # d^(2m) from overflowing at large N.
    x = sigma_omega_rad * sigma_omega_rad
    powers = [1.0] * n_pulse
    residue = 0.0
    for m in range(1, 401):
        for d in range(1, n_pulse):
            powers[d] *= (-x / 2.0) * d * d / m
        if m < n_pulse - 1:
            continue  # S_m == 0 analytically; see the docstring
        term = 2.0 * math.fsum(a[d] * powers[d] for d in range(1, n_pulse))
        residue += term
        if abs(term) <= 1e-18 * abs(residue):
            break
    return residue


def mti_improvement_factor(n_pulse: int, sigma_omega_rad: float) -> float:
    """Improvement factor I = G * CA for an N-pulse binomial canceller.

    Computed from the general quadratic form

        I = sum_k w_k^2 / sum_i sum_j w_i w_j rho_c[i-j]

    rather than from the published closed forms, which it reproduces exactly:
    Richards FRSP Eq. (5.52) gives 1/(1 - rho[1]) for N = 2 and Eq. (5.54)
    gives 1/(1 - (4/3) rho[1] + (1/3) rho[2]) for N = 3. Both are asserted
    against this function in the oracle tests. See :func:`_clutter_residue` for
    how the denominator is evaluated, which is the whole difficulty.

    Returned as a linear ratio, with the small-spread limit

        I -> (2 / sigma_omega^2)^(N-1) / (N-1)!

    so perfectly stationary clutter (sigma_omega = 0) returns ``math.inf``:
    it is perfectly correlated pulse to pulse and cancels exactly. That is a
    documented limit of the model, not a bad input, and the caller is expected
    to cap it -- ``RadarModel`` does, via
    ``RadarDetectionScenario.mti_improvement_limit_db``. A design should not
    lean on the uncapped figure, which passes 200 dB for a narrow spectrum and
    a long canceller, far beyond the phase noise, transmitter stability and
    converter dynamic range this model does not represent.
    """
    if sigma_omega_rad < 0:
        raise ValueError("sigma_omega_rad must be >= 0")
    gain = mti_signal_gain(n_pulse)
    if sigma_omega_rad == 0.0:
        return math.inf
    residue = _clutter_residue(n_pulse, sigma_omega_rad)
    if residue <= 0:  # pragma: no cover - unreachable: the Gaussian kernel is PD
        raise ValueError("clutter residue is non-positive; sigma_omega out of valid range")
    return float(gain / residue)


def mti_target_gain(n_pulse: int, normalized_doppler_rad: float) -> float:
    """|H(omega_d)|^2, the canceller's power gain at a *known* target Doppler.

    :func:`mti_signal_gain` is the average over an unknown target velocity.
    When the velocity is known this is what the filter actually does to the
    target, and it falls to zero at the blind speeds, where the canceller nulls
    the target along with the clutter. ``normalized_doppler_rad`` is
    2 pi f_d / PRF.
    """
    weights = canceller_weights(n_pulse)
    real = math.fsum(w * math.cos(normalized_doppler_rad * k) for k, w in enumerate(weights))
    imag = math.fsum(w * math.sin(normalized_doppler_rad * k) for k, w in enumerate(weights))
    return float(real * real + imag * imag)


def mti_improvement_factor_at_doppler(
    n_pulse: int,
    sigma_omega_rad: float,
    normalized_doppler_rad: float,
) -> float:
    """Improvement factor against a target of known Doppler: |H(omega_d)|^2 / residue.

    :func:`mti_improvement_factor` credits the Doppler-averaged gain G, which
    is the right figure when the target velocity is unknown and badly wrong at
    a blind speed -- there the average says the canceller helps by G while the
    filter is actually nulling the target.
    """
    if sigma_omega_rad < 0:
        raise ValueError("sigma_omega_rad must be >= 0")
    gain = mti_target_gain(n_pulse, normalized_doppler_rad)
    if sigma_omega_rad == 0.0:
        return math.inf if gain > 0 else 0.0
    residue = _clutter_residue(n_pulse, sigma_omega_rad)
    if residue <= 0:  # pragma: no cover - unreachable: the Gaussian kernel is PD
        raise ValueError("clutter residue is non-positive; sigma_omega out of valid range")
    return float(gain / residue)


def mti_clutter_attenuation(n_pulse: int, sigma_omega_rad: float) -> float:
    """CA = I / G, the clutter power ratio across the filter (FRSP Eq. 5.43).

    Distinct from the improvement factor: this is rejection alone, with no
    credit for the filter's gain on the target.
    """
    return float(mti_improvement_factor(n_pulse, sigma_omega_rad) / mti_signal_gain(n_pulse))


def required_improvement_factor_db(
    target_rcs_dbsm: float,
    clutter_rcs_dbsm: float,
    required_scr_db: float,
) -> float:
    """I_req = (S/C)_required - (sigma_target - sigma_clutter), in dB.

    How far the signal-to-clutter ratio must be improved for the target to
    clear the required S/C. Positive means suppression is needed.

    This is a required *improvement factor*, and it must be judged against I,
    not against CA. It was named for clutter attenuation until v0.15.0, which
    put it a full signal gain G -- 3.0 dB for a two-pulse canceller, 7.8 dB for
    a three-pulse -- away from the quantity ``RadarModel`` actually credits to
    the SCR budget, so a canceller that met the requirement could be reported
    as falling short of it.
    """
    return float(required_scr_db - (target_rcs_dbsm - clutter_rcs_dbsm))


def required_clutter_attenuation_db(
    target_rcs_dbsm: float,
    clutter_rcs_dbsm: float,
    required_scr_db: float,
) -> float:
    """Deprecated alias for :func:`required_improvement_factor_db`.

    The old name described the returned quantity incorrectly; see that
    function. Kept for one release.
    """
    warnings.warn(
        "required_clutter_attenuation_db is deprecated: it returns a required "
        "improvement factor, not a required clutter attenuation, and must be "
        "compared against I rather than CA. Use required_improvement_factor_db.",
        DeprecationWarning,
        stacklevel=2,
    )
    return required_improvement_factor_db(target_rcs_dbsm, clutter_rcs_dbsm, required_scr_db)


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
