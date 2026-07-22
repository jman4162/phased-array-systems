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
