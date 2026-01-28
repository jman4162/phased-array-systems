"""Tests for radar detection models."""

import pytest

from phased_array_systems.architecture import Architecture, ArrayConfig, RFChainConfig
from phased_array_systems.evaluate import evaluate_case
from phased_array_systems.models.radar import (
    RadarModel,
    albersheim_snr,
    coherent_integration_gain,
    compute_detection_threshold,
    compute_pd_from_snr,
    compute_snr_for_pd,
    noncoherent_integration_gain,
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
