"""One-at-a-time (OAT) sensitivity analysis for trade studies."""

from __future__ import annotations

import copy
from typing import Any

import pandas as pd

from phased_array_systems.architecture import Architecture
from phased_array_systems.evaluate import evaluate_case
from phased_array_systems.requirements import RequirementSet
from phased_array_systems.types import Scenario


def _set_nested_attr(obj: Any, dotted_key: str, value: Any) -> Any:
    """Set a nested attribute using dot notation (e.g., 'array.nx').

    Returns a deep copy of the object with the attribute modified.
    """
    obj = copy.deepcopy(obj)
    parts = dotted_key.split(".")

    current = obj
    for part in parts[:-1]:
        current = getattr(current, part)

    setattr(current, parts[-1], value)
    return obj


def oat_sensitivity(
    arch: Architecture,
    scenario: Scenario,
    param_ranges: dict[str, list[float]],
    metric_keys: list[str] | None = None,
    requirements: RequirementSet | None = None,
    n_steps: int = 5,
) -> pd.DataFrame:
    """Run one-at-a-time sensitivity analysis.

    Sweeps each parameter independently while holding others at baseline.
    Returns sensitivity coefficients for each parameter/metric pair.

    Args:
        arch: Baseline architecture configuration
        scenario: Baseline scenario configuration
        param_ranges: Dict mapping parameter names (dot notation, e.g. 'array.nx')
            to [min, max] range. Parameters starting with 'scenario.' are
            applied to the scenario object.
        metric_keys: List of output metric keys to track. If None, uses
            common defaults (g_peak_db, sll_db, eirp_dbw, etc.)
        requirements: Optional requirements for verification
        n_steps: Number of steps per parameter sweep

    Returns:
        DataFrame with columns: parameter, value, and one column per metric key.
        Also includes a 'baseline' row for each parameter showing the center value.
    """
    if metric_keys is None:
        metric_keys = [
            "g_peak_db",
            "sll_db",
            "beamwidth_az_deg",
            "eirp_dbw",
            "link_margin_db",
            "snr_rx_db",
            "cost_usd",
            "prime_power_w",
        ]

    # Evaluate baseline
    baseline_metrics = evaluate_case(arch, scenario, requirements)

    rows: list[dict[str, Any]] = []

    for param_name, (lo, hi) in param_ranges.items():
        import numpy as np

        sweep_values = np.linspace(lo, hi, n_steps).tolist()

        for val in sweep_values:
            # Determine if parameter is on arch or scenario
            if param_name.startswith("scenario."):
                actual_key = param_name[len("scenario.") :]
                sweep_arch = arch
                sweep_scenario = _set_nested_attr(scenario, actual_key, val)
            else:
                sweep_arch = _set_nested_attr(arch, param_name, val)
                sweep_scenario = scenario

            try:
                metrics = evaluate_case(sweep_arch, sweep_scenario, requirements)
            except Exception:
                # Skip invalid parameter combinations
                continue

            row: dict[str, Any] = {"parameter": param_name, "value": val}
            for mk in metric_keys:
                row[mk] = metrics.get(mk, float("nan"))
                row[f"{mk}_baseline"] = baseline_metrics.get(mk, float("nan"))
            rows.append(row)

    return pd.DataFrame(rows)


def compute_sensitivity_coefficients(
    sensitivity_df: pd.DataFrame,
    metric_keys: list[str] | None = None,
) -> pd.DataFrame:
    """Compute normalized sensitivity coefficients from OAT sweep results.

    For each parameter, computes:
        S = (metric_max - metric_min) / |metric_baseline|

    This gives the fractional change in the metric across the swept range.

    Args:
        sensitivity_df: Output of oat_sensitivity()
        metric_keys: Metric columns to analyze (auto-detected if None)

    Returns:
        DataFrame with columns: parameter, metric, delta, baseline, sensitivity
    """
    if metric_keys is None:
        # Auto-detect metric columns
        metric_keys = [
            c
            for c in sensitivity_df.columns
            if c not in ("parameter", "value") and not c.endswith("_baseline")
        ]

    rows = []
    for param, group in sensitivity_df.groupby("parameter"):
        for mk in metric_keys:
            if mk not in group.columns:
                continue
            values = group[mk].dropna()
            if len(values) < 2:
                continue

            baseline_col = f"{mk}_baseline"
            baseline = (
                group[baseline_col].iloc[0] if baseline_col in group.columns else values.mean()
            )

            delta = values.max() - values.min()
            sensitivity = delta / abs(baseline) if baseline != 0 else float("inf")

            rows.append(
                {
                    "parameter": param,
                    "metric": mk,
                    "delta": delta,
                    "baseline": baseline,
                    "sensitivity": sensitivity,
                    "metric_min": values.min(),
                    "metric_max": values.max(),
                }
            )

    return pd.DataFrame(rows)


def sobol_sensitivity(
    design_space: Any,
    scenario: Scenario,
    metric_keys: list[str],
    requirements: RequirementSet | None = None,
    base_config: dict[str, Any] | None = None,
    n_base: int = 256,
    seed: int | None = None,
    n_workers: int = 1,
) -> pd.DataFrame:
    """Global Sobol sensitivity indices via SALib Saltelli sampling.

    Unlike one-at-a-time sweeps, Sobol indices capture interaction
    effects: S1 is the first-order share of output variance, ST the
    total share including interactions. Requires the optional [mdao]
    extra (pip install "phased-array-systems[mdao]").

    Args:
        design_space: DesignSpace with float/int variables only
            (categorical variables are not supported by variance-based
            sensitivity; encode them as separate studies)
        scenario: Scenario to evaluate against
        metric_keys: Output metrics to analyze
        requirements: Optional requirements (verification metrics added)
        base_config: Constant architecture fields (e.g. {"array.nx": 8})
            added as fixed columns to every sampled case
        n_base: Saltelli base sample count (total runs = n_base * (2D + 2));
            powers of two converge best
        seed: Random seed for reproducibility
        n_workers: Parallel workers for the batch evaluation

    Returns:
        DataFrame with columns: parameter, metric, S1, S1_conf, ST, ST_conf

    Raises:
        ImportError: If SALib is not installed
        ValueError: If the design space contains categorical variables
    """
    try:
        from SALib.analyze import sobol as sobol_analyze
        from SALib.sample import sobol as sobol_sample
    except ImportError as e:  # pragma: no cover
        raise ImportError(
            "SALib is required for sobol_sensitivity. Install the MDAO "
            'extra: pip install "phased-array-systems[mdao]"'
        ) from e

    import numpy as np

    from phased_array_systems.trades.runner import BatchRunner

    for var in design_space.variables:
        if var.type == "categorical":
            raise ValueError(
                f"Variable '{var.name}' is categorical; Sobol indices need "
                "numeric variables (run one study per category instead)"
            )
        if var.low == var.high:
            raise ValueError(
                f"Variable '{var.name}' has degenerate bounds; move fixed "
                "values into base_config instead"
            )

    problem = {
        "num_vars": design_space.n_dims,
        "names": design_space.variable_names,
        "bounds": [[float(v.low), float(v.high)] for v in design_space.variables],
    }

    samples = sobol_sample.sample(problem, n_base, calc_second_order=False, seed=seed)

    # Round integer variables to valid values (SALib samples continuously)
    cases = pd.DataFrame(samples, columns=design_space.variable_names)
    for var in design_space.variables:
        if var.type == "int":
            cases[var.name] = cases[var.name].round().astype(int)
    for key, value in (base_config or {}).items():
        cases[key] = value
    cases.insert(0, "case_id", [f"case_{i:05d}" for i in range(len(cases))])

    runner = BatchRunner(scenario, requirements)
    results = runner.run(cases, n_workers=n_workers)

    if "meta.error" in results.columns:
        failed_frac = float(results["meta.error"].notna().mean())
        if failed_frac > 0.5:
            raise ValueError(
                f"{failed_frac:.0%} of Saltelli samples failed evaluation. "
                "Variance-based sensitivity needs a (nearly) rectangular "
                "feasible domain; exclude constrained integer variables "
                "(e.g. array.nx under the sub-array rule) or disable the "
                "constraint via base_config."
            )
        if failed_frac > 0:
            import warnings

            warnings.warn(
                f"{failed_frac:.1%} of samples failed evaluation; their "
                "outputs are imputed with the column mean, diluting the "
                "indices.",
                stacklevel=2,
            )

    rows: list[dict[str, Any]] = []
    for metric in metric_keys:
        if metric not in results.columns:
            continue
        y = results[metric].to_numpy(dtype=float)
        if np.isnan(y).all():
            continue
        if np.isnan(y).any():
            # SALib cannot handle NaN outputs; substitute the column mean
            # (cases that failed evaluation dilute, not break, the indices)
            y = np.where(np.isnan(y), np.nanmean(y), y)
        si = sobol_analyze.analyze(problem, y, calc_second_order=False, seed=seed)
        for i, name in enumerate(design_space.variable_names):
            rows.append(
                {
                    "parameter": name,
                    "metric": metric,
                    "S1": float(si["S1"][i]),
                    "S1_conf": float(si["S1_conf"][i]),
                    "ST": float(si["ST"][i]),
                    "ST_conf": float(si["ST_conf"][i]),
                }
            )

    return pd.DataFrame(rows)
