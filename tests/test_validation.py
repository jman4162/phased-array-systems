"""Validation against published reference values.

Each test asserts a model output against a value from its published
source (ITU-R Recommendation tables, textbook worked examples, or an
independent reference implementation), with the tolerance stated inline.
"""

import pytest

from phased_array_systems.models.propagation import (
    gaseous_attenuation_db_per_km,
    rain_k_alpha,
    rain_specific_attenuation_db_per_km,
)


class TestITUP676:
    """ITU-R P.676-13 line-by-line gaseous attenuation.

    References computed with ITU-Rpy 0.4 (independent implementation of
    P.676-13 exact model) at 1013.25 hPa, 15 C, 7.5 g/m^3. Tolerance 2%.
    """

    REFERENCES = {
        10.0: 0.014199,
        22.235: 0.192271,  # water vapour line
        60.0: 14.778317,  # oxygen complex peak
        94.0: 0.408129,  # W-band window
        118.75: 1.948928,  # oxygen line
        183.31: 28.020467,  # water vapour line
    }

    @pytest.mark.parametrize(("freq_ghz", "expected"), sorted(REFERENCES.items()))
    def test_reference_frequencies(self, freq_ghz, expected):
        gamma = gaseous_attenuation_db_per_km(
            freq_ghz, temperature_c=15.0, pressure_hpa=1013.25, water_vapor_g_m3=7.5
        )
        assert gamma == pytest.approx(expected, rel=0.02)

    def test_below_1ghz_is_zero(self):
        assert gaseous_attenuation_db_per_km(0.5) == 0.0

    def test_dry_air_removes_water_line(self):
        """With no water vapour, the 22 GHz line contribution vanishes."""
        wet = gaseous_attenuation_db_per_km(22.235, water_vapor_g_m3=7.5)
        dry = gaseous_attenuation_db_per_km(22.235, water_vapor_g_m3=0.0)
        assert dry < 0.2 * wet

    def test_pressure_scaling_monotone(self):
        """Away from lines, attenuation increases with pressure."""
        low = gaseous_attenuation_db_per_km(10.0, pressure_hpa=800.0)
        high = gaseous_attenuation_db_per_km(10.0, pressure_hpa=1013.25)
        assert high > low


class TestITUP838:
    """ITU-R P.838-3 rain coefficients vs the Recommendation's Table 5.

    Reference values cross-checked against ITU-Rpy's P.838-3
    implementation; regression reproduces the tables to ~1e-4.
    """

    TABLE = {
        # freq_ghz: (kH, alphaH, kV, alphaV)
        10.0: (0.01217, 1.2571, 0.01129, 1.2156),
        20.0: (0.09164, 1.0568, 0.09611, 0.9847),
        40.0: (0.44306, 0.8673, 0.42738, 0.8421),
        100.0: (1.36711, 0.6815, 1.36805, 0.6765),
    }

    @pytest.mark.parametrize(("freq_ghz", "expected"), sorted(TABLE.items()))
    def test_k_alpha_table_values(self, freq_ghz, expected):
        kh_ref, ah_ref, kv_ref, av_ref = expected
        kh, ah = rain_k_alpha(freq_ghz, "H")
        kv, av = rain_k_alpha(freq_ghz, "V")
        assert kh == pytest.approx(kh_ref, rel=1e-3)
        assert ah == pytest.approx(ah_ref, rel=1e-3)
        assert kv == pytest.approx(kv_ref, rel=1e-3)
        assert av == pytest.approx(av_ref, rel=1e-3)

    def test_specific_attenuation_20ghz_heavy_rain(self):
        """20 GHz, 42 mm/h, H-pol: gamma = kH * R^alphaH."""
        kh, ah = rain_k_alpha(20.0, "H")
        expected = kh * 42.0**ah
        got = rain_specific_attenuation_db_per_km(20.0, 42.0, "H")
        assert got == pytest.approx(expected, rel=1e-12)
        # Order of magnitude sanity: a few dB/km at Ka-band rain
        assert 3.0 < got < 8.0

    def test_out_of_range_raises(self):
        with pytest.raises(ValueError):
            rain_k_alpha(0.5)

    def test_zero_rain_is_zero(self):
        assert rain_specific_attenuation_db_per_km(20.0, 0.0) == 0.0


class TestFriisCascade:
    """Friis cascade vs the standard textbook 3-stage example."""

    def test_textbook_cascade(self):
        """Pozar-style chain: LNA (G=10 dB, F=1.5 dB) -> mixer (G=-3, F=6)
        -> IF amp (G=20, F=5). F = F1 + (F2-1)/G1 + (F3-1)/(G1 G2)."""
        from phased_array_systems.models.rf.cascade import friis_noise_figure

        result = friis_noise_figure([(10.0, 1.5), (-3.0, 6.0), (20.0, 5.0)])

        f1, f2, f3 = (10 ** (nf / 10) for nf in (1.5, 6.0, 5.0))
        g1, g2 = 10.0, 10 ** (-3 / 10)
        f_total = f1 + (f2 - 1) / g1 + (f3 - 1) / (g1 * g2)
        import math

        assert result["total_nf_db"] == pytest.approx(10 * math.log10(f_total), abs=1e-9)
        assert result["total_gain_db"] == pytest.approx(27.0)

    def test_contributions_sum_to_100(self):
        from phased_array_systems.models.rf.cascade import friis_noise_figure

        result = friis_noise_figure([(20.0, 1.5), (-7.0, 7.0), (30.0, 4.0)])
        assert sum(result["stage_contribution_pct"]) == pytest.approx(100.0, abs=1e-9)
        # First stage dominates when it has gain (Friis's point)
        assert result["stage_contribution_pct"][0] == max(result["stage_contribution_pct"])

    def test_nf_delta_is_positive_and_ordered(self):
        from phased_array_systems.models.rf.cascade import friis_noise_figure

        result = friis_noise_figure([(20.0, 1.5), (-7.0, 7.0), (30.0, 4.0)])
        deltas = result["stage_nf_delta_db"]
        assert all(d > 0 for d in deltas)
        assert deltas[0] == max(deltas)


class TestNoiseConvention:
    """T_sys = T_ant + T0*(F-1) system-noise composition."""

    def test_290k_matches_ktb_plus_nf(self):
        """At T_ant = 290 K the convention equals the old kTB + NF form."""
        import math

        from phased_array_systems.constants import K_B
        from phased_array_systems.models.comms.link_budget import compute_link_margin

        nf_db = 3.0
        result = compute_link_margin(
            eirp_dbw=40.0,
            path_loss_db=180.0,
            g_rx_db=30.0,
            noise_temp_k=290.0,
            bandwidth_hz=1e6,
            noise_figure_db=nf_db,
            required_snr_db=10.0,
        )
        old_form = 10 * math.log10(K_B * 290.0 * 1e6) + nf_db
        assert result["noise_power_dbw"] == pytest.approx(old_form, abs=1e-9)

    def test_low_sky_temp_satcom_case(self):
        """Textbook downlink: T_ant=60 K, NF=1 dB -> T_sys = 60+75.1 = 135.1 K.

        G/T-style budgets (e.g. Ippolito, 'Satellite Communications
        Systems Engineering') use exactly this composition; the old
        kTB+NF form would have used 60*F = 75.5 K equivalent, overstating
        SNR by ~2.5 dB.
        """
        from phased_array_systems.models.comms.link_budget import compute_link_margin

        result = compute_link_margin(
            eirp_dbw=50.0,
            path_loss_db=205.0,
            g_rx_db=40.0,
            noise_temp_k=60.0,
            bandwidth_hz=10e6,
            noise_figure_db=1.0,
            required_snr_db=10.0,
        )
        t_rx = 290.0 * (10 ** (1.0 / 10.0) - 1.0)  # 75.09 K
        assert result["noise_temp_system_k"] == pytest.approx(60.0 + t_rx, abs=0.01)


class TestCFARLoss:
    """CA-CFAR universal-curve loss (Gregers-Hansen; Richards ch. 16)."""

    def test_universal_curve_points(self):
        from phased_array_systems.models.radar.cfar import cfar_loss_db

        # Published universal curve: ~2.0 dB at N=16, ~0.95 dB at N=32
        # for Pfa = 1e-6
        assert cfar_loss_db("CA", 16, 1e-6) == pytest.approx(2.0, abs=0.1)
        assert cfar_loss_db("CA", 32, 1e-6) == pytest.approx(0.97, abs=0.1)

    def test_loss_decreases_with_cells(self):
        from phased_array_systems.models.radar.cfar import cfar_loss_db

        losses = [cfar_loss_db("CA", n, 1e-6) for n in [8, 16, 32, 64]]
        assert losses == sorted(losses, reverse=True)

    def test_loss_increases_with_lower_pfa(self):
        from phased_array_systems.models.radar.cfar import cfar_loss_db

        assert cfar_loss_db("CA", 16, 1e-8) > cfar_loss_db("CA", 16, 1e-4)

    def test_type_ordering(self):
        """SO > OS > GO > CA loss in homogeneous clutter."""
        from phased_array_systems.models.radar.cfar import cfar_loss_db

        ca = cfar_loss_db("CA", 16, 1e-6)
        go = cfar_loss_db("GO", 16, 1e-6)
        os_ = cfar_loss_db("OS", 16, 1e-6)
        so = cfar_loss_db("SO", 16, 1e-6)
        assert ca < go < os_ < so


class TestNRLSeaClutter:
    """NRL sea clutter model (Gregers-Hansen & Mittal, NRL/MR/5310-12-9346).

    Spot values computed from the published closed form (author's
    reference MATLAB implementation); the model itself fits the Nathanson
    tables within ~2.3 dB for 0.1-10 deg grazing.
    """

    def test_xband_ss3_low_grazing_spot(self):
        """9.3 GHz, SS3, 1 deg, HH: published-form value -43.83 dB."""
        from phased_array_systems.models.radar.clutter import sea_clutter_sigma0

        got = sea_clutter_sigma0(3, 1.0, 9.3e9, "HH")
        assert got == pytest.approx(-43.83, abs=0.05)
        # Nathanson X-band SS3 HH low-grazing values cluster near -45 dB
        assert -50.0 < got < -40.0

    def test_vv_exceeds_hh_at_low_grazing(self):
        from phased_array_systems.models.radar.clutter import sea_clutter_sigma0

        hh = sea_clutter_sigma0(3, 1.0, 9.3e9, "HH")
        vv = sea_clutter_sigma0(3, 1.0, 9.3e9, "VV")
        assert vv > hh

    def test_monotone_in_sea_state_and_grazing(self):
        from phased_array_systems.models.radar.clutter import sea_clutter_sigma0

        by_ss = [sea_clutter_sigma0(s, 1.0, 9.3e9) for s in range(7)]
        assert by_ss == sorted(by_ss)
        by_psi = [sea_clutter_sigma0(3, g, 9.3e9) for g in [0.1, 1.0, 10.0, 30.0]]
        assert by_psi == sorted(by_psi)


class TestConstantGammaGroundClutter:
    """Constant-gamma terrain model with Barton's published median gammas."""

    def test_sigma0_is_gamma_sin_psi(self):
        import math

        from phased_array_systems.models.radar.clutter import ground_clutter_sigma0

        got = ground_clutter_sigma0("rural", 5.0, 10e9)
        expected = -15.0 + 10 * math.log10(math.sin(math.radians(5.0)))
        assert got == pytest.approx(expected, abs=1e-9)

    def test_terrain_ordering(self):
        """Urban > forest > rural > wetland > desert reflectivity."""
        from phased_array_systems.models.radar.clutter import ground_clutter_sigma0

        vals = [
            ground_clutter_sigma0(t, 5.0, 10e9)
            for t in ["urban", "forest", "rural", "wetland", "desert"]
        ]
        assert vals == sorted(vals, reverse=True)
