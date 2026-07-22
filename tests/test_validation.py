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
