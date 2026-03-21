"""Tests for the architecture configuration subsystem."""

import pytest
from pydantic import ValidationError

from phased_array_systems.architecture import (
    Architecture,
    ArrayConfig,
    CostConfig,
    RFChainConfig,
)


class TestArrayConfig:
    """Tests for ArrayConfig."""

    def test_default_values(self):
        config = ArrayConfig(nx=8, ny=8)
        assert config.geometry == "rectangular"
        assert config.dx_lambda == 0.5
        assert config.dy_lambda == 0.5
        assert config.scan_limit_deg == 60.0

    def test_n_elements(self):
        config = ArrayConfig(nx=8, ny=16)
        assert config.n_elements == 128

    def test_invalid_nx(self):
        with pytest.raises(ValidationError):
            ArrayConfig(nx=0, ny=8)

    def test_invalid_spacing(self):
        with pytest.raises(ValidationError):
            ArrayConfig(nx=8, ny=8, dx_lambda=-0.5)

    def test_invalid_scan_limit(self):
        with pytest.raises(ValidationError):
            ArrayConfig(nx=8, ny=8, scan_limit_deg=95.0)


class TestSubarrayConstraints:
    """Tests for sub-array constraints (power-of-two)."""

    def test_default_subarray_values(self):
        """Test default sub-array constraint values."""
        config = ArrayConfig(nx=8, ny=8)
        assert config.max_subarray_nx == 8
        assert config.max_subarray_ny == 8
        assert config.enforce_subarray_constraint is True

    def test_subarray_properties_small_array(self):
        """Test sub-array properties for array smaller than max."""
        config = ArrayConfig(nx=4, ny=4)
        assert config.subarray_nx == 4
        assert config.subarray_ny == 4
        assert config.n_subarrays_x == 1
        assert config.n_subarrays_y == 1
        assert config.n_subarrays == 1
        assert config.elements_per_subarray == 16

    def test_subarray_properties_large_array(self):
        """Test sub-array properties for array larger than max."""
        config = ArrayConfig(nx=16, ny=32, max_subarray_nx=8, max_subarray_ny=8)
        assert config.subarray_nx == 8
        assert config.subarray_ny == 8
        assert config.n_subarrays_x == 2
        assert config.n_subarrays_y == 4
        assert config.n_subarrays == 8
        assert config.elements_per_subarray == 64

    def test_subarray_constraint_enforced_valid(self):
        """Test valid array dimensions with constraint enforced."""
        # 16 is divisible by 8 and both are powers of 2
        config = ArrayConfig(nx=16, ny=16, max_subarray_nx=8, max_subarray_ny=8)
        assert config.n_subarrays == 4

    def test_subarray_constraint_invalid_not_power_of_two_small(self):
        """Test that non-power-of-two small array raises error."""
        # nx=6 is not a power of 2
        with pytest.raises(ValidationError, match="nx=6 must be a power of 2"):
            ArrayConfig(nx=6, ny=8, max_subarray_nx=8, max_subarray_ny=8)

    def test_subarray_constraint_invalid_not_divisible(self):
        """Test that non-divisible large array raises error."""
        # nx=12 is larger than 8 but not divisible by 8
        with pytest.raises(ValidationError, match="nx=12 must be divisible by"):
            ArrayConfig(nx=12, ny=8, max_subarray_nx=8, max_subarray_ny=8)

    def test_max_subarray_must_be_power_of_two(self):
        """Test that max_subarray values must be powers of two."""
        with pytest.raises(ValidationError, match="must be a power of 2"):
            ArrayConfig(nx=8, ny=8, max_subarray_nx=6, max_subarray_ny=8)

    def test_subarray_constraint_disabled(self):
        """Test that constraint can be disabled."""
        # This would fail with constraint enabled (10, 12 not powers of 2)
        config = ArrayConfig(
            nx=10, ny=12, max_subarray_nx=8, max_subarray_ny=8, enforce_subarray_constraint=False
        )
        assert config.nx == 10
        assert config.ny == 12
        assert config.n_subarrays_x == 2  # ceil(10/8)
        assert config.n_subarrays_y == 2  # ceil(12/8)

    def test_custom_subarray_size_power_of_two(self):
        """Test custom sub-array sizes (must be powers of two)."""
        config = ArrayConfig(nx=16, ny=16, max_subarray_nx=4, max_subarray_ny=4)
        assert config.n_subarrays_x == 4
        assert config.n_subarrays_y == 4
        assert config.n_subarrays == 16

    def test_non_rectangular_skips_constraint(self):
        """Test that non-rectangular geometries skip constraint validation."""
        # This would fail for rectangular with constraint enforced
        config = ArrayConfig(
            nx=10,
            ny=12,
            geometry="circular",
            max_subarray_nx=8,
            max_subarray_ny=8,
            enforce_subarray_constraint=True,
        )
        assert config.nx == 10
        assert config.ny == 12

    def test_valid_power_of_two_sizes(self):
        """Test various valid power-of-two array sizes."""
        for size in [2, 4, 8, 16, 32]:
            config = ArrayConfig(nx=size, ny=size)
            assert config.nx == size
            assert config.ny == size

    def test_large_array_multiple_subarrays(self):
        """Test large array with multiple sub-arrays."""
        config = ArrayConfig(nx=64, ny=32, max_subarray_nx=16, max_subarray_ny=8)
        assert config.n_subarrays_x == 4  # 64/16
        assert config.n_subarrays_y == 4  # 32/8
        assert config.n_subarrays == 16
        assert config.elements_per_subarray == 128  # 16*8


class TestRFChainConfig:
    """Tests for RFChainConfig."""

    def test_default_values(self):
        config = RFChainConfig(tx_power_w_per_elem=1.0)
        assert config.pa_efficiency == 0.3
        assert config.noise_figure_db == 3.0
        assert config.n_tx_beams == 1
        assert config.feed_loss_db == 1.0

    def test_invalid_efficiency(self):
        with pytest.raises(ValidationError):
            RFChainConfig(tx_power_w_per_elem=1.0, pa_efficiency=1.5)

    def test_invalid_power(self):
        with pytest.raises(ValidationError):
            RFChainConfig(tx_power_w_per_elem=0)


class TestCostConfig:
    """Tests for CostConfig."""

    def test_default_values(self):
        config = CostConfig()
        assert config.cost_per_elem_usd == 100.0
        assert config.nre_usd == 0.0
        assert config.integration_cost_usd == 0.0

    def test_custom_values(self):
        config = CostConfig(
            cost_per_elem_usd=150.0,
            nre_usd=50000.0,
            integration_cost_usd=10000.0,
        )
        assert config.cost_per_elem_usd == 150.0
        assert config.nre_usd == 50000.0


class TestArchitecture:
    """Tests for the Architecture class."""

    @pytest.fixture
    def sample_architecture(self):
        return Architecture(
            array=ArrayConfig(nx=8, ny=8),
            rf=RFChainConfig(tx_power_w_per_elem=1.0),
            cost=CostConfig(cost_per_elem_usd=100.0),
            name="Test Array",
        )

    def test_create_architecture(self, sample_architecture):
        assert sample_architecture.array.nx == 8
        assert sample_architecture.rf.tx_power_w_per_elem == 1.0
        assert sample_architecture.n_elements == 64
        assert sample_architecture.name == "Test Array"

    def test_default_cost(self):
        arch = Architecture(
            array=ArrayConfig(nx=4, ny=4),
            rf=RFChainConfig(tx_power_w_per_elem=0.5),
        )
        assert arch.cost.cost_per_elem_usd == 100.0

    def test_model_dump_flat(self, sample_architecture):
        flat = sample_architecture.model_dump_flat()

        assert flat["array.nx"] == 8
        assert flat["array.ny"] == 8
        assert flat["rf.tx_power_w_per_elem"] == 1.0
        assert flat["cost.cost_per_elem_usd"] == 100.0
        assert flat["name"] == "Test Array"

    def test_from_flat(self):
        flat_dict = {
            "array.nx": 16,
            "array.ny": 16,
            "array.geometry": "rectangular",
            "array.dx_lambda": 0.5,
            "array.dy_lambda": 0.5,
            "array.scan_limit_deg": 45.0,
            "rf.tx_power_w_per_elem": 2.0,
            "rf.pa_efficiency": 0.4,
            "rf.noise_figure_db": 2.5,
            "rf.n_tx_beams": 1,
            "rf.feed_loss_db": 0.5,
            "rf.system_loss_db": 0.0,
            "cost.cost_per_elem_usd": 200.0,
            "cost.nre_usd": 10000.0,
            "cost.integration_cost_usd": 5000.0,
            "name": "From Flat",
        }

        arch = Architecture.from_flat(flat_dict)

        assert arch.array.nx == 16
        assert arch.array.scan_limit_deg == 45.0
        assert arch.rf.tx_power_w_per_elem == 2.0
        assert arch.cost.cost_per_elem_usd == 200.0
        assert arch.name == "From Flat"

    def test_round_trip_flat(self, sample_architecture):
        """Test that from_flat(model_dump_flat()) returns equivalent architecture."""
        flat = sample_architecture.model_dump_flat()
        reconstructed = Architecture.from_flat(flat)

        assert reconstructed.array.nx == sample_architecture.array.nx
        assert reconstructed.rf.tx_power_w_per_elem == sample_architecture.rf.tx_power_w_per_elem
        assert reconstructed.cost.cost_per_elem_usd == sample_architecture.cost.cost_per_elem_usd
