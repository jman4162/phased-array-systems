"""Single-case evaluation orchestrator."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from phased_array_systems.__about__ import __version__
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
    seed: int | None = None,
) -> MetricsDict:
    """Evaluate a single architecture/scenario case.

    Runs all applicable models and returns merged metrics dictionary.
    Optionally verifies against requirements and includes verification results.

    Args:
        arch: Architecture configuration
        scenario: Scenario configuration (CommsLinkScenario or RadarDetectionScenario)
        requirements: Optional requirement set for verification
        case_id: Optional case identifier for tracking
        seed: Optional RNG seed threaded to stochastic sub-models (element
            failure simulation); recorded as meta.seed

    Returns:
        Dictionary containing all computed metrics plus metadata:
            - All antenna metrics (g_peak_db, beamwidth_*, sll_db, etc.)
            - All link/radar metrics (eirp_dbw, snr_*, margin_*, etc.)
            - All SWaP-C metrics (power_*, cost_*)
            - Verification results if requirements provided
            - Metadata (case_id, runtime_s, seed, versions)
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
    antenna_context: dict[str, Any] = {}
    if seed is not None:
        antenna_context["meta.seed"] = seed
    antenna_metrics = antenna_model.evaluate(arch, scenario, antenna_context)
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
                name=str(s.get("name", f"stage_{i}")),
                gain_db=float(s["gain_db"]),
                noise_figure_db=float(s["nf_db"]),
                iip3_dbm=float(s.get("iip3_dbm", 100.0)),
                p1db_dbm=float(s.get("p1db_dbm", 100.0)),
            )
            for i, s in enumerate(arch.rf.rx_stages)
        ]
        bw = getattr(scenario, "bandwidth_hz", 1e6)
        cascade_metrics: dict[str, Any] = cascade_analysis(stages, bandwidth_hz=bw)
        metrics.update(
            {
                "cascade_nf_db": float(cascade_metrics["total_nf_db"]),
                "cascade_gain_db": float(cascade_metrics["total_gain_db"]),
                "cascade_iip3_dbm": float(cascade_metrics["iip3_dbm"]),
                "cascade_oip3_dbm": float(cascade_metrics["oip3_dbm"]),
                "cascade_mds_dbm": float(cascade_metrics["mds_dbm"]),
                "cascade_sfdr_db": float(cascade_metrics["sfdr_db"]),
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
        sll_val = metrics.get("sll_db", -30.0)
        original_sll = float(sll_val) if isinstance(sll_val, (int, float)) else -30.0
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

    # Digital beamformer analysis (if configured)
    if arch.digital is not None:
        import math

        from phased_array_systems.models.digital.bandwidth import (
            beamformer_operations,
            digital_beamformer_data_rate,
            processing_margin,
        )
        from phased_array_systems.models.digital.converters import adc_effective_snr

        bw = getattr(scenario, "bandwidth_hz", 1e6)
        sample_rate = bw * arch.digital.oversampling_ratio
        bits_per_sample = int(arch.digital.adc_enob) * 2  # I + Q

        # Digitized channel count follows the digitization level
        # (element / subarray / analog), not the raw element count
        n_channels = arch.n_digital_channels

        # ADC metrics (quantization + aperture jitter)
        jitter_s = (
            arch.digital.adc_jitter_ps_rms * 1e-12
            if arch.digital.adc_jitter_ps_rms is not None
            else None
        )
        adc = adc_effective_snr(
            arch.digital.adc_enob,
            sample_rate,
            input_freq_hz=arch.digital.adc_input_freq_hz,
            jitter_s_rms=jitter_s,
        )
        metrics["adc_enob"] = arch.digital.adc_enob
        metrics["adc_enob_effective"] = adc["enob_effective"]
        metrics["adc_snr_db"] = adc["snr_total_db"]
        metrics["adc_sample_rate_hz"] = sample_rate
        metrics["n_digital_channels"] = float(n_channels)

        # Combining N digitized channels adds 10*log10(N) processing gain
        # to the system dynamic range
        metrics["dynamic_range_system_db"] = adc["snr_total_db"] + 10 * math.log10(n_channels)

        # Beamformer data rate
        bf_rate = digital_beamformer_data_rate(
            n_channels,
            sample_rate,
            bits_per_sample,
        )
        metrics["bf_data_rate_gbps"] = bf_rate["with_overhead_gbps"]

        # Beamformer compute
        bf_ops = beamformer_operations(
            n_channels,
            arch.digital.n_beams,
            sample_rate,
        )
        metrics["bf_compute_gops"] = bf_ops["total_gops"]

        # Processing margin (if FPGA throughput specified)
        if arch.digital.fpga_throughput_gops is not None:
            pm = processing_margin(arch.digital.fpga_throughput_gops, bf_ops["total_gops"])
            metrics["processing_margin_db"] = pm["margin_db"]
            metrics["fpga_utilization_pct"] = pm["utilization_percent"]

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

    # Add timing and provenance metadata
    elapsed = time.perf_counter() - start_time
    metrics["meta.runtime_s"] = elapsed
    if seed is not None:
        metrics["meta.seed"] = seed
    metrics["meta.package_version"] = __version__
    metrics["meta.pam_version"] = _pam_version()

    return metrics


def _pam_version() -> str:
    """Version of the phased_array backend, or 'analytical' if absent."""
    from phased_array_systems.models.antenna.adapter import HAS_PAM

    if not HAS_PAM:
        return "analytical"
    try:
        import phased_array

        return str(getattr(phased_array, "__version__", "unknown"))
    except ImportError:  # pragma: no cover
        return "analytical"


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
