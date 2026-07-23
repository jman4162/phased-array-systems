"""Tests for NSGA-II multi-objective optimization (requires [mdao] extra)."""

import pytest

pytest.importorskip("pymoo", reason="pymoo required for multi-objective tests")

from phased_array_systems.requirements import Requirement, RequirementSet  # noqa: E402
from phased_array_systems.scenarios import CommsLinkScenario  # noqa: E402
from phased_array_systems.trades import DesignSpace, filter_feasible  # noqa: E402
from phased_array_systems.trades.moo import optimize_pareto  # noqa: E402


@pytest.fixture
def scenario():
    return CommsLinkScenario(
        freq_hz=10e9,
        bandwidth_hz=10e6,
        range_m=100e3,
        required_snr_db=10.0,
    )


@pytest.fixture
def space():
    return (
        DesignSpace()
        .add_variable("array.nx", "categorical", values=[4, 8, 16, 32])
        .add_variable("array.ny", "categorical", values=[4, 8, 16, 32])
        .add_variable("rf.tx_power_w_per_elem", "float", low=0.5, high=2.0)
    )


@pytest.fixture
def requirements():
    return RequirementSet(
        requirements=[
            Requirement(
                id="R1",
                name="Positive margin",
                metric_key="link_margin_db",
                op=">=",
                value=0.0,
                severity="must",
            ),
        ]
    )


class TestOptimizePareto:
    def _run(self, space, scenario, requirements, seed=3):
        return optimize_pareto(
            space,
            scenario,
            [("eirp_dbw", "maximize"), ("cost_usd", "minimize")],
            requirements=requirements,
            n_generations=20,
            pop_size=24,
            seed=seed,
        )

    def test_front_contains_extreme_corners(self, space, scenario, requirements):
        """EIRP is monotone in N*P and cost in N: the true front spans from
        the smallest feasible array to the largest at max power."""
        front = self._run(space, scenario, requirements)

        assert len(front) >= 3
        # Cheapest point uses the smallest array; best-EIRP point the largest
        cheapest = front.loc[front["cost_usd"].idxmin()]
        best = front.loc[front["eirp_dbw"].idxmax()]
        assert cheapest["cost_usd"] < best["cost_usd"]
        assert best["array.nx"] * best["array.ny"] == 32 * 32
        # On this trade, max TX power is free (cost is per-element only)
        assert (front["rf.tx_power_w_per_elem"] > 1.9).all()

    def test_front_is_nondominated_and_feasible(self, space, scenario, requirements):
        front = self._run(space, scenario, requirements)

        # Feasible per the same requirements
        feasible = filter_feasible(front, requirements)
        assert len(feasible) == len(front)

        # Pairwise nondomination on (max eirp, min cost)
        pts = front[["eirp_dbw", "cost_usd"]].to_numpy()
        for i in range(len(pts)):
            for j in range(len(pts)):
                if i == j:
                    continue
                dominates = (
                    pts[j][0] >= pts[i][0]
                    and pts[j][1] <= pts[i][1]
                    and (pts[j][0] > pts[i][0] or pts[j][1] < pts[i][1])
                )
                assert not dominates, f"point {j} dominates point {i}"

    def test_integer_and_categorical_types_preserved(self, space, scenario, requirements):
        front = self._run(space, scenario, requirements)
        assert all(v in (4, 8, 16, 32) for v in front["array.nx"])
        assert all(v in (4, 8, 16, 32) for v in front["array.ny"])

    def test_deterministic_under_seed(self, space, scenario, requirements):
        a = self._run(space, scenario, requirements, seed=11)
        b = self._run(space, scenario, requirements, seed=11)
        cols = ["array.nx", "array.ny", "rf.tx_power_w_per_elem", "eirp_dbw", "cost_usd"]
        assert a[cols].round(9).equals(b[cols].round(9))

    def test_integer_variable_type(self, scenario, requirements):
        """Integer (not categorical) design variables land on integers."""
        space = (
            DesignSpace()
            .add_variable("array.nx", "int", low=4, high=8)
            .add_variable("array.ny", "categorical", values=[8])
            .add_variable("rf.tx_power_w_per_elem", "float", low=0.5, high=2.0)
        )
        front = optimize_pareto(
            space,
            scenario,
            [("eirp_dbw", "maximize"), ("cost_usd", "minimize")],
            requirements=requirements,
            n_generations=10,
            pop_size=16,
            seed=5,
        )
        # Subarray constraint (power of two in 4..8) is enforced by the
        # worst-case handling: infeasible nx values cannot survive
        assert all(float(v).is_integer() for v in front["array.nx"])

    def test_empty_objectives_raises(self, space, scenario):
        with pytest.raises(ValueError):
            optimize_pareto(space, scenario, [], n_generations=2, pop_size=8)
