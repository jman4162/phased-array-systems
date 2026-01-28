"""Single-case evaluation orchestrator."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from phased_array_systems.architecture import Architecture
from phased_array_systems.models.antenna import PhasedArrayAdapter
from phased_array_systems.models.comms import CommsLinkModel
from phased_array_systems.models.radar import RadarModel
from phased_array_systems.models.swapc import CostModel, PowerModel
from phased_array_systems.requirements import RequirementSet, VerificationReport
from phased_array_systems.scenarios import CommsLinkScenario, RadarDetectionScenario
from phased_array_systems.types import MetricsDict, Scenario

if TYPE_CHECKING:
    from phased_array_systems.io.schema import StudyConfig


def evaluate_case(
    arch: Architecture,
    scenario: Scenario,
    requirements: RequirementSet | None = None,
    case_id: str | None = None,
) -> MetricsDict:
    """Evaluate a single architecture/scenario case.

    Runs all applicable models and returns merged metrics dictionary.
    Optionally verifies against requirements and includes verification results.

    Args:
        arch: Architecture configuration
        scenario: Scenario configuration (CommsLinkScenario or RadarDetectionScenario)
        requirements: Optional requirement set for verification
        case_id: Optional case identifier for tracking

    Returns:
        Dictionary containing all computed metrics plus metadata:
            - All antenna metrics (g_peak_db, beamwidth_*, sll_db, etc.)
            - All link/radar metrics (eirp_dbw, snr_*, margin_*, etc.)
            - All SWaP-C metrics (power_*, cost_*)
            - Verification results if requirements provided
            - Metadata (case_id, runtime_s)
    """
    start_time = time.perf_counter()
    metrics: MetricsDict = {}

    # Add case ID if provided
    if case_id is not None:
        metrics["meta.case_id"] = case_id

    # Initialize models
    antenna_model = PhasedArrayAdapter(use_analytical_fallback=True)
    power_model = PowerModel()
    cost_model = CostModel()

    # Evaluate antenna model first (provides gain for link budget)
    antenna_metrics = antenna_model.evaluate(arch, scenario, {})
    metrics.update(antenna_metrics)

    # Create context with antenna results for downstream models
    context: dict[str, Any] = dict(antenna_metrics)

    # Evaluate SWaP-C models
    power_metrics = power_model.evaluate(arch, scenario, context)
    metrics.update(power_metrics)

    cost_metrics = cost_model.evaluate(arch, scenario, context)
    metrics.update(cost_metrics)

    # Evaluate scenario-specific models
    if isinstance(scenario, CommsLinkScenario):
        comms_model = CommsLinkModel()
        comms_metrics = comms_model.evaluate(arch, scenario, context)
        metrics.update(comms_metrics)
    elif isinstance(scenario, RadarDetectionScenario):
        radar_model = RadarModel()
        radar_metrics = radar_model.evaluate(arch, scenario, context)
        metrics.update(radar_metrics)

    # Verify requirements if provided
    if requirements is not None and len(requirements) > 0:
        report = requirements.verify(metrics)
        metrics["verification.passes"] = 1.0 if report.passes else 0.0
        metrics["verification.must_pass_count"] = float(report.must_pass_count)
        metrics["verification.must_total_count"] = float(report.must_total_count)
        metrics["verification.failed_ids"] = ",".join(report.failed_ids) if report.failed_ids else ""

    # Add timing metadata
    elapsed = time.perf_counter() - start_time
    metrics["meta.runtime_s"] = elapsed

    return metrics


def evaluate_case_with_report(
    arch: Architecture,
    scenario: Scenario,
    requirements: RequirementSet,
    case_id: str | None = None,
) -> tuple[MetricsDict, VerificationReport]:
    """Evaluate a case and return both metrics and full verification report.

    Args:
        arch: Architecture configuration
        scenario: Scenario configuration
        requirements: Requirement set for verification
        case_id: Optional case identifier

    Returns:
        Tuple of (metrics dict, VerificationReport)
    """
    metrics = evaluate_case(arch, scenario, requirements, case_id)
    report = requirements.verify(metrics)
    return metrics, report


def evaluate_config(config: StudyConfig) -> MetricsDict:
    """Evaluate a case from a StudyConfig object.

    Convenience function for config-driven evaluation.

    Args:
        config: StudyConfig object with architecture, scenario, requirements

    Returns:
        Metrics dictionary
    """

    arch = config.get_architecture()
    scenario = config.get_scenario()
    requirements = config.get_requirement_set()

    if scenario is None:
        raise ValueError("StudyConfig must have a scenario defined")

    return evaluate_case(arch, scenario, requirements, case_id=config.name)
