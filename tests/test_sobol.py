"""Tests for Sobol global sensitivity (requires [mdao] extra)."""

import pytest

pytest.importorskip("SALib", reason="SALib required for Sobol tests")

from phased_array_systems.scenarios import CommsLinkScenario  # noqa: E402
from phased_array_systems.trades import DesignSpace  # noqa: E402
from phased_array_systems.trades.sensitivity import sobol_sensitivity  # noqa: E402

BASE = {"array.nx": 8, "array.ny": 8}


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
        .add_variable("rf.tx_power_w_per_elem", "float", low=0.5, high=4.0)
        .add_variable("rf.pa_efficiency", "float", low=0.2, high=0.5)
    )


class TestSobolSensitivity:
    def test_known_variance_shares(self, space, scenario):
        """EIRP depends only on TX power; PA efficiency's index must be ~0."""
        df = sobol_sensitivity(
            space,
            scenario,
            ["eirp_dbw", "prime_power_w"],
            base_config=BASE,
            n_base=64,
            seed=2,
        )

        eirp = df[df["metric"] == "eirp_dbw"].set_index("parameter")
        assert eirp.loc["rf.tx_power_w_per_elem", "ST"] > 0.9
        assert abs(eirp.loc["rf.pa_efficiency", "ST"]) < 0.05

        # Prime power depends on both (P/eta scaling)
        power = df[df["metric"] == "prime_power_w"].set_index("parameter")
        assert power.loc["rf.tx_power_w_per_elem", "ST"] > 0.3
        assert power.loc["rf.pa_efficiency", "ST"] > 0.1

    def test_deterministic_under_seed(self, space, scenario):
        a = sobol_sensitivity(space, scenario, ["eirp_dbw"], base_config=BASE, n_base=32, seed=5)
        b = sobol_sensitivity(space, scenario, ["eirp_dbw"], base_config=BASE, n_base=32, seed=5)
        assert a.round(12).equals(b.round(12))

    def test_categorical_raises(self, scenario):
        space = DesignSpace().add_variable("array.geometry", "categorical", values=["rectangular"])
        with pytest.raises(ValueError, match="categorical"):
            sobol_sensitivity(space, scenario, ["eirp_dbw"], base_config=BASE, n_base=8)

    def test_degenerate_bounds_raise(self, scenario):
        space = DesignSpace().add_variable("rf.tx_power_w_per_elem", "float", low=1.0, high=1.0)
        with pytest.raises(ValueError, match="degenerate"):
            sobol_sensitivity(space, scenario, ["eirp_dbw"], base_config=BASE, n_base=8)

    def test_constrained_domain_raises_clearly(self, scenario):
        """Mostly-infeasible integer domains produce an actionable error."""
        space = (
            DesignSpace()
            .add_variable("array.nx", "int", low=4, high=16)
            .add_variable("array.ny", "int", low=4, high=16)
        )
        with pytest.raises(ValueError, match="rectangular feasible domain"):
            sobol_sensitivity(
                space,
                scenario,
                ["eirp_dbw"],
                base_config={"rf.tx_power_w_per_elem": 1.0},
                n_base=16,
            )
