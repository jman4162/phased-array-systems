"""Batch evaluation runner for DOE trade studies."""

import time
import traceback
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

from phased_array_systems.architecture import Architecture
from phased_array_systems.evaluate import evaluate_case
from phased_array_systems.requirements import RequirementSet
from phased_array_systems.types import Scenario


def _evaluate_single_case(
    case_row: dict,
    scenario: Scenario,
    requirements: RequirementSet | None,
    architecture_builder: Callable[[dict], Architecture],
) -> dict:
    """Worker function to evaluate a single case.

    Args:
        case_row: Dictionary of design variable values
        scenario: Scenario to evaluate against
        requirements: Optional requirements for verification
        architecture_builder: Function to build Architecture from case dict

    Returns:
        Dictionary with case_id, all design variables, and all metrics
    """
    case_id = case_row.get("case_id", "unknown")

    try:
        # Build architecture from case parameters
        arch = architecture_builder(case_row)

        # Evaluate
        metrics = evaluate_case(arch, scenario, requirements, case_id=case_id)

        # Merge case params with metrics
        result = dict(case_row)
        result.update(metrics)
        result["meta.error"] = None

    except Exception as e:
        # Case-level error handling - don't crash the batch
        result = dict(case_row)
        result["meta.error"] = f"{type(e).__name__}: {e}"
        result["meta.traceback"] = traceback.format_exc()
        result["meta.runtime_s"] = 0.0

    return result


class BatchRunner:
    """Parallel batch evaluation of DOE cases.

    Evaluates multiple architecture/scenario combinations with
    case-level error handling, progress reporting, and resume capability.

    Attributes:
        scenario: Scenario to evaluate against
        requirements: Optional requirements for verification
        architecture_builder: Function to build Architecture from case dict
    """

    def __init__(
        self,
        scenario: Scenario,
        requirements: RequirementSet | None = None,
        architecture_builder: Callable[[dict], Architecture] | None = None,
    ):
        """Initialize the batch runner.

        Args:
            scenario: Scenario to evaluate
            requirements: Optional requirements for verification
            architecture_builder: Function to convert case dict to Architecture.
                If None, uses default_architecture_builder.
        """
        self.scenario = scenario
        self.requirements = requirements
        self.architecture_builder = architecture_builder or default_architecture_builder

    def run(
        self,
        cases: pd.DataFrame,
        n_workers: int = 1,
        cache_path: Path | None = None,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> pd.DataFrame:
        """Run batch evaluation.

        Args:
            cases: DataFrame with design variable columns + case_id
            n_workers: Number of parallel workers (1 = sequential)
            cache_path: Optional path to save/load partial results
            progress_callback: Optional callback(completed, total) for progress

        Returns:
            DataFrame with all input columns + all metric columns
        """
        # Load cached results if available
        completed_ids = set()
        cached_results = []

        if cache_path is not None and cache_path.exists():
            try:
                cached_df = pd.read_parquet(cache_path)
                completed_ids = set(cached_df["case_id"])
                cached_results = cached_df.to_dict("records")
                print(f"Resuming: {len(completed_ids)} cases already completed")
            except Exception:
                pass  # Ignore cache errors

        # Filter to uncompleted cases
        cases_to_run = cases[~cases["case_id"].isin(completed_ids)]
        total_cases = len(cases)
        remaining = len(cases_to_run)

        if remaining == 0:
            print("All cases already completed")
            return pd.DataFrame(cached_results)

        print(f"Running {remaining} cases ({len(completed_ids)} cached)")

        # Convert to list of dicts for processing
        case_dicts = cases_to_run.to_dict("records")

        results = list(cached_results)
        start_time = time.perf_counter()

        if n_workers == 1:
            # Sequential execution
            for i, case_row in enumerate(case_dicts):
                result = _evaluate_single_case(
                    case_row,
                    self.scenario,
                    self.requirements,
                    self.architecture_builder,
                )
                results.append(result)

                if progress_callback:
                    progress_callback(len(results), total_cases)

                # Save intermediate results
                if cache_path is not None and (i + 1) % 10 == 0:
                    self._save_cache(results, cache_path)

        else:
            # Parallel execution
            with ProcessPoolExecutor(max_workers=n_workers) as executor:
                futures = {
                    executor.submit(
                        _evaluate_single_case,
                        case_row,
                        self.scenario,
                        self.requirements,
                        self.architecture_builder,
                    ): case_row["case_id"]
                    for case_row in case_dicts
                }

                for future in as_completed(futures):
                    result = future.result()
                    results.append(result)

                    if progress_callback:
                        progress_callback(len(results), total_cases)

                    # Save intermediate results periodically
                    if cache_path is not None and len(results) % 10 == 0:
                        self._save_cache(results, cache_path)

        elapsed = time.perf_counter() - start_time
        print(f"Completed {remaining} cases in {elapsed:.1f}s ({elapsed / remaining:.3f}s/case)")

        # Final save
        if cache_path is not None:
            self._save_cache(results, cache_path)

        # Build result DataFrame
        result_df = pd.DataFrame(results)

        # Ensure consistent column order
        cols = list(cases.columns) + [c for c in result_df.columns if c not in cases.columns]
        result_df = result_df[[c for c in cols if c in result_df.columns]]

        return result_df

    def _save_cache(self, results: list[dict], cache_path: Path) -> None:
        """Save results to cache file."""
        try:
            df = pd.DataFrame(results)
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            df.to_parquet(cache_path)
        except Exception as e:
            print(f"Warning: Failed to save cache: {e}")


def default_architecture_builder(case_row: dict) -> Architecture:
    """Default function to build Architecture from DOE case dictionary.

    Expects keys like "array.nx", "rf.tx_power_w_per_elem", etc.

    Args:
        case_row: Dictionary with dot-notation keys

    Returns:
        Architecture object
    """
    # Filter out non-architecture keys
    arch_keys = {
        k: v for k, v in case_row.items() if k.startswith(("array.", "rf.", "cost.")) or k == "name"
    }

    return Architecture.from_flat(arch_keys)


def run_batch_simple(
    cases: pd.DataFrame,
    scenario: Scenario,
    requirements: RequirementSet | None = None,
    n_workers: int = 1,
) -> pd.DataFrame:
    """Simple batch run without caching or progress.

    Convenience function for basic batch evaluation.

    Args:
        cases: DataFrame with design variable columns
        scenario: Scenario to evaluate
        requirements: Optional requirements
        n_workers: Number of parallel workers

    Returns:
        Results DataFrame
    """
    runner = BatchRunner(scenario, requirements)
    return runner.run(cases, n_workers=n_workers)
