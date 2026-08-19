"""Golden oracle tests for design-time track accuracy.

Every assertion is pinned to a public source or to an independent
implementation in this file, never to the package's own output:

- Richards, Scheer & Holm, *Principles of Modern Radar: Basic Principles*,
  SciTech 2010 (ISBN 9781891121524). Ch. 18 "Radar Measurements" and Ch. 19
  "Radar Tracking Algorithms" (W. D. Blair). Read locally 2026-08-18.
  Equations cited: (18.27) p. 689, (18.33)/(18.34) pp. 689-690, (18.55)
  p. 703, (18.63) p. 706, k_m = 1.6 p. 708, (19.47)-(19.56) pp. 731-732,
  (19.59)-(19.66) pp. 733-734, Figs. 19-14 and 19-15.
- Curry, *Radar System Performance Modeling*, 2nd ed., Artech House 2005
  (ISBN 1-58053-816-9), ch. 8 pp. 165-193. Worked examples at pp. 168 and
  pp. 170-171 are asserted directly.
- Mahafza, *Radar Systems Analysis and Design Using MATLAB*, Chapman &
  Hall/CRC ch. 11, Eq. (11.94).
- Kalata, IEEE Trans. AES-20(2) pp. 174-182, 1984,
  doi:10.1109/TAES.1984.310438, for the tracking index and the relation
  beta = 2(2 - alpha) - 4 sqrt(1 - alpha).

The strongest oracle here is ``_iterated_steady_state_covariance``: an
independent fixed-gain covariance recursion in Joseph form, iterated to
convergence, sharing no code with the package. It settles a genuine conflict
in the literature -- POMR Eq. (19.53) and Mahafza Eq. (11.94) disagree
numerically because they answer different questions (total error with process
noise, versus sensor-noise-only reduction). Both are reproduced below from the
same recursion, which is also the demonstration that omitting a recursive
filter costs nothing at steady state.
"""

import math

import pytest

from phased_array_systems.models.radar.tracking import (
    MONOPULSE_SNR_FLOOR_DB,
    alpha_beta_gains,
    angle_sigma_deg,
    combine_angle_errors_deg,
    crossrange_sigma_m,
    deterministic_tracking_index,
    maneuver_lag_m,
    process_noise_from_maneuver,
    range_resolution_m,
    range_sigma_m,
    scan_broadened_beamwidth_deg,
    steady_state_sigmas,
    tracking_index,
    variance_reduction_position,
    velocity_sigma_ms,
)


def _iterated_steady_state_covariance(alpha, beta, revisit_s, sigma_w, sigma_v, include_q):
    """Fixed-gain alpha-beta covariance recursion, Joseph form, to convergence.

    Independent of the package: builds F, Q, H, R and the constant gain
    K = [alpha, beta/T]^T directly and iterates

        P_pred = F P F' + Q
        P      = (I - K H) P_pred (I - K H)' + K R K'

    Q is the discrete white-noise-acceleration form of POMR Eq. (19.45).
    Pure-Python 2x2 arithmetic, no numpy, no package imports.
    """
    t = revisit_s
    f = ((1.0, t), (0.0, 1.0))
    g = (t * t / 2.0, t)
    q = (
        (
            ((sigma_v**2) * g[0] * g[0], (sigma_v**2) * g[0] * g[1]),
            ((sigma_v**2) * g[1] * g[0], (sigma_v**2) * g[1] * g[1]),
        )
        if include_q
        else ((0.0, 0.0), (0.0, 0.0))
    )
    k0, k1 = alpha, beta / t
    # I - K H  with H = [1 0]
    a = ((1.0 - k0, 0.0), (-k1, 1.0))
    r = sigma_w**2
    p = ((sigma_w**2, 0.0), (0.0, sigma_w**2))

    def mm(x, y):
        return (
            (x[0][0] * y[0][0] + x[0][1] * y[1][0], x[0][0] * y[0][1] + x[0][1] * y[1][1]),
            (x[1][0] * y[0][0] + x[1][1] * y[1][0], x[1][0] * y[0][1] + x[1][1] * y[1][1]),
        )

    def tr(x):
        return ((x[0][0], x[1][0]), (x[0][1], x[1][1]))

    for _ in range(500_000):
        pm = mm(mm(f, p), tr(f))
        pm = ((pm[0][0] + q[0][0], pm[0][1] + q[0][1]), (pm[1][0] + q[1][0], pm[1][1] + q[1][1]))
        joseph = mm(mm(a, pm), tr(a))
        krk = ((k0 * r * k0, k0 * r * k1), (k1 * r * k0, k1 * r * k1))
        new = (
            (joseph[0][0] + krk[0][0], joseph[0][1] + krk[0][1]),
            (joseph[1][0] + krk[1][0], joseph[1][1] + krk[1][1]),
        )
        scale = max(abs(p[i][j]) for i in (0, 1) for j in (0, 1)) or 1.0
        if max(abs(new[i][j] - p[i][j]) for i in (0, 1) for j in (0, 1)) < 1e-15 * scale:
            return new
        p = new
    raise AssertionError("covariance recursion did not converge")


class TestMeasurementAccuracy:
    """POMR ch. 18 and Curry ch. 8."""

    def test_range_resolution_identity(self):
        """dR = c/2B, POMR Eq. (18.34) with alpha = 1. B = 1 MHz gives 150 m
        (Curry p. 168 worked example)."""
        assert range_resolution_m(1e6) == pytest.approx(149.896, abs=0.2)

    def test_curry_range_worked_example(self):
        """Curry p. 168: B = 1 MHz, S/N = 15 dB gives sigma_RN = 18.9 m.

        sigma_R = dR/sqrt(2 S/N) = 149.9/sqrt(2*31.62) = 18.85 m.
        """
        assert range_sigma_m(15.0, 1e6) == pytest.approx(18.9, abs=0.1)

    def test_range_sigma_is_stated_fraction_of_resolution(self):
        """POMR p. 690 states the bound is 32% of rms resolution at SNR = 10 dB
        and 10% at 20 dB, on its SNR = 2E/N0 convention. On this package's S/N
        convention those are S/N = 7 dB and 17 dB."""
        assert range_sigma_m(7.0, 1e6) / range_resolution_m(1e6) == pytest.approx(0.32, abs=0.005)
        assert range_sigma_m(17.0, 1e6) / range_resolution_m(1e6) == pytest.approx(0.10, abs=0.005)

    def test_curry_angle_worked_example(self):
        """Curry pp. 170-171: theta = 1 deg, S/N = 12 dB gives sigma_AN = 1.9 mrad
        with k_m = 1.6."""
        sigma_mrad = math.radians(angle_sigma_deg(12.0, 1.0)) * 1e3
        assert sigma_mrad == pytest.approx(1.9, abs=0.05)

    def test_curry_scan_broadening_worked_example(self):
        """Curry p. 171: at phi = 30 deg a 1 deg beam becomes 1.15 deg and
        sigma_AN rises from 1.9 to 2.2 mrad."""
        broadened = scan_broadened_beamwidth_deg(1.0, 30.0)
        assert broadened == pytest.approx(1.15, abs=0.01)
        sigma_mrad = math.radians(angle_sigma_deg(12.0, broadened)) * 1e3
        assert sigma_mrad == pytest.approx(2.2, abs=0.05)

    def test_angle_sigma_near_beamsplit_rule_of_thumb(self):
        """POMR p. 703: an angle estimator can be expected to reach a precision
        on the order of theta_3dB/10. At a typical track S/N this lands in the
        beam-splitting band Curry quotes as 1/40 to 1/125 of a beamwidth
        (Curry p. 170)."""
        ratio = angle_sigma_deg(20.0, 1.0) / 1.0
        assert 1.0 / 125.0 < ratio < 1.0 / 10.0

    def test_crossrange_dominates_range_error(self):
        """The trade this model exists to expose: at 100 km, X-band, 20 dB S/N,
        10 MHz bandwidth and a 1 deg beam, cross-range error exceeds range error
        by more than an order of magnitude."""
        sigma_r = range_sigma_m(20.0, 10e6)
        sigma_c = crossrange_sigma_m(100e3, angle_sigma_deg(20.0, 1.0))
        assert sigma_c / sigma_r > 20.0

    def test_crossrange_scales_inversely_with_aperture(self):
        """theta_3dB ~ 0.886 lambda/(N d), so doubling the array halves the
        cross-range error at fixed SNR."""
        wide = crossrange_sigma_m(100e3, angle_sigma_deg(20.0, 2.0))
        narrow = crossrange_sigma_m(100e3, angle_sigma_deg(20.0, 1.0))
        assert wide / narrow == pytest.approx(2.0, rel=1e-12)

    def test_velocity_sigma_matches_hand_assembly(self):
        """Curry Eq. (8.13): sigma_V = lambda/(2 tau sqrt(2 S/N)), hand-computed
        at lambda = 0.03 m, tau = 10 ms, S/N = 20 dB."""
        expected = 0.03 / (2.0 * 10e-3 * math.sqrt(2.0 * 100.0))
        assert velocity_sigma_ms(20.0, 10e-3, 0.03) == pytest.approx(expected, rel=1e-12)

    def test_errors_combine_in_quadrature(self):
        assert combine_angle_errors_deg(0.03, 0.04) == pytest.approx(0.05, rel=1e-12)

    def test_monopulse_floor_is_recorded(self):
        """POMR Eq. (18.63) is derived for SNR > 13 dB; the constant must say so."""
        assert MONOPULSE_SNR_FLOOR_DB == 13.0

    @pytest.mark.parametrize("bad", [0.0, -1.0])
    def test_rejects_nonpositive_bandwidth(self, bad):
        with pytest.raises(ValueError):
            range_resolution_m(bad)


class TestTrackingIndexAndGains:
    """POMR ch. 19 sec. 19.2 / Kalata 1984."""

    def test_pomr_worked_example_page_734(self):
        """POMR p. 734: a target maneuvering at 40 m/s^2, measured at 1 Hz with
        sigma_w = 120 m, gives Gamma_D = 0.33; Eq. (19.66) then gives
        kappa_1_min = 0.91 and sigma_v = 36.4."""
        gamma_d = deterministic_tracking_index(40.0, 1.0, 120.0)
        assert gamma_d == pytest.approx(0.33, abs=0.005)
        sigma_v = process_noise_from_maneuver(gamma_d, 40.0)
        assert sigma_v / 40.0 == pytest.approx(0.91, abs=0.005)
        assert sigma_v == pytest.approx(36.4, abs=0.1)

    @pytest.mark.parametrize("gamma", [0.01, 0.1, 0.333, 1.0, 3.0, 10.0, 100.0])
    def test_kalata_relation_holds(self, gamma):
        """POMR Eq. (19.56): beta = 2(2 - alpha) - 4 sqrt(1 - alpha), an identity
        the gains of Eqs. (19.54)/(19.55) must satisfy exactly."""
        alpha, beta = alpha_beta_gains(gamma)
        assert beta == pytest.approx(2.0 * (2.0 - alpha) - 4.0 * math.sqrt(1.0 - alpha), rel=1e-12)

    @pytest.mark.parametrize("gamma", [0.01, 0.1, 0.333, 1.0, 3.0, 10.0, 100.0])
    def test_tracking_index_round_trips(self, gamma):
        """POMR Eq. (19.47) gives Gamma = beta/sqrt(1 - alpha); recovering the
        input index from the gains closes the loop."""
        alpha, beta = alpha_beta_gains(gamma)
        assert beta / math.sqrt(1.0 - alpha) == pytest.approx(gamma, rel=1e-10)

    @pytest.mark.parametrize("gamma", [0.01, 0.1, 1.0, 10.0, 100.0])
    def test_literal_pomr_gain_equations_agree(self, gamma):
        """Eqs. (19.54)/(19.55) written out literally must give the same gains as
        the rearrangement the module uses.

        Tolerance is budgeted from the literal form's own conditioning: it loses
        precision as alpha approaches 1 (measured 2e-12 relative at Gamma = 100),
        which is why the module does not use it directly.
        """
        root = math.sqrt(gamma**2 + 8.0 * gamma)
        alpha_lit = -(gamma**2) / 8.0 - gamma + (gamma + 4.0) / 8.0 * root
        beta_lit = gamma**2 / 4.0 + gamma - gamma / 4.0 * root
        alpha, beta = alpha_beta_gains(gamma)
        assert alpha == pytest.approx(alpha_lit, abs=1e-11)
        assert beta == pytest.approx(beta_lit, rel=1e-10)

    def test_unit_index_gives_exact_rational_gains(self):
        """Gamma = 1 lands on alpha = 3/4, beta = 1/2 exactly -- a memorable
        pin on Eqs. (19.54)/(19.55)."""
        alpha, beta = alpha_beta_gains(1.0)
        assert alpha == pytest.approx(0.75, rel=1e-12)
        assert beta == pytest.approx(0.50, rel=1e-12)

    def test_gains_approach_published_asymptotes(self):
        """POMR p. 732 and Fig. 19-14: alpha approaches 1 and beta approaches 2
        for large tracking index."""
        alpha, beta = alpha_beta_gains(1e4)
        assert alpha == pytest.approx(1.0, abs=1e-3)
        assert beta == pytest.approx(2.0, abs=1e-2)

    def test_gains_increase_with_index(self):
        """A more maneuverable target relative to sensor noise must be tracked
        with heavier weight on the measurement."""
        gains = [alpha_beta_gains(g) for g in (0.1, 1.0, 10.0)]
        assert [g[0] for g in gains] == sorted(g[0] for g in gains)
        assert [g[1] for g in gains] == sorted(g[1] for g in gains)

    def test_index_definition(self):
        """Gamma = sigma_v T^2 / sigma_w, POMR Eq. (19.47)."""
        assert tracking_index(2.0, 8.0, 2.0) == pytest.approx(1.0, rel=1e-12)


class TestSteadyStateCovariance:
    """The independent-recursion oracle, and the literature conflict it settles."""

    @pytest.mark.parametrize("gamma", [0.01, 0.1, 0.333, 1.0, 3.0, 10.0])
    def test_pomr_covariance_matches_iterated_recursion(self, gamma):
        """POMR Eq. (19.53) must equal the fixed-gain covariance recursion
        iterated to convergence with process noise present."""
        sigma_w, revisit = 1.0, 1.0
        alpha, beta = alpha_beta_gains(gamma)
        sigma_v = gamma * sigma_w / revisit**2
        pos, vel = steady_state_sigmas(sigma_w, alpha, beta, revisit)
        p = _iterated_steady_state_covariance(alpha, beta, revisit, sigma_w, sigma_v, True)
        assert pos**2 == pytest.approx(p[0][0], rel=1e-9)
        assert vel**2 == pytest.approx(p[1][1], rel=1e-7)

    @pytest.mark.parametrize("gamma", [0.01, 0.1, 0.333, 1.0, 3.0, 10.0])
    def test_mahafza_vrr_matches_noise_only_recursion(self, gamma):
        """Mahafza Eq. (11.94) must equal the same recursion with Q = 0.

        This is the resolution of the apparent conflict with POMR Eq. (19.53):
        the two formulas describe different quantities, and each reproduces its
        own recursion exactly.
        """
        sigma_w, revisit = 1.0, 1.0
        alpha, beta = alpha_beta_gains(gamma)
        p = _iterated_steady_state_covariance(alpha, beta, revisit, sigma_w, 0.0, False)
        assert variance_reduction_position(alpha, beta) == pytest.approx(p[0][0], rel=1e-9)

    @pytest.mark.parametrize("gamma", [0.1, 1.0, 10.0])
    def test_the_two_forms_genuinely_differ(self, gamma):
        """Guard against the two being silently conflated in future edits: the
        total error always exceeds the sensor-noise-only figure."""
        alpha, beta = alpha_beta_gains(gamma)
        pos, _ = steady_state_sigmas(1.0, alpha, beta, 1.0)
        assert pos**2 > variance_reduction_position(alpha, beta)

    def test_position_covariance_is_exactly_alpha(self):
        """POMR Eq. (19.53) top-left entry is sigma_w^2 alpha, which is why the
        published form is so much simpler than the general alpha-beta result."""
        alpha, beta = alpha_beta_gains(1.0)
        pos, _ = steady_state_sigmas(3.0, alpha, beta, 1.0)
        assert pos == pytest.approx(3.0 * math.sqrt(alpha), rel=1e-12)

    def test_filtering_beats_the_raw_measurement(self):
        """A track must be no worse than the measurement that feeds it."""
        for gamma in (0.01, 0.1, 1.0):
            alpha, beta = alpha_beta_gains(gamma)
            pos, _ = steady_state_sigmas(10.0, alpha, beta, 1.0)
            assert pos < 10.0

    def test_wrong_literature_form_is_rejected(self):
        """Canary. The circulating variant (2a^2 + 2b + ab)/(a(4 - 2a - b))
        exceeds unity, i.e. claims filtering amplifies noise. Assert the package
        does not implement it."""
        alpha, beta = alpha_beta_gains(10.0)
        bad = (2 * alpha**2 + 2 * beta + alpha * beta) / (alpha * (4 - 2 * alpha - beta))
        assert bad > 1.0
        assert variance_reduction_position(alpha, beta) < 1.0

    def test_faster_revisit_improves_velocity_estimate(self):
        """Velocity accuracy scales as 1/T at fixed gains."""
        alpha, beta = alpha_beta_gains(1.0)
        _, slow = steady_state_sigmas(1.0, alpha, beta, 2.0)
        _, fast = steady_state_sigmas(1.0, alpha, beta, 1.0)
        assert fast == pytest.approx(slow * 2.0, rel=1e-12)


class TestManeuverLag:
    def test_lag_grows_with_deterministic_index(self):
        """POMR Eq. (19.60): the maneuver term (1-alpha)^2 Gamma_D^2/beta^2 grows
        without bound as the target out-maneuvers the filter."""
        alpha, beta = alpha_beta_gains(1.0)
        quiet = maneuver_lag_m(100.0, alpha, beta, 0.1)
        hard = maneuver_lag_m(100.0, alpha, beta, 5.0)
        assert hard > quiet

    def test_lag_reduces_to_noise_term_without_maneuver(self):
        """With Gamma_D = 0 the MMSE collapses to the sensor-noise term."""
        alpha, beta = alpha_beta_gains(1.0)
        denom = alpha * (4.0 - 2.0 * alpha - beta)
        expected = 100.0 * math.sqrt((2 * alpha**2 + beta * (2 - 3 * alpha)) / denom)
        assert maneuver_lag_m(100.0, alpha, beta, 0.0) == pytest.approx(expected, rel=1e-12)
