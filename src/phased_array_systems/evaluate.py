"""Single-case evaluation orchestrator."""

from __future__ import annotations

import math
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
    antenna_fidelity: str | None = None,
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
        antenna_fidelity: Explicit antenna method: "analytic" | "pattern" |
            None (dispatch on library availability)

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
    antenna_model = PhasedArrayAdapter(
        use_analytical_fallback=True, antenna_fidelity=antenna_fidelity
    )
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

    # Cooling feasibility: does the declared approach remove the aperture heat
    # flux this design produces? Independent of the junction-temperature path,
    # which asserts a thermal resistance rather than checking it.
    if arch.cooling is not None and "heat_flux_w_per_cm2" in metrics:
        from phased_array_systems.models.swapc.cooling import assess, max_heat_flux

        flux = metrics["heat_flux_w_per_cm2"]
        flux = float(flux) if isinstance(flux, (int, float)) else 0.0
        if arch.cooling.max_heat_flux_w_per_cm2 is not None:
            ceiling = float(arch.cooling.max_heat_flux_w_per_cm2)
            metrics.update(
                {
                    "cooling_class": arch.cooling.cooling_class,
                    "max_heat_flux_w_per_cm2": ceiling,
                    "cooling_margin_w_per_cm2": ceiling - flux,
                    "cooling_feasible": bool(ceiling >= flux),
                }
            )
        else:
            max_heat_flux(arch.cooling.cooling_class)  # raises on unknown class
            metrics.update(assess(flux, arch.cooling.cooling_class))

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
        # Expose IIP3 so the link budget can fold IM3 into an SNDR when the
        # scenario enables nonlinear impairments
        context["cascade_iip3_dbm"] = float(cascade_metrics["iip3_dbm"])

    # TX cascade analysis (if tx_stages configured): gain, composite P1dB, and
    # a per-stage compression check at the commanded per-element drive level
    if arch.rf.tx_stages:
        from phased_array_systems.models.rf.cascade import (
            RFStage,
            cascade_analysis,
            compression_check,
        )

        tx_rf_stages = [
            RFStage(
                name=str(s.get("name", f"tx_stage_{i}")),
                gain_db=float(s["gain_db"]),
                noise_figure_db=float(s["nf_db"]),
                iip3_dbm=float(s.get("iip3_dbm", 100.0)),
                p1db_dbm=float(s.get("p1db_dbm", 100.0)),
            )
            for i, s in enumerate(arch.rf.tx_stages)
        ]
        bw = getattr(scenario, "bandwidth_hz", 1e6)
        tx_cascade: dict[str, Any] = cascade_analysis(tx_rf_stages, bandwidth_hz=bw)
        # Drive level into the TX chain: the commanded per-element power
        # referred to the chain input (subtract the cascade gain), minus any
        # scenario backoff
        tx_out_dbm = 10.0 * math.log10(arch.rf.tx_power_w_per_elem * 1e3)
        tx_out_dbm -= getattr(scenario, "tx_backoff_db", 0.0)
        tx_in_dbm = tx_out_dbm - float(tx_cascade["total_gain_db"])
        tx_comp = compression_check(tx_rf_stages, tx_in_dbm)
        tx_min_headroom = tx_comp["min_headroom_db"]
        assert isinstance(tx_min_headroom, float)
        metrics.update(
            {
                "tx_cascade_gain_db": float(tx_cascade["total_gain_db"]),
                "tx_cascade_op1db_dbm": float(tx_cascade["op1db_dbm"]),
                "tx_cascade_ip1db_dbm": float(tx_cascade["ip1db_dbm"]),
                "tx_min_p1db_headroom_db": tx_min_headroom,
                "tx_p1db_binding_stage": str(tx_comp["binding_stage"]),
                "tx_compressed": bool(tx_comp["compressed"]),
            }
        )

    # Reliability analysis (if configured)
    if arch.reliability is not None:
        from phased_array_systems.models.rf.reliability import (
            TRMReliabilitySpec,
            analyze_array_reliability,
        )

        # Feed-forward thermal coupling: when a thermal resistance is
        # given, estimate the TRM junction temperature from the dissipated
        # heat the power model already computed (heat = DC in - RF out),
        # so array size, TX power, and duty cycle drive Arrhenius derating
        operating_temp_c = arch.reliability.operating_temp_c
        if arch.reliability.thermal_resistance_c_per_w is not None:
            # One energy balance, computed by PowerModel via
            # compute_thermal_load; this consumes it rather than repeating it.
            heat_w = metrics.get("heat_dissipation_w", 0.0)
            heat_w = float(heat_w) if isinstance(heat_w, (int, float)) else 0.0
            # Per-DEVICE normalization: this is a junction temperature, so the
            # divisor is element count, not aperture area. The areal quantity
            # (heat_flux_w_per_cm2) answers a different question -- whether the
            # cooling technology assumed by thermal_resistance_c_per_w can
            # actually remove that flux -- and is checked separately.
            heat_per_elem_w = max(0.0, heat_w) / arch.array.n_elements
            operating_temp_c = (
                arch.reliability.ambient_temp_c
                + arch.reliability.thermal_resistance_c_per_w * heat_per_elem_w
            )
            metrics["junction_temp_c"] = operating_temp_c
            # Junction limit. The technology catalog carries tj_max_c and
            # nothing read it until now, so a design could run the junction
            # past its rated maximum and only ever be penalized indirectly,
            # through Arrhenius derating of MTBF.
            tj_max = arch.reliability.tj_max_c
            if tj_max is None and arch.trm is not None and arch.trm.technology:
                from phased_array_systems.models.rf.technology import entry

                tj_max = entry(arch.trm.technology).get("tj_max_c")
            if tj_max is not None:
                metrics["junction_temp_max_c"] = float(tj_max)
                metrics["junction_temp_margin_c"] = float(tj_max) - operating_temp_c
                metrics["junction_temp_ok"] = bool(operating_temp_c <= float(tj_max))

        spec = TRMReliabilitySpec(
            component_mtbfs=arch.reliability.component_mtbfs,
            operating_temp_c=operating_temp_c,
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
        from phased_array_systems.models.digital.bandwidth import (
            beamformer_operations,
            digital_beamformer_data_rate,
            processing_margin,
        )
        from phased_array_systems.models.digital.converters import adc_effective_snr

        bw = getattr(scenario, "bandwidth_hz", 1e6)
        sample_rate = bw * arch.digital.oversampling_ratio
        # Physical bit width sizes the data stream, not ENOB (a 12-bit
        # converter with 10.5 effective bits still moves 12-bit words)
        bits_per_sample = arch.digital.adc_bits_physical * 2  # I + Q

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

        # TX digital path (if a DAC is configured)
        if arch.digital.dac_enob is not None:
            from phased_array_systems.models.digital.converters import dac_output_power

            dac = dac_output_power(
                arch.digital.dac_enob,
                arch.digital.dac_full_scale_dbm,
                backoff_db=arch.digital.dac_backoff_db,
            )
            metrics["dac_operating_power_dbm"] = dac["operating_power_dbm"]
            metrics["dac_snr_db"] = dac["snr_db"]
            metrics["dac_sfdr_db"] = dac["sfdr_db"]
            # TX stream mirrors the RX one at the same digitization level
            dac_bits = arch.digital.dac_bits_physical
            assert dac_bits is not None
            tx_rate = digital_beamformer_data_rate(
                n_channels,
                sample_rate,
                dac_bits * 2,  # I + Q
            )
            metrics["tx_bf_data_rate_gbps"] = tx_rate["with_overhead_gbps"]

    # Evaluate scenario-specific models
    if isinstance(scenario, CommsLinkScenario):
        comms_model = CommsLinkModel()
        comms_metrics = comms_model.evaluate(arch, scenario, context)
        metrics.update(comms_metrics)
    elif isinstance(scenario, RadarDetectionScenario):
        radar_model = RadarModel()
        radar_metrics = radar_model.evaluate(arch, scenario, context)
        metrics.update(radar_metrics)

        # Power-aperture product: the mission figure of merit that pairs with
        # aperture heat flux. P*A (W*m^2) says how much power and aperture the
        # search demands; heat flux (W/cm^2) constrains how tightly it may be
        # packaged. They are dimensional inverses; see models/radar/search.py.
        from phased_array_systems.models.radar.search import (
            effective_aperture_m2,
            power_aperture_product_w_m2,
            required_power_aperture_w_m2,
            search_solid_angle_sr,
        )

        g_ant = metrics.get("g_ant_db")
        rf_avg = metrics.get("rf_avg_power_w")
        if isinstance(g_ant, (int, float)) and isinstance(rf_avg, (int, float)):
            a_eff = effective_aperture_m2(float(g_ant), scenario.freq_hz)
            pa_product = power_aperture_product_w_m2(float(rf_avg), a_eff)
            metrics["effective_aperture_m2"] = a_eff
            metrics["power_aperture_product_w_m2"] = pa_product

            frame_s = (
                scenario.search_frame_time_ms / 1e3
                if scenario.search_frame_time_ms is not None
                else None
            )
            if (
                scenario.search_az_extent_deg is not None
                and scenario.search_el_extent_deg is not None
                and frame_s is not None
                and frame_s > 0
            ):
                snr_req = metrics.get("snr_required_db", 0.0)
                t_sys = metrics.get("noise_temp_system_k", 290.0)
                loss = metrics.get("system_loss_db", 0.0)
                required = required_power_aperture_w_m2(
                    range_m=scenario.range_m,
                    target_rcs_m2=scenario.target_rcs_m2,
                    search_solid_angle_sr=search_solid_angle_sr(
                        scenario.search_az_extent_deg, scenario.search_el_extent_deg
                    ),
                    frame_time_s=frame_s,
                    snr_required_db=float(snr_req) if isinstance(snr_req, (int, float)) else 0.0,
                    system_noise_temp_k=float(t_sys) if isinstance(t_sys, (int, float)) else 290.0,
                    loss_db=float(loss) if isinstance(loss, (int, float)) else 0.0,
                )
                metrics["power_aperture_required_w_m2"] = required
                metrics["power_aperture_margin_db"] = 10.0 * math.log10(
                    pa_product / required if required > 0 else float("inf")
                )

        # Search timeline (if PRF and search extents configured): connects
        # the antenna beamwidths and dwell time to volume revisit rate
        if (
            scenario.prf_hz is not None
            and scenario.search_az_extent_deg is not None
            and scenario.search_el_extent_deg is not None
        ):
            from phased_array_systems.models.digital.scheduling import max_update_rate

            dwell_time_s = scenario.n_pulses / scenario.prf_hz

            bw_az = metrics.get("beamwidth_az_deg", 5.0)
            bw_el = metrics.get("beamwidth_el_deg", 5.0)
            bw_az = float(bw_az) if isinstance(bw_az, (int, float)) else 5.0
            bw_el = float(bw_el) if isinstance(bw_el, (int, float)) else 5.0
            beam_solid_angle_sr = math.radians(bw_az) * math.radians(bw_el)
            scan_volume_sr = math.radians(scenario.search_az_extent_deg) * math.radians(
                scenario.search_el_extent_deg
            )

            timeline = max_update_rate(
                scan_volume_sr=scan_volume_sr,
                beam_solid_angle_sr=beam_solid_angle_sr,
                dwell_time_us=dwell_time_s * 1e6,
                overhead_us=scenario.beam_overhead_us,
            )
            metrics["dwell_time_ms"] = dwell_time_s * 1e3
            metrics["n_beam_positions"] = timeline["n_beam_positions"]
            metrics["search_frame_time_s"] = timeline["scan_time_s"]
            metrics["search_update_rate_hz"] = timeline["update_rate_hz"]
            # Occupancy vs an allotted frame budget: > 1 means the search
            # task is oversubscribed (natural must-requirement metric)
            if scenario.search_frame_time_ms is not None:
                metrics["timeline_occupancy"] = timeline["frame_time_ms"] / (
                    scenario.search_frame_time_ms
                )

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

    return evaluate_case(
        arch,
        scenario,
        requirements,
        case_id=config.name,
        antenna_fidelity=config.antenna_fidelity,
    )
