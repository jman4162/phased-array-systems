"""Shared test fixtures for phased-array-systems."""

from pathlib import Path

import pytest

from phased_array_systems.architecture import (
    Architecture,
    ArrayConfig,
    CostConfig,
    RFChainConfig,
)
from phased_array_systems.requirements import Requirement, RequirementSet
from phased_array_systems.scenarios import CommsLinkScenario, RadarDetectionScenario
from phased_array_systems.trades import DesignSpace


@pytest.fixture
def comms_scenario():
    """Standard 10 GHz comms scenario at 100 km range."""
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
def radar_scenario():
    """Standard 10 GHz radar scenario at 50 km range."""
    return RadarDetectionScenario(
        freq_hz=10e9,
        bandwidth_hz=1e6,
        range_m=50e3,
        target_rcs_dbsm=0.0,
        pfa=1e-6,
        pd_required=0.9,
        n_pulses=10,
        integration_type="noncoherent",
    )


@pytest.fixture
def base_architecture():
    """8x8 array with 1W/element and standard RF chain."""
    return Architecture(
        array=ArrayConfig(
            nx=8,
            ny=8,
            dx_lambda=0.5,
            dy_lambda=0.5,
            enforce_subarray_constraint=False,
        ),
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
def basic_requirements():
    """Simple EIRP + cost requirement set."""
    return RequirementSet(
        requirements=[
            Requirement(
                id="REQ-001",
                name="Minimum EIRP",
                metric_key="eirp_dbw",
                op=">=",
                value=30.0,
                severity="must",
            ),
            Requirement(
                id="REQ-002",
                name="Maximum Cost",
                metric_key="cost_usd",
                op="<=",
                value=50000.0,
                severity="must",
            ),
        ],
        name="Basic Requirements",
    )


@pytest.fixture
def architecture_design_space():
    """Design space for array sizing and RF parameters."""
    return (
        DesignSpace(name="Test Design Space")
        .add_variable("array.nx", type="categorical", values=[4, 8, 16])
        .add_variable("array.ny", type="categorical", values=[4, 8, 16])
        .add_variable(
            "array.enforce_subarray_constraint",
            type="categorical",
            values=[True],
        )
        .add_variable("array.geometry", type="categorical", values=["rectangular"])
        .add_variable("rf.tx_power_w_per_elem", type="float", low=0.5, high=3.0)
        .add_variable("rf.pa_efficiency", type="float", low=0.2, high=0.5)
        .add_variable("rf.noise_figure_db", type="float", low=3.0, high=3.0)
        .add_variable("cost.cost_per_elem_usd", type="float", low=75.0, high=150.0)
    )


@pytest.fixture
def configs_dir():
    """Path to example config files."""
    return Path(__file__).parent.parent / "examples" / "configs"
