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
