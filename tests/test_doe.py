"""Tests for DOE generation."""

import pytest

from phased_array_systems.trades.design_space import DesignSpace, DesignVariable
from phased_array_systems.trades.doe import augment_doe, generate_doe, generate_doe_from_dict


class TestDesignVariable:
    """Tests for DesignVariable."""

    def test_float_variable(self):
        var = DesignVariable(name="x", type="float", low=0.0, high=1.0)
        assert var.name == "x"
        assert var.type == "float"
        assert var.low == 0.0
        assert var.high == 1.0

    def test_int_variable(self):
        var = DesignVariable(name="n", type="int", low=4, high=16)
        assert var.type == "int"

    def test_categorical_variable(self):
        var = DesignVariable(name="geom", type="categorical", values=["rect", "circ"])
        assert var.type == "categorical"
        assert len(var.values) == 2

    def test_missing_bounds_raises(self):
        with pytest.raises(ValueError):
            DesignVariable(name="x", type="float", low=0.0)  # Missing high

    def test_invalid_bounds_raises(self):
        with pytest.raises(ValueError):
            DesignVariable(name="x", type="float", low=10.0, high=0.0)  # low > high

    def test_categorical_missing_values_raises(self):
        with pytest.raises(ValueError):
            DesignVariable(name="x", type="categorical")


class TestDesignSpace:
    """Tests for DesignSpace."""

    @pytest.fixture
    def sample_space(self):
        return (
            DesignSpace(name="Test Space")
            .add_variable("x", "float", low=0.0, high=1.0)
            .add_variable("n", "int", low=4, high=8)
            .add_variable("geom", "categorical", values=["rect", "circ"])
        )

    def test_add_variable(self, sample_space):
        assert len(sample_space.variables) == 3
        assert sample_space.n_dims == 3

    def test_variable_names(self, sample_space):
        assert sample_space.variable_names == ["x", "n", "geom"]

    def test_get_variable(self, sample_space):
        var = sample_space.get_variable("n")
        assert var is not None
        assert var.type == "int"

        var_none = sample_space.get_variable("nonexistent")
        assert var_none is None


class TestGenerateDOE:
    """Tests for DOE generation."""

    @pytest.fixture
    def simple_space(self):
        return (
            DesignSpace()
            .add_variable("x", "float", low=0.0, high=10.0)
            .add_variable("y", "float", low=0.0, high=5.0)
        )

    def test_lhs_sampling(self, simple_space):
        doe = generate_doe(simple_space, method="lhs", n_samples=20, seed=42)

        assert len(doe) == 20
        assert "case_id" in doe.columns
        assert "x" in doe.columns
        assert "y" in doe.columns

        # Check bounds
        assert doe["x"].min() >= 0.0
        assert doe["x"].max() <= 10.0
        assert doe["y"].min() >= 0.0
        assert doe["y"].max() <= 5.0

    def test_random_sampling(self, simple_space):
        doe = generate_doe(simple_space, method="random", n_samples=50, seed=123)

        assert len(doe) == 50
        assert doe["x"].min() >= 0.0
        assert doe["x"].max() <= 10.0

    def test_grid_sampling(self, simple_space):
        doe = generate_doe(simple_space, method="grid", grid_levels=5)

        # 5 levels * 5 levels = 25 cases
        assert len(doe) == 25
        assert "case_id" in doe.columns

    def test_grid_with_different_levels(self):
        space = (
            DesignSpace()
            .add_variable("x", "float", low=0.0, high=1.0)
            .add_variable("y", "float", low=0.0, high=1.0)
        )
        doe = generate_doe(space, method="grid", grid_levels=[3, 4])

        # 3 * 4 = 12 cases
        assert len(doe) == 12

    def test_seed_reproducibility(self, simple_space):
        doe1 = generate_doe(simple_space, method="lhs", n_samples=10, seed=42)
        doe2 = generate_doe(simple_space, method="lhs", n_samples=10, seed=42)

        assert doe1["x"].tolist() == doe2["x"].tolist()
        assert doe1["y"].tolist() == doe2["y"].tolist()

    def test_integer_variable(self):
        space = DesignSpace().add_variable("n", "int", low=4, high=16)

        doe = generate_doe(space, method="lhs", n_samples=20, seed=42)

        # All values should be integers
        assert all(isinstance(v, (int, type(doe["n"].iloc[0]))) for v in doe["n"])
        # Within bounds
        assert all(4 <= v <= 16 for v in doe["n"])

    def test_categorical_variable(self):
        space = DesignSpace().add_variable("geom", "categorical", values=["rect", "circ", "tri"])

        doe = generate_doe(space, method="random", n_samples=30, seed=42)

        # All values should be from allowed set
        assert all(v in ["rect", "circ", "tri"] for v in doe["geom"])


class TestGenerateDOEFromDict:
    """Tests for dictionary-based DOE generation."""

    def test_simple_dict(self):
        doe = generate_doe_from_dict(
            {
                "x": (0.0, 10.0),
                "y": (0.0, 5.0, "float"),
            },
            n_samples=20,
            seed=42,
        )

        assert len(doe) == 20
        assert "x" in doe.columns
        assert "y" in doe.columns

    def test_mixed_types(self):
        doe = generate_doe_from_dict(
            {
                "n": (4, 16, "int"),
                "power": (0.5, 2.0),
                "geom": ["rect", "circ"],
            },
            n_samples=50,
            seed=42,
        )

        assert len(doe) == 50
        assert all(v in ["rect", "circ"] for v in doe["geom"])


class TestAugmentDOE:
    """Tests for DOE augmentation."""

    def test_augment_adds_samples(self):
        space = DesignSpace().add_variable("x", "float", low=0.0, high=1.0)

        original = generate_doe(space, n_samples=10, seed=42)
        augmented = augment_doe(original, space, n_additional=5, seed=123)

        assert len(augmented) == 15

    def test_augment_preserves_original(self):
        space = DesignSpace().add_variable("x", "float", low=0.0, high=1.0)

        original = generate_doe(space, n_samples=10, seed=42)
        original_x = original["x"].tolist()

        augmented = augment_doe(original, space, n_additional=5, seed=123)

        # First 10 rows should be unchanged
        assert augmented["x"][:10].tolist() == original_x

    def test_augment_unique_case_ids(self):
        space = DesignSpace().add_variable("x", "float", low=0.0, high=1.0)

        original = generate_doe(space, n_samples=10, seed=42)
        augmented = augment_doe(original, space, n_additional=5, seed=123)

        # All case IDs should be unique
        assert len(augmented["case_id"].unique()) == 15

    def test_augment_draws_new_points(self):
        """Augmenting with the same seed must not repeat the original draws."""
        space = DesignSpace().add_variable("x", "float", low=0.0, high=1.0)

        original = generate_doe(space, n_samples=10, seed=42)
        augmented = augment_doe(original, space, n_additional=10, seed=42)

        new_x = set(augmented["x"][10:].tolist())
        assert new_x.isdisjoint(set(original["x"].tolist()))
