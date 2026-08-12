"""Golden oracle tests for the radar detection chain.

Every assertion here is pinned to a public, citable source or an
independent implementation, not to this codebase's own output:

- Albersheim's equation and its validity claim: M. A. Richards,
  "Alternative Forms of Albersheim's Equation" (2014) and *Fundamentals
  of Radar Signal Processing* ch. 6 (public excerpt), radarsp.weebly.com.
  Both fetched and read 2026-08-12.
- Exact detection statistics: independently recomputed with
  scipy.stats.ncx2 in this file (the noncentral-chi-square form of the
  square-law detector), never with this package's own functions.
- Swerling fluctuation behavior: P. Swerling, RAND RM-1217 (1954); the
  ~8 dB Swerling-1 fluctuation loss at Pd=0.9 is the standard figure
  (Richards ch. 6).
- Radar equation form: L. V. Blake, NRL Report 6930 (1969), via the
  R^-4 identity.

Measured finding preserved as a canary test: Albersheim's published
"<0.2 dB for Pd 0.1-0.9, Pfa 1e-3..1e-7" claim fails at its own joint
extreme corner (Pd=0.1, Pfa=1e-3), where the equation's inner term
A + 0.12AB + 1.7B collapses toward 1 and the estimate lands ~4 dB
below the exact requirement (verified against scipy independently).
"""

import math

import pytest
from scipy import optimize, stats

from phased_array_systems.architecture import Architecture, ArrayConfig, RFChainConfig
from phased_array_systems.models.radar.detection import (
    albersheim_snr,
    compute_detection_threshold,
    compute_pd_from_snr,
    compute_snr_for_pd,
)
from phased_array_systems.models.radar.equation import RadarModel
from phased_array_systems.scenarios import RadarDetectionScenario


def _independent_required_snr_db(pd: float, pfa: float) -> float:
    """SW0, N=1, square-law required SNR via scipy's noncentral chi-square.

    Pd = P(ncx2(2 dof, lambda=2*SNR) > 2*T) with T = -ln(Pfa). Shares no
    code with the package's detection module.
    """
    threshold = -math.log(pfa)

    def pd_at(snr_db: float) -> float:
        snr = 10 ** (snr_db / 10)
        return float(stats.ncx2.sf(2 * threshold, 2, 2 * snr))

    return float(optimize.brentq(lambda s: pd_at(s) - pd, -25.0, 35.0))


class TestAlbersheim:
    def test_richards_worked_example(self):
        """Richards ch. 6, sec. 6.4.3: Pd=0.9, Pfa=1e-6, N=1 gives
        A = ln(0.62e6) = 13.34, B = ln(9) = 2.197, chi_1 = 13.14 dB."""
        assert albersheim_snr(0.9, 1e-6, 1) == pytest.approx(13.14, abs=0.03)

    def test_implements_the_published_form(self):
        """A = ln(0.62/Pfa); B = ln(Pd/(1-Pd));
        chi_dB = -5 log10(N) + (6.2 + 4.54/sqrt(N+0.44)) log10(A + 0.12AB + 1.7B)
        (Richards, 'Alternative Forms of Albersheim's Equation', eq. 1)."""
        for pd, pfa, n in ((0.9, 1e-6, 1), (0.5, 1e-4, 10), (0.75, 1e-7, 100)):
            a = math.log(0.62 / pfa)
            b = math.log(pd / (1 - pd))
            expected = -5 * math.log10(n) + (6.2 + 4.54 / math.sqrt(n + 0.44)) * math.log10(
                a + 0.12 * a * b + 1.7 * b
            )
            assert albersheim_snr(pd, pfa, n) == pytest.approx(expected, abs=1e-12)

    def test_agreement_with_exact_in_operational_region(self):
        """Pd 0.5-0.9, Pfa 1e-3..1e-7, N to 512: measured worst deviation
        from the exact square-law statistics is 0.30 dB. Budget: 0.2 dB
        (Albersheim's claim, linear detector) + <=0.2 dB linear-vs-square
        detector difference (Richards). Frozen at 0.35 dB from measurement."""
        for pd in (0.5, 0.75, 0.9):
            for pfa in (1e-3, 1e-5, 1e-7):
                for n in (1, 4, 16, 64, 512):
                    exact = compute_snr_for_pd(pd, pfa, swerling=0, n_pulses=n)
                    assert albersheim_snr(pd, pfa, n) == pytest.approx(exact, abs=0.35)

    def test_breakdown_at_the_joint_extreme_corner(self):
        """Canary: at Pd=0.1, Pfa=1e-3 (both at the edge of the stated
        validity box) Albersheim's inner term collapses toward 1 and the
        estimate is ~4 dB low. The exact value is confirmed independently
        below, so this pins where NOT to trust the approximation."""
        exact = compute_snr_for_pd(0.1, 1e-3, swerling=0, n_pulses=1)
        assert exact == pytest.approx(_independent_required_snr_db(0.1, 1e-3), abs=0.01)
        assert exact - albersheim_snr(0.1, 1e-3, 1) > 3.0


class TestExactDetectionStatistics:
    def test_sw0_matches_independent_ncx2(self):
        """The package's exact solver vs an independent scipy noncentral
        chi-square implementation, across the Pd/Pfa plane (SW0, N=1)."""
        for pd in (0.1, 0.5, 0.9, 0.99):
            for pfa in (1e-3, 1e-6, 1e-9):
                ours = compute_snr_for_pd(pd, pfa, swerling=0, n_pulses=1)
                theirs = _independent_required_snr_db(pd, pfa)
                assert ours == pytest.approx(theirs, abs=0.01), (pd, pfa)

    def test_threshold_is_exact_for_single_sample(self):
        """N=1 square-law noise is exponential: threshold = -ln(Pfa)."""
        for pfa in (1e-3, 1e-6, 1e-9):
            assert compute_detection_threshold(pfa, 1) == pytest.approx(-math.log(pfa), rel=1e-8)

    def test_threshold_roundtrip_multi_sample(self):
        """P(chi2_2N/2 > T) = Pfa by construction (gamma survival)."""
        for n in (2, 8, 32):
            t = compute_detection_threshold(1e-6, n)
            pfa = float(stats.gamma.sf(t, a=n))
            assert pfa == pytest.approx(1e-6, rel=1e-6)


class TestSwerlingBehavior:
    def test_swerling1_fluctuation_loss_is_the_standard_8db(self):
        """At Pd=0.9, Pfa=1e-6, N=1 the Swerling-1 penalty over the
        nonfluctuating case is the textbook ~8 dB (measured: 7.96)."""
        s0 = compute_snr_for_pd(0.9, 1e-6, swerling=0, n_pulses=1)
        s1 = compute_snr_for_pd(0.9, 1e-6, swerling=1, n_pulses=1)
        assert s1 - s0 == pytest.approx(8.0, abs=0.5)

    def test_high_pd_ordering(self):
        """At high Pd fluctuation always costs SNR, and the one-dominant-
        scatterer models (3/4) cost less than the many-scatterer models
        (1/2): SW1 > SW3 > SW0 at N=1 (RM-1217)."""
        s0 = compute_snr_for_pd(0.9, 1e-6, swerling=0, n_pulses=1)
        s1 = compute_snr_for_pd(0.9, 1e-6, swerling=1, n_pulses=1)
        s3 = compute_snr_for_pd(0.9, 1e-6, swerling=3, n_pulses=1)
        assert s1 > s3 > s0

    def test_pulse_to_pulse_decorrelation_recovers_fluctuation_loss(self):
        """SW2 (pulse-to-pulse) integrates fluctuation away; SW1
        (scan-to-scan) cannot: SW2 needs much less SNR at N=16."""
        s1 = compute_snr_for_pd(0.9, 1e-6, swerling=1, n_pulses=16)
        s2 = compute_snr_for_pd(0.9, 1e-6, swerling=2, n_pulses=16)
        s3 = compute_snr_for_pd(0.9, 1e-6, swerling=3, n_pulses=16)
        s4 = compute_snr_for_pd(0.9, 1e-6, swerling=4, n_pulses=16)
        assert s2 < s1
        assert s4 < s3

    def test_pd_monotone_in_snr(self):
        pds = [compute_pd_from_snr(s, 1e-6, swerling=1, n_pulses=4) for s in range(0, 30, 3)]
        assert all(b > a for a, b in zip(pds, pds[1:], strict=False))


class TestRadarEquationForm:
    """Blake-form radar equation (NRL 6930): monostatic SNR follows R^-4."""

    def _metrics(self, range_m: float) -> dict:
        arch = Architecture(
            array=ArrayConfig(nx=16, ny=16, dx_lambda=0.5, dy_lambda=0.5),
            rf=RFChainConfig(tx_power_w_per_elem=1.0, noise_figure_db=3.0),
        )
        scenario = RadarDetectionScenario(
            freq_hz=10e9,
            bandwidth_hz=1e6,
            range_m=range_m,
            target_rcs_dbsm=0.0,
            pfa=1e-6,
            pd_required=0.9,
            include_atmos_loss=False,
            clutter_type="none",
            cfar_type="none",
        )
        return RadarModel().evaluate(arch, scenario, {"g_peak_db": 30.0})

    def test_snr_falls_12db_per_range_doubling(self):
        near = self._metrics(10e3)
        far = self._metrics(20e3)
        assert near["snr_single_pulse_db"] - far["snr_single_pulse_db"] == pytest.approx(
            40 * math.log10(2), abs=1e-6
        )
