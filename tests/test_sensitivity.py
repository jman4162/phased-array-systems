"""Tests for sensitivity analysis module."""

import pytest

from phased_array_systems.architecture import Architecture, ArrayConfig, RFChainConfig
from phased_array_systems.scenarios import CommsLinkScenario
from phased_array_systems.trades.sensitivity import (
    compute_sensitivity_coefficients,
    oat_sensitivity,
)


@pytest.fixture
def baseline_arch():
    return Architecture(
        array=ArrayConfig(
            nx=8,
            ny=8,
            dx_lambda=0.5,
            dy_lambda=0.5,
            enforce_subarray_constraint=False,
        ),
        rf=RFChainConfig(tx_power_w_per_elem=1.0),
    )


@pytest.fixture
def baseline_scenario():
    return CommsLinkScenario(
        freq_hz=10e9,
        bandwidth_hz=10e6,
        range_m=100e3,
        required_snr_db=10.0,
    )


class TestOATSensitivity:
    """Tests for one-at-a-time sensitivity analysis."""

    def test_basic_sweep(self, baseline_arch, baseline_scenario):
        """Test basic parameter sweep runs without error."""
        param_ranges = {
            "rf.tx_power_w_per_elem": [0.5, 2.0],
        }
        df = oat_sensitivity(
            baseline_arch,
            baseline_scenario,
            param_ranges,
            metric_keys=["g_peak_db", "eirp_dbw"],
            n_steps=3,
        )

        assert len(df) == 3  # 3 steps for 1 parameter
        assert "parameter" in df.columns
        assert "value" in df.columns
        assert "g_peak_db" in df.columns
        assert "eirp_dbw" in df.columns

    def test_multiple_parameters(self, baseline_arch, baseline_scenario):
        """Test sweep with multiple parameters."""
        param_ranges = {
            "rf.tx_power_w_per_elem": [0.5, 2.0],
            "array.dx_lambda": [0.4, 0.6],
        }
        df = oat_sensitivity(
            baseline_arch,
            baseline_scenario,
            param_ranges,
            metric_keys=["g_peak_db"],
            n_steps=3,
        )

        # 3 steps * 2 parameters = 6 rows
        assert len(df) == 6
        assert set(df["parameter"].unique()) == {"rf.tx_power_w_per_elem", "array.dx_lambda"}

    def test_scenario_parameter(self, baseline_arch, baseline_scenario):
        """Test sweeping a scenario parameter."""
        param_ranges = {
            "scenario.range_m": [50e3, 200e3],
        }
        df = oat_sensitivity(
            baseline_arch,
            baseline_scenario,
            param_ranges,
            metric_keys=["link_margin_db"],
            n_steps=3,
        )

        assert len(df) == 3
        # Longer range should reduce link margin
        margins = df.sort_values("value")["link_margin_db"].values
        assert margins[-1] < margins[0]

    def test_tx_power_affects_eirp(self, baseline_arch, baseline_scenario):
        """Higher TX power should increase EIRP monotonically."""
        param_ranges = {
            "rf.tx_power_w_per_elem": [0.5, 5.0],
        }
        df = oat_sensitivity(
            baseline_arch,
            baseline_scenario,
            param_ranges,
            metric_keys=["eirp_dbw"],
            n_steps=5,
        )

        eirp_values = df.sort_values("value")["eirp_dbw"].values
        # Each step should have higher EIRP
        for i in range(len(eirp_values) - 1):
            assert eirp_values[i + 1] > eirp_values[i]


class TestSensitivityCoefficients:
    """Tests for sensitivity coefficient computation."""

    def test_coefficients_computed(self, baseline_arch, baseline_scenario):
        """Test that coefficients are computed correctly."""
        param_ranges = {
            "rf.tx_power_w_per_elem": [0.5, 5.0],
        }
        df = oat_sensitivity(
            baseline_arch,
            baseline_scenario,
            param_ranges,
            metric_keys=["eirp_dbw"],
            n_steps=5,
        )

        coeffs = compute_sensitivity_coefficients(df, metric_keys=["eirp_dbw"])

        assert len(coeffs) == 1
        assert coeffs.iloc[0]["parameter"] == "rf.tx_power_w_per_elem"
        assert coeffs.iloc[0]["metric"] == "eirp_dbw"
        assert coeffs.iloc[0]["sensitivity"] > 0
        assert coeffs.iloc[0]["delta"] > 0

    def test_relative_sensitivity_ranking(self, baseline_arch, baseline_scenario):
        """Test that high-impact parameters rank higher."""
        param_ranges = {
            "rf.tx_power_w_per_elem": [0.1, 10.0],  # 20x range, big impact on EIRP
            "array.dx_lambda": [0.45, 0.55],  # Small range, small impact on EIRP
        }
        df = oat_sensitivity(
            baseline_arch,
            baseline_scenario,
            param_ranges,
            metric_keys=["eirp_dbw"],
            n_steps=5,
        )

        coeffs = compute_sensitivity_coefficients(df, metric_keys=["eirp_dbw"])
        coeffs = coeffs.sort_values("sensitivity", ascending=False)

        # TX power should be more sensitive than element spacing for EIRP
        assert coeffs.iloc[0]["parameter"] == "rf.tx_power_w_per_elem"
