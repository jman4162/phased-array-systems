"""Tests for SWaP-C models."""

import pytest

from phased_array_systems.architecture import (
    Architecture,
    ArrayConfig,
    CostConfig,
    RFChainConfig,
)
from phased_array_systems.models.swapc import CostModel, PowerModel
from phased_array_systems.models.swapc.cost import compute_cost_per_watt
from phased_array_systems.models.swapc.power import compute_thermal_load
from phased_array_systems.scenarios import CommsLinkScenario


class TestPowerModel:
    """Tests for the PowerModel."""

    @pytest.fixture
    def sample_architecture(self):
        return Architecture(
            array=ArrayConfig(nx=8, ny=8),  # 64 elements
            rf=RFChainConfig(
                tx_power_w_per_elem=1.0,  # 1W per element
                pa_efficiency=0.3,  # 30% efficiency
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

    def test_model_creation(self):
        """Test model can be created."""
        model = PowerModel()
        assert model.name == "power"
        assert model.overhead_factor == 0.2

    def test_rf_power_calculation(self, sample_architecture, sample_scenario):
        """Test RF power calculation."""
        model = PowerModel()
        metrics = model.evaluate(sample_architecture, sample_scenario, {})

        # 64 elements * 1W = 64W
        assert metrics["rf_power_w"] == pytest.approx(64.0)

    def test_dc_power_calculation(self, sample_architecture, sample_scenario):
        """Test DC power calculation."""
        model = PowerModel()
        metrics = model.evaluate(sample_architecture, sample_scenario, {})

        # DC = RF / efficiency = 64 / 0.3 ≈ 213.3W
        expected_dc = 64.0 / 0.3
        assert metrics["dc_power_w"] == pytest.approx(expected_dc)

    def test_prime_power_calculation(self, sample_architecture, sample_scenario):
        """Test prime power with overhead."""
        model = PowerModel(overhead_factor=0.2)
        metrics = model.evaluate(sample_architecture, sample_scenario, {})

        # Prime = DC * (1 + 0.2) = DC * 1.2
        expected_prime = (64.0 / 0.3) * 1.2
        assert metrics["prime_power_w"] == pytest.approx(expected_prime)

    def test_custom_overhead(self, sample_architecture, sample_scenario):
        """Test custom overhead factor."""
        model = PowerModel(overhead_factor=0.5)  # 50% overhead
        metrics = model.evaluate(sample_architecture, sample_scenario, {})

        expected_prime = (64.0 / 0.3) * 1.5
        assert metrics["prime_power_w"] == pytest.approx(expected_prime)


class TestPowerModelExtended:
    """Tests for duty cycle, RX chain, and digital section power."""

    @pytest.fixture
    def comms_scenario(self):
        return CommsLinkScenario(
            freq_hz=10e9,
            bandwidth_hz=100e6,
            range_m=100e3,
            required_snr_db=10.0,
        )

    def test_duty_cycle_scales_dc_power(self):
        """Pulsed radar at 10% duty draws 10% of the CW PA DC power."""
        from phased_array_systems.scenarios import RadarDetectionScenario

        arch = Architecture(
            array=ArrayConfig(nx=8, ny=8),
            rf=RFChainConfig(tx_power_w_per_elem=1.0, pa_efficiency=0.4),
        )
        cw = RadarDetectionScenario(
            freq_hz=10e9, bandwidth_hz=1e6, range_m=50e3, target_rcs_dbsm=0.0, duty_cycle=1.0
        )
        pulsed = RadarDetectionScenario(
            freq_hz=10e9, bandwidth_hz=1e6, range_m=50e3, target_rcs_dbsm=0.0, duty_cycle=0.1
        )

        model = PowerModel()
        m_cw = model.evaluate(arch, cw, {})
        m_pulsed = model.evaluate(arch, pulsed, {})

        # Peak RF power is unchanged; average and DC scale with duty
        assert m_pulsed["rf_power_w"] == pytest.approx(m_cw["rf_power_w"])
        assert m_pulsed["rf_avg_power_w"] == pytest.approx(0.1 * m_cw["rf_avg_power_w"])
        assert m_pulsed["pa_dc_power_w"] == pytest.approx(0.1 * m_cw["pa_dc_power_w"])

    def test_rx_chain_power_included(self, comms_scenario):
        arch = Architecture(
            array=ArrayConfig(nx=8, ny=8),
            rf=RFChainConfig(tx_power_w_per_elem=1.0, pa_efficiency=0.4, rx_power_w_per_elem=0.25),
        )
        metrics = PowerModel().evaluate(arch, comms_scenario, {})

        assert metrics["rx_dc_power_w"] == pytest.approx(64 * 0.25)
        assert metrics["dc_power_w"] == pytest.approx(
            metrics["pa_dc_power_w"] + metrics["rx_dc_power_w"]
        )

    def test_digital_section_power_included(self, comms_scenario):
        """ADC and DSP power appear in the DC budget when digital is configured."""
        from phased_array_systems.architecture import DigitalConfig

        arch = Architecture(
            array=ArrayConfig(nx=8, ny=8),
            rf=RFChainConfig(tx_power_w_per_elem=1.0, pa_efficiency=0.4),
            digital=DigitalConfig(adc_enob=12.0, n_beams=4),
        )
        metrics = PowerModel().evaluate(arch, comms_scenario, {})

        assert metrics["adc_power_w"] > 0
        assert metrics["dsp_power_w"] > 0
        assert metrics["dc_power_w"] == pytest.approx(
            metrics["pa_dc_power_w"]
            + metrics["rx_dc_power_w"]
            + metrics["adc_power_w"]
            + metrics["dsp_power_w"]
        )

    def test_subarray_digitization_cuts_digital_power(self, comms_scenario):
        """Fewer digitized channels -> less ADC power."""
        from phased_array_systems.architecture import DigitalConfig

        def build(level):
            return Architecture(
                array=ArrayConfig(nx=16, ny=16, max_subarray_nx=8, max_subarray_ny=8),
                rf=RFChainConfig(tx_power_w_per_elem=1.0, pa_efficiency=0.4),
                digital=DigitalConfig(adc_enob=12.0, digitization_level=level),
            )

        model = PowerModel()
        elem = model.evaluate(build("element"), comms_scenario, {})
        sub = model.evaluate(build("subarray"), comms_scenario, {})

        # 256 elements vs 4 subarrays
        assert elem["adc_power_w"] == pytest.approx(64 * sub["adc_power_w"])


class TestThermalLoad:
    """Tests for thermal load calculation."""

    def test_basic_thermal(self):
        """Test basic thermal dissipation calculation."""
        result = compute_thermal_load(
            dc_power_w=200.0,
            rf_power_w=60.0,
        )

        # Heat = 200 - 60 = 140W
        assert result["heat_dissipation_w"] == pytest.approx(140.0)
        # Efficiency = 60/200 = 0.3
        assert result["rf_efficiency"] == pytest.approx(0.3)

    def test_with_additional_dissipation(self):
        """Test thermal with additional heat sources."""
        result = compute_thermal_load(
            dc_power_w=200.0,
            rf_power_w=60.0,
            additional_dissipation_w=20.0,
        )

        # Heat = 200 - 60 + 20 = 160W
        assert result["heat_dissipation_w"] == pytest.approx(160.0)


class TestCostModel:
    """Tests for the CostModel."""

    @pytest.fixture
    def sample_architecture(self):
        return Architecture(
            array=ArrayConfig(nx=8, ny=8),  # 64 elements
            rf=RFChainConfig(tx_power_w_per_elem=1.0),
            cost=CostConfig(
                cost_per_elem_usd=100.0,
                nre_usd=10000.0,
                integration_cost_usd=5000.0,
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

    def test_model_creation(self):
        """Test model can be created."""
        model = CostModel()
        assert model.name == "cost"

    def test_recurring_cost(self, sample_architecture, sample_scenario):
        """Test recurring cost calculation."""
        model = CostModel()
        metrics = model.evaluate(sample_architecture, sample_scenario, {})

        # 64 elements * $100 = $6,400
        assert metrics["recurring_cost_usd"] == pytest.approx(6400.0)

    def test_total_cost(self, sample_architecture, sample_scenario):
        """Test total cost calculation."""
        model = CostModel()
        metrics = model.evaluate(sample_architecture, sample_scenario, {})

        # Total = 6400 + 10000 + 5000 = $21,400
        assert metrics["total_cost_usd"] == pytest.approx(21400.0)
        assert metrics["cost_usd"] == pytest.approx(21400.0)

    def test_cost_scales_with_elements(self):
        """Test that cost scales with array size."""
        model = CostModel()
        scenario = CommsLinkScenario(
            freq_hz=10e9,
            bandwidth_hz=10e6,
            range_m=100e3,
            required_snr_db=10.0,
        )

        arch_small = Architecture(
            array=ArrayConfig(nx=4, ny=4),  # 16 elements
            rf=RFChainConfig(tx_power_w_per_elem=1.0),
            cost=CostConfig(cost_per_elem_usd=100.0),
        )

        arch_large = Architecture(
            array=ArrayConfig(nx=16, ny=16),  # 256 elements
            rf=RFChainConfig(tx_power_w_per_elem=1.0),
            cost=CostConfig(cost_per_elem_usd=100.0),
        )

        metrics_small = model.evaluate(arch_small, scenario, {})
        metrics_large = model.evaluate(arch_large, scenario, {})

        # Large should be 16x more expensive in recurring cost
        assert metrics_large["recurring_cost_usd"] == 16 * metrics_small["recurring_cost_usd"]


class TestCostUtilities:
    """Tests for cost utility functions."""

    def test_cost_per_watt(self):
        """Test cost per Watt calculation."""
        cost_per_w = compute_cost_per_watt(10000.0, 100.0)
        assert cost_per_w == pytest.approx(100.0)  # $100/W

    def test_cost_per_watt_zero_power(self):
        """Test cost per Watt with zero power."""
        cost_per_w = compute_cost_per_watt(10000.0, 0.0)
        assert cost_per_w == float("inf")

    def test_cost_per_db_removed(self):
        """USD divided by a dB value is dimensionless nonsense; removed in v0.8."""
        import phased_array_systems.models.swapc.cost as cost_mod

        assert not hasattr(cost_mod, "compute_cost_per_db")
