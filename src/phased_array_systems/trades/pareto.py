"""Pareto frontier extraction and analysis utilities."""

from typing import Literal, cast

import numpy as np
import pandas as pd

from phased_array_systems.requirements import RequirementSet
from phased_array_systems.types import MetricsDict, OptimizeDirection


def filter_feasible(
    results: pd.DataFrame,
    requirements: RequirementSet | None = None,
    verification_column: str = "verification.passes",
) -> pd.DataFrame:
    """Filter results to only feasible (requirement-passing) designs.

    Args:
        results: DataFrame with evaluation results
        requirements: Optional RequirementSet to verify against
        verification_column: Column name for verification status

    Returns:
        DataFrame containing only feasible designs
    """
    if requirements is not None and len(requirements) > 0:
        # Re-verify against requirements
        mask = []
        for _, row in results.iterrows():
            metrics = cast("MetricsDict", {str(k): v for k, v in row.to_dict().items()})
            report = requirements.verify(metrics)
            mask.append(report.passes)
        return results[mask].copy()

    elif verification_column in results.columns:
        # Use pre-computed verification
        return results[results[verification_column] == 1.0].copy()

    else:
        # No filtering - return all
        return results.copy()


def extract_pareto(
    results: pd.DataFrame,
    objectives: list[tuple[str, OptimizeDirection]],
    include_dominated: bool = False,
) -> pd.DataFrame:
    """Extract Pareto-optimal designs from results.

    A design is Pareto-optimal if no other design is better in all objectives.

    Args:
        results: DataFrame with evaluation results
        objectives: List of (column_name, direction) tuples where direction
            is "minimize" or "maximize"
        include_dominated: If True, include a 'pareto_optimal' column marking
            Pareto-optimal rows

    Returns:
        DataFrame containing only Pareto-optimal designs (or all designs
        with pareto_optimal column if include_dominated=True)

    Examples:
        >>> pareto = extract_pareto(results, [
        ...     ("cost_usd", "minimize"),
        ...     ("eirp_dbw", "maximize"),
        ... ])
    """
    if len(results) == 0:
        return results.copy()

    # Convert to minimization (negate maximization objectives)
    obj_matrix = np.zeros((len(results), len(objectives)))
    for i, (name, direction) in enumerate(objectives):
        values = np.asarray(results[name].values, dtype=float)
        if direction == "maximize":
            obj_matrix[:, i] = -values
        else:
            obj_matrix[:, i] = values

    # Find Pareto-optimal points
    is_pareto = np.ones(len(results), dtype=bool)

    for i in range(len(results)):
        if not is_pareto[i]:
            continue

        # Check if any other point dominates point i
        for j in range(len(results)):
            if i == j or not is_pareto[j]:
                continue

            # j dominates i if j is <= in all objectives and < in at least one
            all_leq = np.all(obj_matrix[j] <= obj_matrix[i])
            any_lt = np.any(obj_matrix[j] < obj_matrix[i])

            if all_leq and any_lt:
                is_pareto[i] = False
                break

    if include_dominated:
        result_df = results.copy()
        result_df["pareto_optimal"] = is_pareto
        return result_df
    else:
        return results[is_pareto].copy()


def rank_pareto(
    pareto: pd.DataFrame,
    objectives: list[tuple[str, OptimizeDirection]],
    weights: list[float] | None = None,
    method: Literal["weighted_sum", "topsis"] = "weighted_sum",
) -> pd.DataFrame:
    """Rank Pareto-optimal designs using weighted objectives.

    Args:
        pareto: DataFrame with Pareto-optimal designs
        objectives: List of (column_name, direction) tuples
        weights: Weights for each objective (default: equal weights)
        method: Ranking method ("weighted_sum" or "topsis")

    Returns:
        DataFrame with added 'rank' and 'score' columns, sorted by rank
    """
    if len(pareto) == 0:
        return pareto.copy()

    n_obj = len(objectives)
    if weights is None:
        weights = [1.0 / n_obj] * n_obj
    else:
        # Normalize weights
        total = sum(weights)
        weights = [w / total for w in weights]

    # Extract and normalize objective values
    obj_matrix = np.zeros((len(pareto), n_obj))
    for i, (name, direction) in enumerate(objectives):
        values = np.asarray(pareto[name].values, dtype=float)
        # Normalize to [0, 1]
        min_val, max_val = values.min(), values.max()
        if max_val > min_val:
            normalized = (values - min_val) / (max_val - min_val)
        else:
            normalized = np.zeros_like(values)

        # Flip for maximization (higher is better -> lower normalized score)
        if direction == "maximize":
            normalized = 1 - normalized

        obj_matrix[:, i] = normalized

    if method == "weighted_sum":
        # Weighted sum (lower is better)
        scores = np.sum(obj_matrix * weights, axis=1)

    elif method == "topsis":
        # TOPSIS method
        # Ideal point: min of all (already normalized to minimization)
        ideal = np.zeros(n_obj)
        # Anti-ideal: max of all
        anti_ideal = np.ones(n_obj)

        # Distance to ideal and anti-ideal
        d_ideal = np.sqrt(np.sum(weights * (obj_matrix - ideal) ** 2, axis=1))
        d_anti = np.sqrt(np.sum(weights * (obj_matrix - anti_ideal) ** 2, axis=1))

        # TOPSIS score (higher is better, so negate for ranking)
        with np.errstate(divide="ignore", invalid="ignore"):
            scores = d_ideal / (d_ideal + d_anti)
            scores = np.nan_to_num(scores, nan=1.0)

    else:
        raise ValueError(f"Unknown ranking method: {method}")

    # Add scores and rank
    result_df = pareto.copy()
    result_df["pareto_score"] = scores
    result_df["pareto_rank"] = result_df["pareto_score"].rank(method="min").astype(int)

    return result_df.sort_values("pareto_rank")


def compute_hypervolume(
    pareto: pd.DataFrame,
    objectives: list[tuple[str, OptimizeDirection]],
    reference_point: list[float] | None = None,
) -> float:
    """Compute hypervolume indicator for a Pareto front.

    The hypervolume is the volume of objective space dominated by the
    Pareto front, bounded by a reference point. Higher is better.

    Args:
        pareto: DataFrame with Pareto-optimal designs
        objectives: List of (column_name, direction) tuples
        reference_point: Reference point in objective space (default: worst point + 10%)

    Returns:
        Hypervolume value

    Note:
        For >3 objectives, this uses a simple approximation.
    """
    if len(pareto) == 0:
        return 0.0

    n_obj = len(objectives)

    # Extract objective values (convert to minimization)
    obj_matrix = np.zeros((len(pareto), n_obj))
    for i, (name, direction) in enumerate(objectives):
        values = np.asarray(pareto[name].values, dtype=float)
        if direction == "maximize":
            obj_matrix[:, i] = -values
        else:
            obj_matrix[:, i] = values

    # Set reference point if not provided
    if reference_point is None:
        worst = obj_matrix.max(axis=0)
        reference_point = worst * 1.1 + 0.1  # 10% beyond worst

    ref = np.array(reference_point)

    # For 2D, compute exact hypervolume
    if n_obj == 2:
        # Sort by first objective
        sorted_idx = np.argsort(obj_matrix[:, 0])
        sorted_obj = obj_matrix[sorted_idx]

        hv = 0.0
        prev_y = ref[1]
        for i in range(len(sorted_obj)):
            x, y = sorted_obj[i]
            if x < ref[0] and y < ref[1]:
                hv += (ref[0] - x) * (prev_y - y)
                prev_y = y

        return float(hv)

    else:
        # Monte Carlo approximation for higher dimensions
        n_samples = 10000
        rng = np.random.default_rng(42)

        # Sample random points in hyperbox
        samples = np.zeros((n_samples, n_obj))
        for i in range(n_obj):
            min_val = obj_matrix[:, i].min()
            samples[:, i] = rng.uniform(min_val, ref[i], n_samples)

        # Count points dominated by at least one Pareto point
        dominated = np.zeros(n_samples, dtype=bool)
        for pareto_point in obj_matrix:
            is_dominated = np.all(samples >= pareto_point, axis=1)
            dominated |= is_dominated

        # Estimate hypervolume
        box_volume = np.prod(ref - obj_matrix.min(axis=0))
        hv = box_volume * dominated.sum() / n_samples

        return float(hv)
