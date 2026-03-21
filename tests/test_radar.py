"""Tests for radar detection models."""

import pytest

from phased_array_systems.architecture import Architecture, ArrayConfig, RFChainConfig
from phased_array_systems.evaluate import evaluate_case
from phased_array_systems.models.radar import (
    RadarModel,
    albersheim_snr,
    atmospheric_attenuation_db_per_km,
    atmospheric_loss_db,
    ca_cfar_threshold_factor,
    cfar_loss_db,
    coherent_integration_gain,
    compute_detection_threshold,
    compute_pd_from_snr,
    compute_resolution_cell_area,
    compute_scnr,
    compute_scr,
    compute_snr_for_pd,
    go_cfar_threshold_factor,
    ground_clutter_rcs,
    ground_clutter_sigma0,
    noncoherent_integration_gain,
    os_cfar_threshold_factor,
    radar_horizon_km,
    rain_attenuation_db,
    rain_attenuation_rate,
    rain_clutter_rcs,
    sea_clutter_rcs,
    sea_clutter_sigma0,
)
from phased_array_systems.models.radar.integration import binary_integration_gain, integration_loss
from phased_array_systems.scenarios import RadarDetectionScenario


class TestDetectionThreshold:
    """Tests for detection threshold calculation."""

    def test_threshold_increases_with_lower_pfa(self):
        """Higher threshold needed for lower Pfa."""
        thresh_high_pfa = compute_detection_threshold(1e-3)
        thresh_low_pfa = compute_detection_threshold(1e-9)
        assert thresh_low_pfa > thresh_high_pfa

    def test_threshold_invalid_pfa(self):
        """Test invalid Pfa raises error."""
        with pytest.raises(ValueError):
            compute_detection_threshold(0)
        with pytest.raises(ValueError):
            compute_detection_threshold(1)
        with pytest.raises(ValueError):
            compute_detection_threshold(-0.1)

    def test_threshold_positive(self):
        """Threshold should always be positive."""
        for pfa in [1e-3, 1e-6, 1e-9]:
            threshold = compute_detection_threshold(pfa)
            assert threshold > 0


class TestAlbersheimSNR:
    """Tests for Albersheim's equation."""

    def test_typical_values(self):
        """Test Albersheim for typical Pd/Pfa."""
        snr = albersheim_snr(pd=0.9, pfa=1e-6, n_pulses=1)
        # Should be around 13-14 dB for single pulse
        assert 12 < snr < 16

    def test_snr_increases_with_pd(self):
        """Higher Pd requires higher SNR."""
        snr_90 = albersheim_snr(pd=0.9, pfa=1e-6)
        snr_99 = albersheim_snr(pd=0.99, pfa=1e-6)
        assert snr_99 > snr_90

    def test_snr_increases_with_lower_pfa(self):
        """Lower Pfa requires higher SNR."""
        snr_high_pfa = albersheim_snr(pd=0.9, pfa=1e-3)
        snr_low_pfa = albersheim_snr(pd=0.9, pfa=1e-9)
        assert snr_low_pfa > snr_high_pfa

    def test_snr_decreases_with_pulses(self):
        """More pulses reduce required SNR."""
        snr_1 = albersheim_snr(pd=0.9, pfa=1e-6, n_pulses=1)
        snr_10 = albersheim_snr(pd=0.9, pfa=1e-6, n_pulses=10)
        assert snr_10 < snr_1

    def test_invalid_pd_raises(self):
        """Test invalid Pd raises error."""
        with pytest.raises(ValueError):
            albersheim_snr(pd=0.05, pfa=1e-6)  # Too low
        with pytest.raises(ValueError):
            albersheim_snr(pd=1.0, pfa=1e-6)  # Too high


class TestPdFromSNR:
    """Tests for Pd calculation from SNR."""

    def test_pd_increases_with_snr(self):
        """Pd increases with higher SNR."""
        pd_low = compute_pd_from_snr(5.0, pfa=1e-6)
        pd_high = compute_pd_from_snr(20.0, pfa=1e-6)
        assert pd_high > pd_low

    def test_pd_in_valid_range(self):
        """Pd should be between 0 and 1."""
        for snr in [-10, 0, 10, 20, 30]:
            pd = compute_pd_from_snr(snr, pfa=1e-6)
            assert 0 <= pd <= 1

    def test_high_snr_gives_high_pd(self):
        """Very high SNR should give Pd close to 1."""
        pd = compute_pd_from_snr(30.0, pfa=1e-6)
        assert pd > 0.99

    def test_very_low_snr_gives_low_pd(self):
        """Very low SNR should give low Pd."""
        pd = compute_pd_from_snr(-10.0, pfa=1e-6)
        assert pd < 0.5


class TestSNRForPd:
    """Tests for required SNR calculation."""

    def test_round_trip_consistency(self):
        """compute_snr_for_pd should invert compute_pd_from_snr."""
        target_pd = 0.9
        snr = compute_snr_for_pd(pd=target_pd, pfa=1e-6)
        pd_check = compute_pd_from_snr(snr, pfa=1e-6)
        assert pd_check == pytest.approx(target_pd, rel=0.1)

    def test_snr_increases_with_pd(self):
        """Higher Pd requires higher SNR."""
        snr_50 = compute_snr_for_pd(pd=0.5, pfa=1e-6)
        snr_90 = compute_snr_for_pd(pd=0.9, pfa=1e-6)
        assert snr_90 > snr_50


class TestIntegrationGain:
    """Tests for integration gain calculations."""

    def test_coherent_single_pulse(self):
        """Single pulse has 0 dB gain."""
        gain = coherent_integration_gain(1)
        assert gain == 0.0

    def test_coherent_gain_formula(self):
        """Coherent gain is 10*log10(n)."""
        gain_10 = coherent_integration_gain(10)
        assert gain_10 == pytest.approx(10.0)

        gain_100 = coherent_integration_gain(100)
        assert gain_100 == pytest.approx(20.0)

    def test_noncoherent_less_than_coherent(self):
        """Non-coherent gain is less than coherent."""
        n = 16
        coh = coherent_integration_gain(n)
        noncoh = noncoherent_integration_gain(n)
        assert noncoh < coh

    def test_noncoherent_positive(self):
        """Non-coherent gain is still positive."""
        gain = noncoherent_integration_gain(10)
        assert gain > 0

    def test_integration_loss_coherent_zero(self):
        """Coherent integration has no loss."""
        loss = integration_loss(10, "coherent")
        assert loss == 0.0

    def test_integration_loss_noncoherent_positive(self):
        """Non-coherent integration has positive loss."""
        loss = integration_loss(10, "noncoherent")
        assert loss > 0

    def test_invalid_n_pulses(self):
        """Invalid n_pulses raises error."""
        with pytest.raises(ValueError):
            coherent_integration_gain(0)
        with pytest.raises(ValueError):
            noncoherent_integration_gain(0)

    def test_binary_integration(self):
        """Test M-of-N binary integration."""
        gain = binary_integration_gain(10, 5)
        assert gain > 0
        assert gain < coherent_integration_gain(10)


class TestRadarModel:
    """Tests for the RadarModel class."""

    @pytest.fixture
    def sample_architecture(self):
        """Create sample architecture for tests."""
        return Architecture(
            array=ArrayConfig(nx=16, ny=16),
            rf=RFChainConfig(tx_power_w_per_elem=10.0, pa_efficiency=0.3),
        )

    @pytest.fixture
    def sample_scenario(self):
        """Create sample radar scenario."""
        return RadarDetectionScenario(
            freq_hz=10e9,
            bandwidth_hz=1e6,
            range_m=50e3,
            target_rcs_dbsm=0.0,  # 1 m^2
            pfa=1e-6,
            pd_required=0.9,
            n_pulses=10,
            integration_type="noncoherent",
        )

    def test_model_creation(self):
        """Test model can be created."""
        model = RadarModel()
        assert model.name == "radar"

    def test_basic_evaluation(self, sample_architecture, sample_scenario):
        """Test basic radar evaluation returns expected metrics."""
        model = RadarModel()
        metrics = model.evaluate(sample_architecture, sample_scenario, {})

        # Check all expected metrics are present
        assert "snr_single_pulse_db" in metrics
        assert "snr_integrated_db" in metrics
        assert "snr_required_db" in metrics
        assert "snr_margin_db" in metrics
        assert "pd_achieved" in metrics
        assert "detection_range_m" in metrics
        assert "peak_power_w" in metrics
        assert "g_ant_db" in metrics

    def test_integration_gain_applied(self, sample_architecture, sample_scenario):
        """Test that integration gain is applied to SNR."""
        model = RadarModel()
        metrics = model.evaluate(sample_architecture, sample_scenario, {})

        # Integrated SNR should be higher than single pulse
        assert metrics["snr_integrated_db"] > metrics["snr_single_pulse_db"]

        # Integration gain should be positive
        assert metrics["integration_gain_db"] > 0

    def test_peak_power_calculation(self, sample_architecture, sample_scenario):
        """Test peak power calculation."""
        model = RadarModel()
        metrics = model.evaluate(sample_architecture, sample_scenario, {})

        # 256 elements * 10W = 2560W
        assert metrics["peak_power_w"] == pytest.approx(2560.0)

    def test_snr_margin_consistency(self, sample_architecture, sample_scenario):
        """Test SNR margin is difference of integrated and required."""
        model = RadarModel()
        metrics = model.evaluate(sample_architecture, sample_scenario, {})

        expected_margin = metrics["snr_integrated_db"] - metrics["snr_required_db"]
        assert metrics["snr_margin_db"] == pytest.approx(expected_margin)

    def test_detection_range_positive(self, sample_architecture, sample_scenario):
        """Test detection range is positive."""
        model = RadarModel()
        metrics = model.evaluate(sample_architecture, sample_scenario, {})

        assert metrics["detection_range_m"] > 0

    def test_coherent_integration(self, sample_architecture):
        """Test coherent integration gives higher gain."""
        scenario_coh = RadarDetectionScenario(
            freq_hz=10e9,
            bandwidth_hz=1e6,
            range_m=50e3,
            target_rcs_dbsm=0.0,
            n_pulses=10,
            integration_type="coherent",
        )
        scenario_noncoh = RadarDetectionScenario(
            freq_hz=10e9,
            bandwidth_hz=1e6,
            range_m=50e3,
            target_rcs_dbsm=0.0,
            n_pulses=10,
            integration_type="noncoherent",
        )

        model = RadarModel()
        metrics_coh = model.evaluate(sample_architecture, scenario_coh, {})
        metrics_noncoh = model.evaluate(sample_architecture, scenario_noncoh, {})

        assert metrics_coh["integration_gain_db"] > metrics_noncoh["integration_gain_db"]

    def test_with_antenna_context(self, sample_architecture, sample_scenario):
        """Test that antenna gain from context is used."""
        model = RadarModel()

        # Without context - uses approximate gain
        metrics_no_ctx = model.evaluate(sample_architecture, sample_scenario, {})

        # With context - uses provided gain
        context = {"g_peak_db": 30.0}
        metrics_with_ctx = model.evaluate(sample_architecture, sample_scenario, context)

        # SNR should differ due to different gain
        assert metrics_with_ctx["g_ant_db"] == 30.0
        assert metrics_with_ctx["snr_single_pulse_db"] != metrics_no_ctx["snr_single_pulse_db"]


class TestRadarScenario:
    """Tests for RadarDetectionScenario."""

    def test_wavelength_property(self):
        """Test wavelength calculation."""
        scenario = RadarDetectionScenario(
            freq_hz=10e9,
            bandwidth_hz=1e6,
            range_m=100e3,
            target_rcs_dbsm=0.0,
        )
        # c / 10e9 ≈ 0.03m
        assert scenario.wavelength_m == pytest.approx(0.03, rel=1e-3)

    def test_rcs_m2_property(self):
        """Test RCS conversion to m^2."""
        scenario = RadarDetectionScenario(
            freq_hz=10e9,
            bandwidth_hz=1e6,
            range_m=100e3,
            target_rcs_dbsm=10.0,  # 10 dBsm = 10 m^2
        )
        assert scenario.target_rcs_m2 == pytest.approx(10.0)

    def test_default_values(self):
        """Test default scenario values."""
        scenario = RadarDetectionScenario(
            freq_hz=10e9,
            bandwidth_hz=1e6,
            range_m=100e3,
            target_rcs_dbsm=0.0,
        )
        assert scenario.pfa == 1e-6
        assert scenario.pd_required == 0.9
        assert scenario.n_pulses == 1
        assert scenario.integration_type == "noncoherent"
        assert scenario.rx_noise_temp_k == 290.0


class TestFullEvaluation:
    """Test full evaluation pipeline with radar scenario."""

    def test_evaluate_case_radar(self):
        """Test evaluate_case with radar scenario."""
        arch = Architecture(
            array=ArrayConfig(nx=16, ny=16),
            rf=RFChainConfig(tx_power_w_per_elem=10.0),
        )
        scenario = RadarDetectionScenario(
            freq_hz=10e9,
            bandwidth_hz=1e6,
            range_m=50e3,
            target_rcs_dbsm=0.0,
            n_pulses=10,
        )

        metrics = evaluate_case(arch, scenario)

        # Should have radar metrics
        assert "snr_margin_db" in metrics
        assert "detection_range_m" in metrics

        # Should have antenna metrics
        assert "g_peak_db" in metrics

        # Should have SWaP-C metrics
        assert "cost_usd" in metrics
        assert "prime_power_w" in metrics

        # No meta.warning (radar is implemented)
        assert "meta.warning" not in metrics


class TestSeaClutter:
    """Tests for sea clutter models."""

    def test_sea_clutter_sigma0_increases_with_sea_state(self):
        """Higher sea state gives higher clutter."""
        sigma0_ss2 = sea_clutter_sigma0(2, 5.0, 10e9)
        sigma0_ss5 = sea_clutter_sigma0(5, 5.0, 10e9)
        assert sigma0_ss5 > sigma0_ss2

    def test_sea_clutter_sigma0_grazing_angle_dependence(self):
        """Sigma-0 increases with grazing angle."""
        sigma0_low = sea_clutter_sigma0(3, 1.0, 10e9)
        sigma0_high = sea_clutter_sigma0(3, 30.0, 10e9)
        assert sigma0_high > sigma0_low

    def test_sea_clutter_sigma0_polarization(self):
        """VV typically higher than HH at low grazing angles."""
        sigma0_hh = sea_clutter_sigma0(3, 2.0, 10e9, "HH")
        sigma0_vv = sea_clutter_sigma0(3, 2.0, 10e9, "VV")
        # VV should be higher at low grazing angles
        assert sigma0_vv > sigma0_hh

    def test_sea_clutter_rcs_includes_cell_area(self):
        """Clutter RCS scales with resolution cell area."""
        sea_clutter_sigma0(3, 5.0, 10e9)
        rcs_small = sea_clutter_rcs(3, 5.0, 10e9, 100.0)
        rcs_large = sea_clutter_rcs(3, 5.0, 10e9, 1000.0)
        # 10x larger cell should give ~10 dB more clutter
        assert rcs_large == pytest.approx(rcs_small + 10.0, abs=0.1)

    def test_sea_clutter_invalid_sea_state(self):
        """Invalid sea state raises error."""
        with pytest.raises(ValueError):
            sea_clutter_sigma0(-1, 5.0, 10e9)
        with pytest.raises(ValueError):
            sea_clutter_sigma0(7, 5.0, 10e9)

    def test_sea_clutter_invalid_grazing_angle(self):
        """Invalid grazing angle raises error."""
        with pytest.raises(ValueError):
            sea_clutter_sigma0(3, 0.0, 10e9)
        with pytest.raises(ValueError):
            sea_clutter_sigma0(3, 91.0, 10e9)


class TestGroundClutter:
    """Tests for ground clutter models."""

    def test_ground_clutter_terrain_differences(self):
        """Different terrains have different sigma-0."""
        sigma0_rural = ground_clutter_sigma0("rural", 10.0, 10e9)
        sigma0_urban = ground_clutter_sigma0("urban", 10.0, 10e9)
        sigma0_desert = ground_clutter_sigma0("desert", 10.0, 10e9)

        # Urban should be highest, desert lowest
        assert sigma0_urban > sigma0_rural
        assert sigma0_rural > sigma0_desert

    def test_ground_clutter_grazing_angle(self):
        """Sigma-0 increases with grazing angle."""
        sigma0_low = ground_clutter_sigma0("rural", 1.0, 10e9)
        sigma0_high = ground_clutter_sigma0("rural", 45.0, 10e9)
        assert sigma0_high > sigma0_low

    def test_ground_clutter_rcs_cell_scaling(self):
        """Ground clutter RCS scales with cell area."""
        rcs_100 = ground_clutter_rcs("rural", 10.0, 10e9, 100.0)
        rcs_1000 = ground_clutter_rcs("rural", 10.0, 10e9, 1000.0)
        assert rcs_1000 == pytest.approx(rcs_100 + 10.0, abs=0.1)


class TestRainClutter:
    """Tests for rain clutter models."""

    def test_rain_clutter_increases_with_rate(self):
        """Higher rain rate gives higher clutter."""
        rcs_light = rain_clutter_rcs(1.0, 10e9, 1e6)
        rcs_heavy = rain_clutter_rcs(25.0, 10e9, 1e6)
        assert rcs_heavy > rcs_light

    def test_rain_clutter_zero_rate(self):
        """Zero rain rate gives negligible clutter."""
        rcs = rain_clutter_rcs(0.0, 10e9, 1e6)
        assert rcs < -30  # Very low (returns -40 for zero rain)

    def test_rain_clutter_frequency_dependence(self):
        """Rain clutter increases with frequency."""
        rcs_10ghz = rain_clutter_rcs(10.0, 10e9, 1e6)
        rcs_35ghz = rain_clutter_rcs(10.0, 35e9, 1e6)
        assert rcs_35ghz > rcs_10ghz


class TestSCR:
    """Tests for signal-to-clutter ratio calculations."""

    def test_scr_basic(self):
        """SCR is target RCS minus clutter RCS."""
        scr = compute_scr(10.0, 5.0)
        assert scr == 5.0

    def test_scr_negative_when_clutter_dominates(self):
        """SCR is negative when clutter exceeds target."""
        scr = compute_scr(0.0, 10.0)
        assert scr == -10.0

    def test_scnr_lower_than_snr_and_scr(self):
        """SCNR should be lower than both SNR and SCR."""
        snr = 20.0
        scr = 15.0
        scnr = compute_scnr(snr, scr)
        assert scnr < snr
        assert scnr < scr

    def test_scnr_approaches_lower_value(self):
        """SCNR approaches whichever is lower."""
        # When SCR >> SNR, SCNR ≈ SNR
        scnr = compute_scnr(10.0, 100.0)
        assert scnr == pytest.approx(10.0, abs=0.5)

        # When SNR >> SCR, SCNR ≈ SCR
        scnr = compute_scnr(100.0, 10.0)
        assert scnr == pytest.approx(10.0, abs=0.5)


class TestResolutionCell:
    """Tests for resolution cell calculations."""

    def test_cell_area_calculation(self):
        """Test resolution cell area calculation."""
        area = compute_resolution_cell_area(
            range_m=100e3,  # 100 km
            range_resolution_m=150.0,  # 150 m
            azimuth_beamwidth_deg=2.0,  # 2 degrees
        )
        # Cross-range at 100 km with 2 deg beamwidth ≈ 3490 m
        # Area ≈ 150 * 3490 ≈ 523500 m^2
        assert 400000 < area < 600000


class TestAtmosphericPropagation:
    """Tests for atmospheric propagation models."""

    def test_atmos_atten_increases_with_frequency(self):
        """Atmospheric attenuation increases with frequency."""
        atten_3ghz = atmospheric_attenuation_db_per_km(3e9)
        atten_60ghz = atmospheric_attenuation_db_per_km(60e9)
        assert atten_60ghz > atten_3ghz

    def test_atmos_atten_low_at_low_freq(self):
        """Attenuation is very low below 1 GHz."""
        atten = atmospheric_attenuation_db_per_km(0.5e9)
        assert atten == 0.0

    def test_atmos_loss_two_way(self):
        """Atmospheric loss is two-way for radar."""
        rate = atmospheric_attenuation_db_per_km(10e9)
        loss = atmospheric_loss_db(10e9, 100e3)  # 100 km
        # Two-way loss should be approximately 2 * rate * range_km
        expected = 2 * rate * 100
        assert loss == pytest.approx(expected, rel=0.3)


class TestRainAttenuation:
    """Tests for rain attenuation models."""

    def test_rain_atten_increases_with_rate(self):
        """Rain attenuation increases with rain rate."""
        atten_light = rain_attenuation_rate(10e9, 1.0)
        atten_heavy = rain_attenuation_rate(10e9, 50.0)
        assert atten_heavy > atten_light

    def test_rain_atten_increases_with_frequency(self):
        """Rain attenuation increases with frequency."""
        atten_10ghz = rain_attenuation_rate(10e9, 10.0)
        atten_35ghz = rain_attenuation_rate(35e9, 10.0)
        assert atten_35ghz > atten_10ghz

    def test_rain_atten_zero_for_no_rain(self):
        """No rain means no attenuation."""
        atten = rain_attenuation_rate(10e9, 0.0)
        assert atten == 0.0

    def test_rain_loss_two_way(self):
        """Rain loss is computed two-way."""
        loss = rain_attenuation_db(10e9, 50e3, 10.0)
        assert loss > 0


class TestRadarHorizon:
    """Tests for radar horizon calculations."""

    def test_horizon_increases_with_height(self):
        """Higher antenna means longer horizon."""
        horizon_10m = radar_horizon_km(10.0)
        horizon_100m = radar_horizon_km(100.0)
        assert horizon_100m > horizon_10m

    def test_horizon_with_target_height(self):
        """Target height extends horizon."""
        horizon_surface = radar_horizon_km(30.0, 0.0)
        horizon_aircraft = radar_horizon_km(30.0, 10000.0)
        assert horizon_aircraft > horizon_surface

    def test_horizon_typical_values(self):
        """Test typical radar horizon values."""
        # 30m antenna should see ~20 km to surface target
        horizon = radar_horizon_km(30.0, 0.0)
        assert 15 < horizon < 30


class TestCFAR:
    """Tests for CFAR detection algorithms."""

    def test_ca_cfar_threshold_increases_with_lower_pfa(self):
        """Lower Pfa requires higher threshold factor."""
        alpha_high_pfa = ca_cfar_threshold_factor(16, 1e-3)
        alpha_low_pfa = ca_cfar_threshold_factor(16, 1e-9)
        assert alpha_low_pfa > alpha_high_pfa

    def test_ca_cfar_threshold_decreases_with_more_cells(self):
        """More reference cells means lower threshold factor needed."""
        alpha_8 = ca_cfar_threshold_factor(8, 1e-6)
        alpha_32 = ca_cfar_threshold_factor(32, 1e-6)
        assert alpha_32 < alpha_8

    def test_ca_cfar_invalid_params(self):
        """Invalid parameters raise errors."""
        with pytest.raises(ValueError):
            ca_cfar_threshold_factor(1, 1e-6)  # Need at least 2 cells
        with pytest.raises(ValueError):
            ca_cfar_threshold_factor(16, 0)  # Invalid Pfa
        with pytest.raises(ValueError):
            ca_cfar_threshold_factor(16, 1)  # Invalid Pfa

    def test_os_cfar_threshold(self):
        """OS-CFAR threshold calculation."""
        alpha = os_cfar_threshold_factor(16, 12, 1e-6)
        assert alpha > 0

    def test_go_cfar_threshold(self):
        """GO-CFAR threshold calculation."""
        alpha = go_cfar_threshold_factor(8, 1e-6)
        assert alpha > 0

    def test_cfar_loss_decreases_with_cells(self):
        """CFAR loss decreases with more reference cells."""
        loss_8 = cfar_loss_db("CA", 8)
        loss_32 = cfar_loss_db("CA", 32)
        assert loss_32 < loss_8

    def test_cfar_loss_positive(self):
        """CFAR always has some loss."""
        for cfar_type in ["CA", "OS", "GO", "SO"]:
            loss = cfar_loss_db(cfar_type, 16)
            assert loss > 0


class TestRadarModelWithClutter:
    """Tests for RadarModel with clutter and propagation."""

    @pytest.fixture
    def sample_architecture(self):
        """Create sample architecture for tests."""
        return Architecture(
            array=ArrayConfig(nx=16, ny=16),
            rf=RFChainConfig(tx_power_w_per_elem=10.0, pa_efficiency=0.3),
        )

    def test_sea_clutter_scenario(self, sample_architecture):
        """Test radar model with sea clutter."""
        scenario = RadarDetectionScenario(
            freq_hz=10e9,
            bandwidth_hz=10e6,
            range_m=50e3,
            target_rcs_dbsm=10.0,
            clutter_type="sea",
            sea_state=4,
            grazing_angle_deg=5.0,
            n_pulses=16,
        )

        model = RadarModel()
        metrics = model.evaluate(sample_architecture, scenario, {"beamwidth_az_deg": 3.0})

        # Should have clutter metrics
        assert metrics["clutter_type"] == "sea"
        assert metrics["clutter_rcs_dbsm"] > -100  # Not default
        assert metrics["scr_db"] < 100  # Not default infinite
        assert "scnr_db" in metrics

    def test_ground_clutter_scenario(self, sample_architecture):
        """Test radar model with ground clutter."""
        scenario = RadarDetectionScenario(
            freq_hz=10e9,
            bandwidth_hz=10e6,
            range_m=30e3,
            target_rcs_dbsm=5.0,
            clutter_type="ground",
            terrain_type="urban",
            grazing_angle_deg=10.0,
        )

        model = RadarModel()
        metrics = model.evaluate(sample_architecture, scenario, {})

        assert metrics["clutter_type"] == "ground"
        assert metrics["clutter_rcs_dbsm"] > -100

    def test_rain_clutter_scenario(self, sample_architecture):
        """Test radar model with rain clutter and attenuation."""
        scenario = RadarDetectionScenario(
            freq_hz=35e9,  # Ka-band
            bandwidth_hz=10e6,
            range_m=20e3,
            target_rcs_dbsm=10.0,
            clutter_type="rain",
            rain_rate_mm_hr=25.0,  # Heavy rain
        )

        model = RadarModel()
        metrics = model.evaluate(sample_architecture, scenario, {})

        assert metrics["clutter_type"] == "rain"
        assert metrics["rain_loss_db"] > 0

    def test_atmospheric_loss(self, sample_architecture):
        """Test atmospheric loss is included when enabled."""
        scenario_no_atmos = RadarDetectionScenario(
            freq_hz=60e9,  # V-band (high atmos absorption)
            bandwidth_hz=1e6,
            range_m=10e3,
            target_rcs_dbsm=0.0,
            include_atmos_loss=False,
        )
        scenario_with_atmos = RadarDetectionScenario(
            freq_hz=60e9,
            bandwidth_hz=1e6,
            range_m=10e3,
            target_rcs_dbsm=0.0,
            include_atmos_loss=True,
        )

        model = RadarModel()
        metrics_no_atmos = model.evaluate(sample_architecture, scenario_no_atmos, {})
        metrics_with_atmos = model.evaluate(sample_architecture, scenario_with_atmos, {})

        assert metrics_no_atmos["atmos_loss_db"] == 0.0
        assert metrics_with_atmos["atmos_loss_db"] > 0.0
        assert metrics_with_atmos["snr_single_pulse_db"] < metrics_no_atmos["snr_single_pulse_db"]

    def test_cfar_loss_included(self, sample_architecture):
        """Test CFAR loss is included when enabled."""
        scenario_no_cfar = RadarDetectionScenario(
            freq_hz=10e9,
            bandwidth_hz=1e6,
            range_m=50e3,
            target_rcs_dbsm=0.0,
            cfar_type="none",
        )
        scenario_with_cfar = RadarDetectionScenario(
            freq_hz=10e9,
            bandwidth_hz=1e6,
            range_m=50e3,
            target_rcs_dbsm=0.0,
            cfar_type="CA",
            cfar_ref_cells=16,
        )

        model = RadarModel()
        metrics_no_cfar = model.evaluate(sample_architecture, scenario_no_cfar, {})
        metrics_with_cfar = model.evaluate(sample_architecture, scenario_with_cfar, {})

        assert metrics_no_cfar["cfar_loss_db"] == 0.0
        assert metrics_with_cfar["cfar_loss_db"] > 0.0
        assert metrics_with_cfar["snr_integrated_db"] < metrics_no_cfar["snr_integrated_db"]

    def test_clutter_reduces_detection_range(self, sample_architecture):
        """Clutter should reduce detection range."""
        scenario_no_clutter = RadarDetectionScenario(
            freq_hz=10e9,
            bandwidth_hz=10e6,
            range_m=50e3,
            target_rcs_dbsm=10.0,
            clutter_type="none",
            n_pulses=16,
        )
        scenario_with_clutter = RadarDetectionScenario(
            freq_hz=10e9,
            bandwidth_hz=10e6,
            range_m=50e3,
            target_rcs_dbsm=10.0,
            clutter_type="sea",
            sea_state=5,
            grazing_angle_deg=3.0,
            n_pulses=16,
        )

        model = RadarModel()
        metrics_no_clutter = model.evaluate(
            sample_architecture, scenario_no_clutter, {"beamwidth_az_deg": 3.0}
        )
        metrics_with_clutter = model.evaluate(
            sample_architecture, scenario_with_clutter, {"beamwidth_az_deg": 3.0}
        )

        # With clutter, SNR margin and detection range should be lower
        assert metrics_with_clutter["snr_margin_db"] < metrics_no_clutter["snr_margin_db"]

    def test_new_scenario_fields_defaults(self):
        """Test new scenario fields have correct defaults."""
        scenario = RadarDetectionScenario(
            freq_hz=10e9,
            bandwidth_hz=1e6,
            range_m=50e3,
            target_rcs_dbsm=0.0,
        )

        # Check defaults
        assert scenario.clutter_type == "none"
        assert scenario.sea_state == 3
        assert scenario.terrain_type == "rural"
        assert scenario.rain_rate_mm_hr == 0.0
        assert scenario.polarization == "HH"
        assert scenario.cfar_type == "none"
        assert scenario.include_atmos_loss is False

    def test_range_resolution_property(self):
        """Test range resolution computed property."""
        scenario = RadarDetectionScenario(
            freq_hz=10e9,
            bandwidth_hz=10e6,  # 10 MHz
            range_m=50e3,
            target_rcs_dbsm=0.0,
        )
        # c / (2 * 10e6) = 15 m
        assert scenario.range_resolution_m == pytest.approx(15.0, rel=0.01)
