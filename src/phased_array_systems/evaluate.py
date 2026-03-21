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

    # RF cascade analysis (if rx_stages configured)
    if arch.rf.rx_stages:
        from phased_array_systems.models.rf.cascade import RFStage, cascade_analysis

        stages = [
            RFStage(
                name=s.get("name", f"stage_{i}"),
                gain_db=s["gain_db"],
                noise_figure_db=s["nf_db"],
                iip3_dbm=s.get("iip3_dbm", 100.0),
                p1db_dbm=s.get("p1db_dbm", 100.0),
            )
            for i, s in enumerate(arch.rf.rx_stages)
        ]
        bw = getattr(scenario, "bandwidth_hz", 1e6)
        cascade_metrics = cascade_analysis(stages, bandwidth_hz=bw)
        metrics.update(
            {
                "cascade_nf_db": cascade_metrics["total_nf_db"],
                "cascade_gain_db": cascade_metrics["total_gain_db"],
                "cascade_iip3_dbm": cascade_metrics["iip3_dbm"],
                "cascade_oip3_dbm": cascade_metrics["oip3_dbm"],
                "cascade_mds_dbm": cascade_metrics["mds_dbm"],
                "cascade_sfdr_db": cascade_metrics["sfdr_db"],
            }
        )
        # Override NF in context so link budget uses cascaded value
        context["cascade_nf_db"] = cascade_metrics["total_nf_db"]

    # Reliability analysis (if configured)
    if arch.reliability is not None:
        from phased_array_systems.models.rf.reliability import (
            TRMReliabilitySpec,
            analyze_array_reliability,
        )

        spec = TRMReliabilitySpec(
            component_mtbfs=arch.reliability.component_mtbfs,
            operating_temp_c=arch.reliability.operating_temp_c,
            mttr_hours=arch.reliability.mttr_hours,
            mission_hours=arch.reliability.mission_hours,
        )
        original_sll = metrics.get("sll_db", -30.0)
        result = analyze_array_reliability(
            arch.array.n_elements,
            spec,
            original_sll_db=original_sll,
        )
        metrics.update(
            {
                "trm_mtbf_hours": result.trm_mtbf_hours,
                "array_mtbf_hours": result.array_mtbf_hours,
                "expected_failed_elements": result.expected_failures,
                "array_availability": result.availability,
                "max_failures_for_spec": float(result.max_failures_for_spec),
                "prob_meeting_spec": result.prob_meeting_spec,
            }
        )

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
        metrics["verification.failed_ids"] = (
            ",".join(report.failed_ids) if report.failed_ids else ""
        )

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
