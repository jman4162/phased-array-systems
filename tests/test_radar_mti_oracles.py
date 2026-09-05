"""Golden oracle tests for MTI clutter suppression.

Sources, all public:

- M. A. Richards, *Fundamentals of Radar Signal Processing*. Clutter
  attenuation Eq. (5.43); average signal gain over Doppler p. 246; Gaussian
  clutter autocorrelation Eq. (5.53); two- and three-pulse improvement factor
  closed forms Eqs. (5.52)/(5.54) p. 247. The same text this package already
  cites for CA-CFAR loss and Albersheim's equation.
- M. I. Skolnik, *Introduction to Radar Systems*, ch. 15, for sigma_c = 2
  sigma_v / lambda and the frequency independence of the velocity spread.
- N. Levanon, *Radar Principles*, Wiley, 1988, for I = (S/C)_out / (S/C)_in.

The package computes the improvement factor from the general quadratic form
over binomial canceller weights, never from the closed forms. The closed forms
are written out independently here and asserted against it, so the two- and
three-pulse cases are pinned to their published expressions while the general
form remains free to handle N > 3.

A complete worked system is carried through as an end-to-end case: the ARSR-3
L-band air traffic control radar (1.3 GHz, PRF 400 Hz, 2 us pulse, 1.25 deg
azimuth beamwidth, wooded-hill clutter at sigma0 = -20 dB, clutter velocity
spread 1.16 km/hr, 2 m^2 target at 30 nmi, 15 dB required S/C). Its published
intermediate values -- 3637 m^2 clutter RCS, 47.6 dB required attenuation,
30.2 dB and 57.3 dB improvement factors -- are asserted individually, which
also gives the existing clutter model its first worked-case test.
"""

import math

import pytest

from phased_array_systems.models.radar.clutter import (
    compute_resolution_cell_area,
    compute_scr,
)
from phased_array_systems.models.radar.mti import (
    SERIES_MAX_U,
    _clutter_residue,
    blind_speed_ms,
    canceller_autocorrelation,
    canceller_weights,
    clutter_autocorrelation,
    clutter_spectral_std_hz,
    doppler_shift_hz,
    mti_clutter_attenuation,
    mti_improvement_factor,
    mti_improvement_factor_at_doppler,
    mti_signal_gain,
    mti_target_gain,
    normalized_clutter_spread_rad,
    required_clutter_attenuation_db,
    required_improvement_factor_db,
    unambiguous_range_m,
)

# ARSR-3 system parameters.
FREQ_HZ = 1.3e9
WAVELENGTH_M = 299792458.0 / FREQ_HZ  # 0.2306 m
PRF_HZ = 400.0
PULSE_WIDTH_S = 2e-6
AZ_BEAMWIDTH_DEG = 1.25
CLUTTER_SIGMA0_DB = -20.0
CLUTTER_VELOCITY_STD_MS = 1.16 * 1000.0 / 3600.0  # 1.16 km/hr
TARGET_RCS_DBSM = 3.0  # 2 m^2
TARGET_RANGE_M = 55.56e3  # 30 nmi
REQUIRED_SCR_DB = 15.0


def _sigma_omega() -> float:
    return normalized_clutter_spread_rad(
        clutter_spectral_std_hz(CLUTTER_VELOCITY_STD_MS, WAVELENGTH_M), PRF_HZ
    )


def _closed_form_two_pulse(sigma_omega: float) -> float:
    """FRSP Eq. (5.52): I = 1/(1 - rho[1]). Written out independently.

    The denominator sums to zero at sigma_omega = 0, so it is evaluated with
    ``expm1`` -- the identical formula, without the cancellation. Written
    literally as ``1 - exp(-s^2/2)`` this oracle carries a relative error of
    1.0e-10 at sigma_omega = 0.001, which is larger than the tolerance the
    test asserts: it would fail the package for being *more* accurate than the
    check. See :func:`test_naive_closed_forms_are_the_less_accurate_side`.
    """
    return -1.0 / math.expm1(-(sigma_omega**2) / 2.0)


def _closed_form_three_pulse(sigma_omega: float) -> float:
    """FRSP Eq. (5.54): I = 1/(1 - (4/3) rho[1] + (1/3) rho[2]).

    Same treatment as the two-pulse form: the coefficients 1 - 4/3 + 1/3 sum
    to zero, so the denominator is rewritten over rho[k] - 1 = expm1(...).
    """
    return 1.0 / (
        -(4.0 / 3.0) * math.expm1(-(sigma_omega**2) / 2.0)
        + (1.0 / 3.0) * math.expm1(-2.0 * sigma_omega**2)
    )


def _naive_closed_form_two_pulse(sigma_omega: float) -> float:
    """Eq. (5.52) transcribed literally, for the conditioning test only."""
    return 1.0 / (1.0 - math.exp(-(sigma_omega**2) / 2.0))


def _naive_closed_form_three_pulse(sigma_omega: float) -> float:
    """Eq. (5.54) transcribed literally, for the conditioning test only.

    Returns infinity once the denominator underflows to zero, which it does
    below sigma_omega ~ 1e-3.
    """
    denom = (
        1.0
        - (4.0 / 3.0) * math.exp(-(sigma_omega**2) / 2.0)
        + (1.0 / 3.0) * math.exp(-2.0 * sigma_omega**2)
    )
    return math.inf if denom == 0.0 else 1.0 / denom


class TestClutterSpectrum:
    def test_velocity_to_frequency_spread(self):
        """Skolnik ch. 15: sigma_c = 2 sigma_v / lambda. At 1.3 GHz a
        1.16 km/hr spread gives 2.79 Hz."""
        assert clutter_spectral_std_hz(CLUTTER_VELOCITY_STD_MS, WAVELENGTH_M) == pytest.approx(
            2.79, abs=0.01
        )

    def test_normalized_spread(self):
        """2.79 Hz against a 400 Hz PRF normalizes to 6.98e-3, or
        sigma_omega = 0.0438 rad."""
        sigma_c = clutter_spectral_std_hz(CLUTTER_VELOCITY_STD_MS, WAVELENGTH_M)
        assert sigma_c / PRF_HZ == pytest.approx(6.98e-3, abs=0.01e-3)
        assert normalized_clutter_spread_rad(sigma_c, PRF_HZ) == pytest.approx(0.0438, abs=0.0002)

    def test_spread_is_frequency_dependent_in_hz(self):
        """The velocity spread is a clutter property, so the same scatterers
        produce a wider Doppler spectrum at higher frequency."""
        low = clutter_spectral_std_hz(0.32, 299792458.0 / 1.3e9)
        high = clutter_spectral_std_hz(0.32, 299792458.0 / 10e9)
        assert high > low
        assert high / low == pytest.approx(10e9 / 1.3e9, rel=1e-12)

    def test_autocorrelation_is_unity_at_zero_lag(self):
        assert clutter_autocorrelation(0.0438, 0) == pytest.approx(1.0, rel=1e-15)

    def test_autocorrelation_decays_with_lag(self):
        vals = [clutter_autocorrelation(0.5, k) for k in range(4)]
        assert vals == sorted(vals, reverse=True)


class TestCancellerStructure:
    def test_two_pulse_weights(self):
        """The conventional two-pulse canceller is [1, -1]."""
        assert canceller_weights(2) == [1, -1]

    def test_three_pulse_weights(self):
        """The conventional three-pulse canceller is [1, -2, 1]."""
        assert canceller_weights(3) == [1, -2, 1]

    def test_weights_sum_to_zero(self):
        """A difference canceller must reject DC exactly, or stationary clutter
        survives it."""
        for n in range(2, 8):
            assert sum(canceller_weights(n)) == 0

    @pytest.mark.parametrize("n_pulse,gain", [(2, 2.0), (3, 6.0)])
    def test_published_signal_gains(self, n_pulse, gain):
        """Richards FRSP p. 247: G = 2 (3 dB) for the two-pulse canceller and
        G = 6 (7.8 dB) for the three-pulse."""
        assert mti_signal_gain(n_pulse) == pytest.approx(gain, rel=1e-12)

    def test_three_pulse_gain_in_db(self):
        assert 10 * math.log10(mti_signal_gain(3)) == pytest.approx(7.8, abs=0.05)

    def test_rejects_single_pulse(self):
        with pytest.raises(ValueError):
            canceller_weights(1)


class TestImprovementFactorAgainstClosedForms:
    """The general quadratic form must reproduce the published closed forms."""

    @pytest.mark.parametrize("sigma_omega", [0.001, 0.01, 0.0438, 0.1, 0.3, 1.0])
    def test_two_pulse_matches_frsp_5_52(self, sigma_omega):
        assert mti_improvement_factor(2, sigma_omega) == pytest.approx(
            _closed_form_two_pulse(sigma_omega), rel=1e-10
        )

    @pytest.mark.parametrize("sigma_omega", [0.01, 0.0438, 0.1, 0.3])
    def test_three_pulse_matches_frsp_5_54(self, sigma_omega):
        """Both sides are now evaluated without cancellation, so the tolerance
        measures the package rather than the oracle's own rounding. The old
        budget of 5e-8 was set by writing Eq. (5.54) out literally, where a
        difference of terms all near 1 costs eight digits at sigma_omega =
        0.01; that is a property of the transcription, not of either model.
        """
        assert mti_improvement_factor(3, sigma_omega) == pytest.approx(
            _closed_form_three_pulse(sigma_omega), rel=1e-10
        )

    @pytest.mark.parametrize("sigma_omega", [1e-4, 1e-3, 1e-2])
    def test_naive_closed_forms_are_the_less_accurate_side(self, sigma_omega):
        """Canary for the tolerances above, and for the module's own claim.

        The published closed forms are exact algebra written in a form that
        cancels, so transcribing them literally is what loses the digits. The
        package's value is the reference here: it is machine-accurate against
        150-digit arithmetic across N = 2..8 and sigma_omega = 1e-8..5, which
        neither closed form is. If someone restores the literal transcription
        into the oracles above, their tight tolerances start failing the
        package for being right.

        The three-pulse case is the blunt one: below sigma_omega ~ 1e-3 the
        literal denominator 1 - (4/3)rho[1] + (1/3)rho[2] underflows to
        exactly zero and the textbook formula returns infinity.
        """
        two_ref = mti_improvement_factor(2, sigma_omega)
        assert abs(_closed_form_two_pulse(sigma_omega) - two_ref) / two_ref < 1e-15
        naive_two_err = abs(_naive_closed_form_two_pulse(sigma_omega) - two_ref) / two_ref
        assert naive_two_err > 1e-13

        # Three tiers, and the middle one is why the package does not simply
        # use expm1 everywhere: rewriting Eq. (5.54) over rho[k] - 1 removes
        # the leading cancellation but not the next order, so it still decays
        # as 1/sigma_omega^2 (8.7e-9 here at 1e-4) where the package's series
        # is exact. The literal form is not on the scale at all.
        three_ref = mti_improvement_factor(3, sigma_omega)
        expm1_err = abs(_closed_form_three_pulse(sigma_omega) - three_ref) / three_ref
        assert expm1_err < 1e-7
        naive_three = _naive_closed_form_three_pulse(sigma_omega)
        naive_err = (
            math.inf if math.isinf(naive_three) else abs(naive_three - three_ref) / three_ref
        )
        assert naive_err > 10.0 * expm1_err

    def test_improvement_is_gain_times_attenuation(self):
        """Levanon's definition I = G * CA must hold identically."""
        for n in (2, 3, 4):
            i_factor = mti_improvement_factor(n, 0.0438)
            assert i_factor == pytest.approx(
                mti_signal_gain(n) * mti_clutter_attenuation(n, 0.0438), rel=1e-12
            )

    def test_more_pulses_improve_rejection(self):
        factors = [mti_improvement_factor(n, 0.0438) for n in (2, 3, 4, 5)]
        assert factors == sorted(factors)

    def test_wider_clutter_spectrum_degrades_rejection(self):
        """A canceller nulls DC; clutter that spreads away from DC survives."""
        factors = [mti_improvement_factor(3, s) for s in (0.01, 0.05, 0.2, 0.5)]
        assert factors == sorted(factors, reverse=True)


class TestARSR3WorkedCase:
    """End-to-end verification against a fully worked L-band ATC radar."""

    def test_unambiguous_range(self):
        """PRF 400 Hz gives R_ua = c/2PRF = 375 km."""
        assert unambiguous_range_m(PRF_HZ) == pytest.approx(375e3, rel=0.001)

    def test_first_blind_speed_exceeds_target_doppler_band(self):
        """The first null sits at F = PRF = 400 Hz, above the anticipated 50-350
        Hz target Doppler band, so no wanted target is cancelled."""
        assert doppler_shift_hz(blind_speed_ms(PRF_HZ, WAVELENGTH_M), WAVELENGTH_M) == (
            pytest.approx(PRF_HZ, rel=1e-12)
        )
        assert doppler_shift_hz(blind_speed_ms(PRF_HZ, WAVELENGTH_M), WAVELENGTH_M) > 350.0

    def test_clutter_rcs_from_resolution_cell(self):
        """A_c = R theta_az (c tau / 2); with sigma0 = -20 dB this gives
        3637 m^2 = 35.6 dBsm. First worked-case test of the clutter model."""
        range_resolution = 299792458.0 * PULSE_WIDTH_S / 2.0
        area = compute_resolution_cell_area(TARGET_RANGE_M, range_resolution, AZ_BEAMWIDTH_DEG)
        clutter_rcs = area * 10 ** (CLUTTER_SIGMA0_DB / 10)
        assert clutter_rcs == pytest.approx(3637.0, rel=0.005)
        assert 10 * math.log10(clutter_rcs) == pytest.approx(35.6, abs=0.05)

    def test_required_improvement_factor(self):
        """I_req = 15 - (3 - 35.6) = 47.6 dB.

        Judged against I, which is what RadarModel credits to the SCR budget.
        Quoting this figure against CA -- which the docs and example 08 did
        until v0.15.0 -- puts the verdict a full signal gain G out.
        """
        assert required_improvement_factor_db(
            TARGET_RCS_DBSM, 35.6, REQUIRED_SCR_DB
        ) == pytest.approx(47.6, abs=0.05)

    def test_deprecated_alias_still_works(self):
        with pytest.warns(DeprecationWarning, match="required_improvement_factor_db"):
            assert required_clutter_attenuation_db(
                TARGET_RCS_DBSM, 35.6, REQUIRED_SCR_DB
            ) == pytest.approx(47.6, abs=0.05)

    def test_required_attenuation_agrees_with_scr_helper(self):
        """Cross-check against the existing clutter model's SCR: the shortfall
        below the required S/C is the attenuation needed."""
        scr_db = compute_scr(TARGET_RCS_DBSM, 35.6)
        assert REQUIRED_SCR_DB - scr_db == pytest.approx(47.6, abs=0.05)

    def test_two_pulse_canceller_falls_short(self):
        """I = 30.2 dB, G = 3 dB, so CA = 27.2 dB, below the 47.6 dB needed."""
        sigma_omega = _sigma_omega()
        i_db = 10 * math.log10(mti_improvement_factor(2, sigma_omega))
        ca_db = 10 * math.log10(mti_clutter_attenuation(2, sigma_omega))
        assert i_db == pytest.approx(30.2, abs=0.1)
        assert ca_db == pytest.approx(27.2, abs=0.1)
        assert ca_db < 47.6

    def test_three_pulse_canceller_meets_requirement(self):
        """I = 57.3 dB, G = 7.8 dB, CA = 49.5 dB > 47.6 dB. The three-pulse
        canceller is the smallest binomial canceller that suffices."""
        sigma_omega = _sigma_omega()
        i_db = 10 * math.log10(mti_improvement_factor(3, sigma_omega))
        ca_db = 10 * math.log10(mti_clutter_attenuation(3, sigma_omega))
        assert i_db == pytest.approx(57.3, abs=0.1)
        assert ca_db == pytest.approx(49.5, abs=0.1)
        assert ca_db > 47.6


class TestResidueConditioning:
    """The denominator of I, which is where every digit was being lost.

    Written literally, sum_i sum_j w_i w_j rho[i-j] is a difference of terms of
    magnitude C(2N-2, N-1) whose value is O(sigma_omega^(2N-2)). These pin the
    rearrangements that removed the cancellation.
    """

    @pytest.mark.parametrize("n_pulse", [2, 3, 4, 5, 6, 8])
    def test_series_and_lag_forms_agree_across_the_switchover(self, n_pulse):
        """The branch point is measured, not tuned: both forms are accurate in
        a band around u = sigma_omega (N-1) = SERIES_MAX_U, and this is what
        says so. Anyone who retunes the constant has to keep it inside that
        band."""
        sigma_omega = SERIES_MAX_U / (n_pulse - 1)
        below = _clutter_residue(n_pulse, sigma_omega * (1 - 1e-12))
        above = _clutter_residue(n_pulse, sigma_omega * (1 + 1e-12))
        assert abs(above - below) / abs(below) < 1e-9

    @pytest.mark.parametrize("n_pulse", [2, 3, 4, 5])
    @pytest.mark.parametrize("sigma_omega", [1e-4, 1e-3, 1e-2])
    def test_narrow_spectrum_matches_the_asymptote(self, n_pulse, sigma_omega):
        """I -> (2/sigma_omega^2)^(N-1) / (N-1)! as the spectrum narrows.

        Follows from S_{N-1} being the first non-vanishing moment. The
        quadratic form reached 100% error and a spurious "residue is
        non-positive" ValueError over this whole region.
        """
        asymptote = (2.0 / sigma_omega**2) ** (n_pulse - 1) / math.factorial(n_pulse - 1)
        # The asymptote is the leading term only; the next one is O(sigma^2),
        # so the budget has to carry it. Measured coefficients are 0.25, 0.83,
        # 1.75 and 3.0 for N = 2..5, all comfortably under N^2.
        assert mti_improvement_factor(n_pulse, sigma_omega) == pytest.approx(
            asymptote, rel=n_pulse**2 * sigma_omega**2
        )

    @pytest.mark.parametrize("n_pulse", [2, 3, 4, 5])
    def test_deviation_from_the_asymptote_is_second_order(self, n_pulse):
        """Sharper than the tolerance above: the gap between I and its
        small-spread limit must fall as sigma_omega^2 exactly, which is what
        says the limit is the right one rather than merely close."""

        def gap(sigma_omega: float) -> float:
            asymptote = (2.0 / sigma_omega**2) ** (n_pulse - 1) / math.factorial(n_pulse - 1)
            return abs(mti_improvement_factor(n_pulse, sigma_omega) - asymptote) / asymptote

        assert gap(1e-3) / gap(1e-4) == pytest.approx(100.0, rel=1e-3)

    @pytest.mark.parametrize("sigma_omega", [1e-4, 1e-3, 1e-2, 0.0438])
    def test_longer_cancellers_always_reject_more(self, sigma_omega):
        """The invariant test_more_pulses_improve_rejection asserts, over the
        clutter spreads where it used to break: at sigma_omega ~ 2e-4 the old
        form returned a *smaller* improvement for N = 5 than for N = 4."""
        factors = [mti_improvement_factor(n, sigma_omega) for n in (2, 3, 4, 5, 6)]
        assert factors == sorted(factors)

    def test_weight_autocorrelation_sums_to_zero(self):
        """sum_d a_d = (sum_k w_k)^2 = 0 is the identity both rearrangements
        rest on. Exact in integer arithmetic, and it is what makes the
        (N-1)-order DC null available to the series."""
        for n in range(2, 9):
            a = canceller_autocorrelation(n)
            assert a[0] + 2 * sum(a[1:]) == 0
            assert a[0] == mti_signal_gain(n)


class TestStationaryClutterAndCeiling:
    def test_perfectly_stationary_clutter_is_perfectly_cancelled(self):
        """sigma_omega = 0 is a documented limit of the model, not a bad
        input: clutter that is perfectly correlated pulse to pulse cancels
        exactly. It used to raise, which killed any DOE sweeping
        clutter_velocity_std_ms down to its own lower bound."""
        assert mti_improvement_factor(3, 0.0) == math.inf
        assert mti_clutter_attenuation(3, 0.0) == math.inf

    def test_negative_spread_is_still_rejected(self):
        with pytest.raises(ValueError):
            mti_improvement_factor(3, -1e-6)


class TestTargetDopplerResponse:
    def test_gain_vanishes_at_the_blind_speeds(self):
        """A target advancing a full cycle per pulse is indistinguishable from
        stationary clutter and is cancelled with it."""
        for n in (2, 3, 4):
            for harmonic in (1, 2):
                assert mti_target_gain(n, 2 * math.pi * harmonic) == pytest.approx(0.0, abs=1e-20)

    def test_averaged_gain_is_recovered_over_a_doppler_sweep(self):
        """mti_signal_gain is the mean of |H|^2 over the unambiguous band
        (Parseval), so a fine sweep must average to it."""
        for n in (2, 3, 4):
            samples = 4096
            mean = (
                sum(mti_target_gain(n, 2 * math.pi * k / samples) for k in range(samples)) / samples
            )
            assert mean == pytest.approx(mti_signal_gain(n), rel=1e-9)

    def test_blind_target_gets_no_improvement(self):
        """The averaged figure credits G at a blind speed, where the filter is
        actually nulling the target. Nothing in the metrics dict could catch
        that before."""
        sigma_omega = _sigma_omega()
        averaged = mti_improvement_factor(2, sigma_omega)
        at_blind = mti_improvement_factor_at_doppler(2, sigma_omega, 2 * math.pi)
        assert at_blind == pytest.approx(0.0, abs=1e-12)
        assert averaged > 1000.0

    def test_optimally_placed_target_beats_the_average(self):
        """At half the blind speed the two-pulse canceller doubles the target
        power relative to its Doppler average."""
        sigma_omega = _sigma_omega()
        assert mti_improvement_factor_at_doppler(2, sigma_omega, math.pi) == pytest.approx(
            2.0 * mti_improvement_factor(2, sigma_omega), rel=1e-9
        )
