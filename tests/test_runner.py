"""Tests for the batch runner."""

import tempfile
from pathlib import Path

import pandas as pd
import pytest

from phased_array_systems.requirements import Requirement, RequirementSet
from phased_array_systems.scenarios import CommsLinkScenario
from phased_array_systems.trades.doe import generate_doe_from_dict
from phased_array_systems.trades.runner import (
    BatchRunner,
    default_architecture_builder,
    run_batch_simple,
)


class TestDefaultArchitectureBuilder:
    """Tests for the default architecture builder."""

    def test_builds_from_flat_dict(self):
        case = {
            "case_id": "test_001",
            "array.nx": 8,
            "array.ny": 8,
            "array.geometry": "rectangular",
            "array.dx_lambda": 0.5,
            "array.dy_lambda": 0.5,
            "array.scan_limit_deg": 60.0,
            "rf.tx_power_w_per_elem": 1.0,
            "rf.pa_efficiency": 0.3,
            "rf.noise_figure_db": 3.0,
            "rf.n_tx_beams": 1,
            "rf.feed_loss_db": 1.0,
            "rf.system_loss_db": 0.0,
        }

        arch = default_architecture_builder(case)

        assert arch.array.nx == 8
        assert arch.array.ny == 8
        assert arch.rf.tx_power_w_per_elem == 1.0

    def test_ignores_non_architecture_keys(self):
        case = {
            "case_id": "test_001",
            "extra_column": 42,
            "array.nx": 8,
            "array.ny": 8,
            "array.geometry": "rectangular",
            "array.dx_lambda": 0.5,
            "array.dy_lambda": 0.5,
            "array.scan_limit_deg": 60.0,
            "rf.tx_power_w_per_elem": 1.0,
            "rf.pa_efficiency": 0.3,
            "rf.noise_figure_db": 3.0,
            "rf.n_tx_beams": 1,
            "rf.feed_loss_db": 1.0,
            "rf.system_loss_db": 0.0,
        }

        arch = default_architecture_builder(case)
        assert arch.array.nx == 8

    def test_passes_digital_and_reliability_keys(self):
        case = {
            "case_id": "test_001",
            "array.nx": 8,
            "array.ny": 8,
            "rf.tx_power_w_per_elem": 1.0,
            "digital.adc_enob": 10.0,
            "digital.n_beams": 4,
            "digital.digitization_level": "subarray",
            "reliability.mttr_hours": 4.0,
        }

        arch = default_architecture_builder(case)

        assert arch.digital is not None
        assert arch.digital.adc_enob == 10.0
        assert arch.digital.n_beams == 4
        assert arch.n_digital_channels == arch.array.n_subarrays
        assert arch.reliability is not None
        assert arch.reliability.mttr_hours == 4.0

    def test_doe_over_digital_variables(self):
        """A DOE sweeping digital.* must produce varying digital metrics."""
        doe = generate_doe_from_dict(
            {"digital.adc_enob": (8.0, 14.0)},
            method="lhs",
            n_samples=4,
            seed=1,
        )
        doe["array.nx"] = 8
        doe["array.ny"] = 8
        doe["rf.tx_power_w_per_elem"] = 1.0

        scenario = CommsLinkScenario(
            freq_hz=10e9,
            bandwidth_hz=10e6,
            range_m=100e3,
            required_snr_db=10.0,
        )
        results = run_batch_simple(doe, scenario)

        assert "adc_snr_db" in results.columns
        assert results["adc_snr_db"].nunique() == 4


class TestBatchRunner:
    """Tests for the BatchRunner."""

    @pytest.fixture
    def sample_scenario(self):
        return CommsLinkScenario(
            freq_hz=10e9,
            bandwidth_hz=10e6,
            range_m=100e3,
            required_snr_db=10.0,
        )

    @pytest.fixture
    def sample_cases(self):
        return generate_doe_from_dict(
            {
                "array.nx": (4, 8, "int"),
                "array.ny": (4, 8, "int"),
                "array.geometry": ["rectangular"],
                "array.dx_lambda": (0.5, 0.5),
                "array.dy_lambda": (0.5, 0.5),
                "array.scan_limit_deg": (60.0, 60.0),
                "rf.tx_power_w_per_elem": (0.5, 2.0),
                "rf.pa_efficiency": (0.3, 0.3),
                "rf.noise_figure_db": (3.0, 3.0),
                "rf.n_tx_beams": (1, 1, "int"),
                "rf.feed_loss_db": (1.0, 1.0),
                "rf.system_loss_db": (0.0, 0.0),
            },
            method="grid",
            n_samples=9,  # 3x3 grid for nx, ny
        )

    def test_runner_creation(self, sample_scenario):
        runner = BatchRunner(sample_scenario)
        assert runner.scenario == sample_scenario

    def test_basic_run(self, sample_scenario, sample_cases):
        # Use a small subset
        cases = sample_cases.head(4)

        runner = BatchRunner(sample_scenario)
        results = runner.run(cases, n_workers=1)

        assert len(results) == 4
        assert "eirp_dbw" in results.columns
        assert "link_margin_db" in results.columns
        assert "meta.runtime_s" in results.columns

    def test_run_with_requirements(self, sample_scenario, sample_cases):
        cases = sample_cases.head(4)

        requirements = RequirementSet(
            requirements=[
                Requirement(
                    id="REQ-001",
                    name="Min EIRP",
                    metric_key="eirp_dbw",
                    op=">=",
                    value=20.0,
                ),
            ]
        )

        runner = BatchRunner(sample_scenario, requirements=requirements)
        results = runner.run(cases, n_workers=1)

        assert "verification.passes" in results.columns

    def test_run_with_cache(self, sample_scenario, sample_cases):
        pytest.importorskip("pyarrow", reason="pyarrow required for parquet caching")

        cases = sample_cases.head(4)

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "cache.parquet"

            runner = BatchRunner(sample_scenario)

            # First run
            results1 = runner.run(cases, n_workers=1, cache_path=cache_path)
            assert len(results1) == 4
            assert cache_path.exists()

            # Second run should use cache
            results2 = runner.run(cases, n_workers=1, cache_path=cache_path)
            assert len(results2) == 4

    def test_error_handling(self, sample_scenario):
        """Test that individual case errors don't crash the batch."""
        # Create cases with one that will fail (invalid array size)
        cases = pd.DataFrame(
            {
                "case_id": ["good", "bad"],
                "array.nx": [8, 0],  # 0 will cause validation error
                "array.ny": [8, 8],
                "array.geometry": ["rectangular", "rectangular"],
                "array.dx_lambda": [0.5, 0.5],
                "array.dy_lambda": [0.5, 0.5],
                "array.scan_limit_deg": [60.0, 60.0],
                "rf.tx_power_w_per_elem": [1.0, 1.0],
                "rf.pa_efficiency": [0.3, 0.3],
                "rf.noise_figure_db": [3.0, 3.0],
                "rf.n_tx_beams": [1, 1],
                "rf.feed_loss_db": [1.0, 1.0],
                "rf.system_loss_db": [0.0, 0.0],
            }
        )

        runner = BatchRunner(sample_scenario)
        results = runner.run(cases, n_workers=1)

        # Should still get 2 results
        assert len(results) == 2

        # Good case should have metrics
        good_result = results[results["case_id"] == "good"].iloc[0]
        assert pd.notna(good_result.get("eirp_dbw"))

        # Bad case should have error
        bad_result = results[results["case_id"] == "bad"].iloc[0]
        assert pd.notna(bad_result.get("meta.error"))


class TestRunBatchSimple:
    """Tests for the simple batch run function."""

    def test_simple_run(self):
        scenario = CommsLinkScenario(
            freq_hz=10e9,
            bandwidth_hz=10e6,
            range_m=100e3,
            required_snr_db=10.0,
        )

        cases = generate_doe_from_dict(
            {
                "array.nx": (4, 8, "int"),
                "array.ny": (4, 8, "int"),
                "array.geometry": ["rectangular"],
                "array.dx_lambda": (0.5, 0.5),
                "array.dy_lambda": (0.5, 0.5),
                "array.scan_limit_deg": (60.0, 60.0),
                "rf.tx_power_w_per_elem": (1.0, 1.0),
                "rf.pa_efficiency": (0.3, 0.3),
                "rf.noise_figure_db": (3.0, 3.0),
                "rf.n_tx_beams": (1, 1, "int"),
                "rf.feed_loss_db": (1.0, 1.0),
                "rf.system_loss_db": (0.0, 0.0),
            },
            method="lhs",
            n_samples=5,
            seed=42,
        )

        results = run_batch_simple(cases, scenario)

        assert len(results) == 5
        assert "eirp_dbw" in results.columns
