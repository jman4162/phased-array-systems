"""Tests for the optimization module."""

import argparse
from pathlib import Path

import pytest

from phased_array_systems.architecture import Architecture
from phased_array_systems.evaluate import evaluate_case
from phased_array_systems.requirements import Requirement, RequirementSet
from phased_array_systems.scenarios import CommsLinkScenario
from phased_array_systems.trades import DesignSpace, OptimizationResult, optimize_design


@pytest.fixture
def comms_scenario():
    return CommsLinkScenario(
        freq_hz=10e9,
        bandwidth_hz=10e6,
        range_m=100e3,
        required_snr_db=10.0,
        scan_angle_deg=0.0,
        rx_antenna_gain_db=0.0,
        rx_noise_temp_k=290.0,
    )


@pytest.fixture
def design_space():
    return (
        DesignSpace(name="Test Opt")
        .add_variable("array.nx", type="categorical", values=[4, 8, 16])
        .add_variable("array.ny", type="categorical", values=[4, 8, 16])
        .add_variable("array.enforce_subarray_constraint", type="categorical", values=[True])
        .add_variable("array.geometry", type="categorical", values=["rectangular"])
        .add_variable("rf.tx_power_w_per_elem", type="float", low=0.5, high=3.0)
        .add_variable("rf.pa_efficiency", type="float", low=0.2, high=0.5)
        .add_variable("rf.noise_figure_db", type="float", low=3.0, high=3.0)
        .add_variable("cost.cost_per_elem_usd", type="float", low=75.0, high=150.0)
    )


@pytest.fixture
def requirements():
    return RequirementSet(
        requirements=[
            Requirement(
                id="REQ-001",
                name="Minimum EIRP",
                metric_key="eirp_dbw",
                op=">=",
                value=35.0,
                severity="must",
            ),
            Requirement(
                id="REQ-002",
                name="Maximum Cost",
                metric_key="cost_usd",
                op="<=",
                value=100000.0,
                severity="must",
            ),
        ],
    )


class TestOptimizeSingleObjective:
    """Tests for single-objective optimization."""

    def test_optimize_maximize_eirp(self, design_space, comms_scenario):
        """Maximize EIRP - result should have high EIRP."""
        result = optimize_design(
            design_space=design_space,
            scenario=comms_scenario,
            objectives=[("eirp_dbw", "maximize")],
            method="differential_evolution",
            seed=42,
            max_iter=30,
        )

        assert isinstance(result, OptimizationResult)
        assert result.best_metrics["eirp_dbw"] is not None
        assert result.n_evaluations > 0
        assert result.runtime_s > 0
        assert isinstance(result.best_architecture, Architecture)

    def test_optimize_minimize_cost(self, design_space, comms_scenario):
        """Minimize cost - result should have low cost."""
        result = optimize_design(
            design_space=design_space,
            scenario=comms_scenario,
            objectives=[("cost_usd", "minimize")],
            method="differential_evolution",
            seed=42,
            max_iter=30,
        )

        assert result.best_metrics["cost_usd"] is not None
        # Smallest array (4x4) with cheapest elements should be cheapest
        assert result.best_metrics["cost_usd"] < 50000

    def test_optimize_returns_valid_architecture(self, design_space, comms_scenario):
        """Optimized architecture can be re-evaluated."""
        result = optimize_design(
            design_space=design_space,
            scenario=comms_scenario,
            objectives=[("eirp_dbw", "maximize")],
            method="differential_evolution",
            seed=42,
            max_iter=20,
        )

        # Re-evaluate the architecture
        metrics = evaluate_case(result.best_architecture, comms_scenario)
        assert "eirp_dbw" in metrics
        assert "g_peak_db" in metrics


class TestOptimizeWithConstraints:
    """Tests for constrained optimization."""

    def test_optimize_with_requirements(self, design_space, comms_scenario, requirements):
        """Optimization with requirements as constraints."""
        result = optimize_design(
            design_space=design_space,
            scenario=comms_scenario,
            objectives=[("eirp_dbw", "maximize")],
            requirements=requirements,
            method="differential_evolution",
            seed=42,
            max_iter=30,
        )

        # Should satisfy cost constraint
        assert result.best_metrics["cost_usd"] <= 100000


class TestOptimizeIntegerVariables:
    """Tests for integer variable handling."""

    def test_optimize_respects_int_variables(self, comms_scenario):
        """Integer variables (array.nx via categorical) should stay as valid values."""
        space = (
            DesignSpace(name="Int Test")
            .add_variable("array.nx", type="categorical", values=[4, 8, 16])
            .add_variable("array.ny", type="categorical", values=[4, 8])
            .add_variable("array.enforce_subarray_constraint", type="categorical", values=[True])
            .add_variable("array.geometry", type="categorical", values=["rectangular"])
            .add_variable("rf.tx_power_w_per_elem", type="float", low=1.0, high=2.0)
        )

        result = optimize_design(
            design_space=space,
            scenario=comms_scenario,
            objectives=[("eirp_dbw", "maximize")],
            method="differential_evolution",
            seed=42,
            max_iter=20,
        )

        # nx and ny should be valid power-of-2 values
        nx = result.best_architecture.array.nx
        ny = result.best_architecture.array.ny
        assert nx in [4, 8, 16]
        assert ny in [4, 8]


class TestOptimizeWeightedMultiObjective:
    """Tests for weighted multi-objective optimization."""

    def test_optimize_weighted_eirp_cost(self, design_space, comms_scenario):
        """Weighted optimization of EIRP and cost."""
        result = optimize_design(
            design_space=design_space,
            scenario=comms_scenario,
            objectives=[("eirp_dbw", "maximize"), ("cost_usd", "minimize")],
            weights=[0.5, 0.5],
            method="differential_evolution",
            seed=42,
            max_iter=30,
        )

        assert result.best_metrics["eirp_dbw"] is not None
        assert result.best_metrics["cost_usd"] is not None


class TestOptimizeHistory:
    """Tests for evaluation history tracking."""

    def test_track_history(self, design_space, comms_scenario):
        """History should be populated when track_history=True."""
        result = optimize_design(
            design_space=design_space,
            scenario=comms_scenario,
            objectives=[("eirp_dbw", "maximize")],
            method="differential_evolution",
            seed=42,
            max_iter=10,
            track_history=True,
        )

        assert len(result.design_history) > 0
        assert "eirp_dbw" in result.design_history[0]

    def test_no_history_by_default(self, design_space, comms_scenario):
        """History should be empty by default."""
        result = optimize_design(
            design_space=design_space,
            scenario=comms_scenario,
            objectives=[("eirp_dbw", "maximize")],
            method="differential_evolution",
            seed=42,
            max_iter=10,
        )

        assert len(result.design_history) == 0


class TestOptimizeValidation:
    """Tests for input validation."""

    def test_empty_objectives_raises(self, design_space, comms_scenario):
        """Empty objectives should raise ValueError."""
        with pytest.raises(ValueError, match="At least one objective"):
            optimize_design(
                design_space=design_space,
                scenario=comms_scenario,
                objectives=[],
            )

    def test_weights_mismatch_raises(self, design_space, comms_scenario):
        """Mismatched weights should raise ValueError."""
        with pytest.raises(ValueError, match="weights length"):
            optimize_design(
                design_space=design_space,
                scenario=comms_scenario,
                objectives=[("eirp_dbw", "maximize")],
                weights=[0.5, 0.5],
            )

    def test_unknown_method_raises(self, design_space, comms_scenario):
        """Unknown method should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown method"):
            optimize_design(
                design_space=design_space,
                scenario=comms_scenario,
                objectives=[("eirp_dbw", "maximize")],
                method="bogus",
            )


CONFIGS_DIR = Path(__file__).parent.parent / "examples" / "configs"


class TestCmdOptimize:
    """End-to-end test for the optimize CLI command."""

    def test_cmd_optimize_comms(self, capsys):
        """Test cmd_optimize with comms_doe.yaml."""
        from phased_array_systems.cli import cmd_optimize

        args = argparse.Namespace(
            config=CONFIGS_DIR / "comms_doe.yaml",
            objective="eirp_dbw",
            sense="maximize",
            method="de",
            max_iter=10,
            seed=42,
            output=None,
        )
        ret = cmd_optimize(args)
        assert ret == 0

        captured = capsys.readouterr()
        assert "Optimal Design" in captured.out

    def test_cmd_optimize_output_file(self, tmp_path, capsys):
        """Test cmd_optimize writes output JSON."""
        import json

        from phased_array_systems.cli import cmd_optimize

        out_file = tmp_path / "opt_result.json"
        args = argparse.Namespace(
            config=CONFIGS_DIR / "comms_doe.yaml",
            objective="eirp_dbw",
            sense="maximize",
            method="de",
            max_iter=10,
            seed=42,
            output=out_file,
        )
        ret = cmd_optimize(args)
        assert ret == 0
        assert out_file.exists()

        data = json.loads(out_file.read_text())
        assert data["objective"] == "eirp_dbw"
        assert "metrics" in data
