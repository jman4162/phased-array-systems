"""Tests for the single-case evaluator."""

import pytest

from phased_array_systems.architecture import (
    Architecture,
    ArrayConfig,
    CostConfig,
    DigitalConfig,
    ReliabilityConfig,
    RFChainConfig,
)
from phased_array_systems.evaluate import (
    evaluate_case,
    evaluate_case_with_report,
)
from phased_array_systems.requirements import Requirement, RequirementSet
from phased_array_systems.scenarios import CommsLinkScenario


class TestEvaluateCase:
    """Tests for the evaluate_case function."""

    @pytest.fixture
    def sample_architecture(self):
        return Architecture(
            array=ArrayConfig(nx=8, ny=8, dx_lambda=0.5, dy_lambda=0.5),
            rf=RFChainConfig(
                tx_power_w_per_elem=1.0,
                pa_efficiency=0.3,
                noise_figure_db=3.0,
                feed_loss_db=1.0,
            ),
            cost=CostConfig(
                cost_per_elem_usd=100.0,
                nre_usd=10000.0,
            ),
        )

    @pytest.fixture
    def sample_scenario(self):
        return CommsLinkScenario(
            freq_hz=10e9,
            bandwidth_hz=10e6,
            range_m=100e3,
            required_snr_db=10.0,
            scan_angle_deg=0.0,
        )

    @pytest.fixture
    def sample_requirements(self):
        return RequirementSet(
            requirements=[
                Requirement(
                    id="REQ-001",
                    name="Min EIRP",
                    metric_key="eirp_dbw",
                    op=">=",
                    value=30.0,
                    severity="must",
                ),
                Requirement(
                    id="REQ-002",
                    name="Max Cost",
                    metric_key="cost_usd",
                    op="<=",
                    value=50000.0,
                    severity="must",
                ),
            ]
        )

    def test_basic_evaluation(self, sample_architecture, sample_scenario):
        """Test basic case evaluation without requirements."""
        metrics = evaluate_case(sample_architecture, sample_scenario)

        # Check antenna metrics present
        assert "g_peak_db" in metrics
        assert "beamwidth_az_deg" in metrics
        assert "sll_db" in metrics
        assert "n_elements" in metrics

        # Check comms metrics present
        assert "eirp_dbw" in metrics
        assert "path_loss_db" in metrics
        assert "snr_rx_db" in metrics
        assert "link_margin_db" in metrics

        # Check SWaP-C metrics present
        assert "rf_power_w" in metrics
        assert "prime_power_w" in metrics
        assert "cost_usd" in metrics

        # Check metadata present
        assert "meta.runtime_s" in metrics
        assert metrics["meta.runtime_s"] > 0

    def test_with_case_id(self, sample_architecture, sample_scenario):
        """Test that case_id is included in metrics."""
        metrics = evaluate_case(
            sample_architecture,
            sample_scenario,
            case_id="TEST-001",
        )

        assert metrics["meta.case_id"] == "TEST-001"

    def test_with_requirements_passing(
        self, sample_architecture, sample_scenario, sample_requirements
    ):
        """Test evaluation with passing requirements."""
        metrics = evaluate_case(
            sample_architecture,
            sample_scenario,
            requirements=sample_requirements,
        )

        assert "verification.passes" in metrics
        assert metrics["verification.passes"] == 1.0
        assert metrics["verification.must_pass_count"] == 2.0
        assert metrics["verification.must_total_count"] == 2.0
        assert metrics["verification.failed_ids"] == ""

    def test_with_requirements_failing(self, sample_architecture, sample_scenario):
        """Test evaluation with failing requirements."""
        strict_requirements = RequirementSet(
            requirements=[
                Requirement(
                    id="REQ-001",
                    name="Impossible EIRP",
                    metric_key="eirp_dbw",
                    op=">=",
                    value=100.0,  # Unrealistically high
                    severity="must",
                ),
            ]
        )

        metrics = evaluate_case(
            sample_architecture,
            sample_scenario,
            requirements=strict_requirements,
        )

        assert metrics["verification.passes"] == 0.0
        assert "REQ-001" in metrics["verification.failed_ids"]

    def test_metrics_consistency(self, sample_architecture, sample_scenario):
        """Test that metrics are internally consistent."""
        metrics = evaluate_case(sample_architecture, sample_scenario)

        # n_elements should match array config
        assert metrics["n_elements"] == 64

        # RF power should be n_elements * power_per_elem
        assert metrics["rf_power_w"] == pytest.approx(64.0)

        # Cost should include element cost
        assert metrics["cost_usd"] >= 64 * 100  # At least element cost


class TestEvaluateCaseWithReport:
    """Tests for evaluate_case_with_report function."""

    @pytest.fixture
    def sample_architecture(self):
        return Architecture(
            array=ArrayConfig(nx=8, ny=8),
            rf=RFChainConfig(tx_power_w_per_elem=1.0),
        )

    @pytest.fixture
    def sample_scenario(self):
        return CommsLinkScenario(
            freq_hz=10e9,
            bandwidth_hz=10e6,
            range_m=100e3,
            required_snr_db=10.0,
        )

    @pytest.fixture
    def sample_requirements(self):
        return RequirementSet(
            requirements=[
                Requirement(
                    id="REQ-001",
                    name="Min EIRP",
                    metric_key="eirp_dbw",
                    op=">=",
                    value=30.0,
                ),
            ]
        )

    def test_returns_tuple(self, sample_architecture, sample_scenario, sample_requirements):
        """Test that function returns both metrics and report."""
        metrics, report = evaluate_case_with_report(
            sample_architecture,
            sample_scenario,
            sample_requirements,
        )

        assert isinstance(metrics, dict)
        assert hasattr(report, "passes")
        assert hasattr(report, "results")

    def test_report_has_results(self, sample_architecture, sample_scenario, sample_requirements):
        """Test that report contains individual results."""
        metrics, report = evaluate_case_with_report(
            sample_architecture,
            sample_scenario,
            sample_requirements,
        )

        assert len(report.results) == 1
        assert report.results[0].requirement.id == "REQ-001"
        assert report.results[0].actual_value is not None


class TestRFCascadeIntegration:
    """Tests for RF cascade integration in evaluate_case."""

    @pytest.fixture
    def cascade_architecture(self):
        return Architecture(
            array=ArrayConfig(nx=8, ny=8, dx_lambda=0.5, dy_lambda=0.5),
            rf=RFChainConfig(
                tx_power_w_per_elem=1.0,
                noise_figure_db=3.0,
                feed_loss_db=1.0,
                rx_stages=[
                    {"name": "LNA", "gain_db": 20.0, "nf_db": 2.0, "iip3_dbm": -10.0},
                    {"name": "Filter", "gain_db": -3.0, "nf_db": 3.0, "iip3_dbm": 50.0},
                    {"name": "IF_Amp", "gain_db": 15.0, "nf_db": 8.0, "iip3_dbm": 5.0},
                ],
            ),
            cost=CostConfig(cost_per_elem_usd=100.0),
        )

    @pytest.fixture
    def sample_scenario(self):
        return CommsLinkScenario(
            freq_hz=10e9,
            bandwidth_hz=10e6,
            range_m=100e3,
            required_snr_db=10.0,
        )

    def test_cascade_metrics_present(self, cascade_architecture, sample_scenario):
        """Test that cascade metrics appear in output."""
        metrics = evaluate_case(cascade_architecture, sample_scenario)
        assert "cascade_nf_db" in metrics
        assert "cascade_gain_db" in metrics
        assert "cascade_iip3_dbm" in metrics
        assert "cascade_oip3_dbm" in metrics
        assert "cascade_mds_dbm" in metrics
        assert "cascade_sfdr_db" in metrics

    def test_cascade_nf_reasonable(self, cascade_architecture, sample_scenario):
        """Cascaded NF should be dominated by first stage but higher."""
        metrics = evaluate_case(cascade_architecture, sample_scenario)
        # First stage NF is 2.0 dB; cascaded should be slightly higher
        assert metrics["cascade_nf_db"] > 2.0
        # But not dramatically higher due to LNA gain
        assert metrics["cascade_nf_db"] < 5.0

    def test_cascade_gain_is_sum(self, cascade_architecture, sample_scenario):
        """Cascade gain should equal sum of stage gains."""
        metrics = evaluate_case(cascade_architecture, sample_scenario)
        expected_gain = 20.0 + (-3.0) + 15.0  # 32 dB
        assert metrics["cascade_gain_db"] == pytest.approx(expected_gain)

    def test_no_rx_stages_no_cascade_metrics(self, sample_scenario):
        """Without rx_stages, no cascade metrics should appear."""
        arch = Architecture(
            array=ArrayConfig(nx=8, ny=8),
            rf=RFChainConfig(tx_power_w_per_elem=1.0),
        )
        metrics = evaluate_case(arch, sample_scenario)
        assert "cascade_nf_db" not in metrics

    def test_cascade_nf_affects_link_budget(self, sample_scenario):
        """Cascaded NF override should change link margin vs scalar NF."""
        # Architecture with scalar NF=3 dB
        arch_scalar = Architecture(
            array=ArrayConfig(nx=8, ny=8),
            rf=RFChainConfig(tx_power_w_per_elem=1.0, noise_figure_db=3.0),
        )
        # Architecture with high cascaded NF via rx_stages
        arch_cascade = Architecture(
            array=ArrayConfig(nx=8, ny=8),
            rf=RFChainConfig(
                tx_power_w_per_elem=1.0,
                noise_figure_db=3.0,
                rx_stages=[
                    {"name": "LNA", "gain_db": 10.0, "nf_db": 5.0},
                    {"name": "Mixer", "gain_db": 5.0, "nf_db": 12.0},
                ],
            ),
        )
        m_scalar = evaluate_case(arch_scalar, sample_scenario)
        m_cascade = evaluate_case(arch_cascade, sample_scenario)

        # Higher NF from cascade -> worse SNR -> lower margin
        assert m_cascade["cascade_nf_db"] > 3.0
        assert m_cascade["link_margin_db"] < m_scalar["link_margin_db"]


class TestReliabilityIntegration:
    """Tests for reliability integration in evaluate_case."""

    @pytest.fixture
    def reliability_architecture(self):
        return Architecture(
            array=ArrayConfig(nx=8, ny=8, dx_lambda=0.5, dy_lambda=0.5),
            rf=RFChainConfig(tx_power_w_per_elem=1.0),
            reliability=ReliabilityConfig(
                operating_temp_c=85.0,
                mttr_hours=8.0,
                mission_hours=8760.0,
            ),
        )

    @pytest.fixture
    def sample_scenario(self):
        return CommsLinkScenario(
            freq_hz=10e9,
            bandwidth_hz=10e6,
            range_m=100e3,
            required_snr_db=10.0,
        )

    def test_reliability_metrics_present(self, reliability_architecture, sample_scenario):
        """Test that all reliability metrics appear."""
        metrics = evaluate_case(reliability_architecture, sample_scenario)
        assert "trm_mtbf_hours" in metrics
        assert "array_mtbf_hours" in metrics
        assert "expected_failed_elements" in metrics
        assert "array_availability" in metrics
        assert "max_failures_for_spec" in metrics
        assert "prob_meeting_spec" in metrics

    def test_no_reliability_config_no_metrics(self, sample_scenario):
        """Without reliability config, no reliability metrics."""
        arch = Architecture(
            array=ArrayConfig(nx=8, ny=8),
            rf=RFChainConfig(tx_power_w_per_elem=1.0),
        )
        metrics = evaluate_case(arch, sample_scenario)
        assert "trm_mtbf_hours" not in metrics

    def test_availability_between_0_and_1(self, reliability_architecture, sample_scenario):
        """Availability should be a valid fraction."""
        metrics = evaluate_case(reliability_architecture, sample_scenario)
        assert 0.0 < metrics["array_availability"] <= 1.0

    def test_prob_meeting_spec_between_0_and_1(self, reliability_architecture, sample_scenario):
        """Prob meeting spec should be a valid fraction."""
        metrics = evaluate_case(reliability_architecture, sample_scenario)
        assert 0.0 <= metrics["prob_meeting_spec"] <= 1.0

    def test_higher_temp_lower_mtbf(self, sample_scenario):
        """Higher operating temp should reduce TRM MTBF."""
        arch_cool = Architecture(
            array=ArrayConfig(nx=8, ny=8),
            rf=RFChainConfig(tx_power_w_per_elem=1.0),
            reliability=ReliabilityConfig(operating_temp_c=55.0),
        )
        arch_hot = Architecture(
            array=ArrayConfig(nx=8, ny=8),
            rf=RFChainConfig(tx_power_w_per_elem=1.0),
            reliability=ReliabilityConfig(operating_temp_c=125.0),
        )
        m_cool = evaluate_case(arch_cool, sample_scenario)
        m_hot = evaluate_case(arch_hot, sample_scenario)
        assert m_hot["trm_mtbf_hours"] < m_cool["trm_mtbf_hours"]


class TestDigitalIntegration:
    """Tests for digital beamformer integration in evaluate_case."""

    @pytest.fixture
    def sample_scenario(self):
        return CommsLinkScenario(
            freq_hz=10e9,
            bandwidth_hz=10e6,
            range_m=100e3,
            required_snr_db=10.0,
        )

    def test_digital_metrics_present(self, sample_scenario):
        """Test that digital metrics appear when DigitalConfig is set."""
        arch = Architecture(
            array=ArrayConfig(nx=8, ny=8),
            rf=RFChainConfig(tx_power_w_per_elem=1.0),
            digital=DigitalConfig(adc_enob=12.0, oversampling_ratio=2.5, n_beams=1),
        )
        metrics = evaluate_case(arch, sample_scenario)
        assert "adc_enob" in metrics
        assert "adc_snr_db" in metrics
        assert "adc_sample_rate_hz" in metrics
        assert "bf_data_rate_gbps" in metrics
        assert "bf_compute_gops" in metrics

    def test_no_digital_config_no_metrics(self, sample_scenario):
        """Without digital config, no digital metrics should appear."""
        arch = Architecture(
            array=ArrayConfig(nx=8, ny=8),
            rf=RFChainConfig(tx_power_w_per_elem=1.0),
        )
        metrics = evaluate_case(arch, sample_scenario)
        assert "adc_enob" not in metrics
        assert "bf_data_rate_gbps" not in metrics

    def test_processing_margin_with_fpga(self, sample_scenario):
        """Processing margin should appear when fpga_throughput_gops is set."""
        arch = Architecture(
            array=ArrayConfig(nx=8, ny=8),
            rf=RFChainConfig(tx_power_w_per_elem=1.0),
            digital=DigitalConfig(
                adc_enob=12.0,
                fpga_throughput_gops=500.0,
            ),
        )
        metrics = evaluate_case(arch, sample_scenario)
        assert "processing_margin_db" in metrics
        assert "fpga_utilization_pct" in metrics

    def test_no_processing_margin_without_fpga(self, sample_scenario):
        """No processing margin without fpga_throughput_gops."""
        arch = Architecture(
            array=ArrayConfig(nx=8, ny=8),
            rf=RFChainConfig(tx_power_w_per_elem=1.0),
            digital=DigitalConfig(adc_enob=12.0),
        )
        metrics = evaluate_case(arch, sample_scenario)
        assert "processing_margin_db" not in metrics
        assert "fpga_utilization_pct" not in metrics

    def test_data_rate_scales_with_elements(self, sample_scenario):
        """bf_data_rate_gbps should increase with more elements."""
        arch_small = Architecture(
            array=ArrayConfig(nx=4, ny=4),
            rf=RFChainConfig(tx_power_w_per_elem=1.0),
            digital=DigitalConfig(adc_enob=12.0),
        )
        arch_large = Architecture(
            array=ArrayConfig(nx=16, ny=16),
            rf=RFChainConfig(tx_power_w_per_elem=1.0),
            digital=DigitalConfig(adc_enob=12.0),
        )
        m_small = evaluate_case(arch_small, sample_scenario)
        m_large = evaluate_case(arch_large, sample_scenario)
        assert m_large["bf_data_rate_gbps"] > m_small["bf_data_rate_gbps"]

    def test_adc_snr_matches_enob(self, sample_scenario):
        """ADC SNR should follow 6.02*ENOB + 1.76 formula."""
        arch = Architecture(
            array=ArrayConfig(nx=8, ny=8),
            rf=RFChainConfig(tx_power_w_per_elem=1.0),
            digital=DigitalConfig(adc_enob=14.0),
        )
        metrics = evaluate_case(arch, sample_scenario)
        expected_snr = 6.02 * 14.0 + 1.76
        assert metrics["adc_snr_db"] == pytest.approx(expected_snr)
