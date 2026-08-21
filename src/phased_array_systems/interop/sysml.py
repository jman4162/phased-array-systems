"""Bridge from sysml2kit requirement specs to a RequirementSet.

sysml2kit (the SysML v2 toolkit) extracts machine-checkable requirements
from a model as ``RequirementSpec`` objects carrying ``metric_key``, an
operator-form threshold (``op`` + ``value``), units, and severity — the same
shape as this package's ``Requirement``. This module maps a list of them
(or their ``model_dump()`` dicts, as returned by the sysml2kit MCP tool
``requirements_extract``) into a ``RequirementSet`` ready for
``verify(metrics)``.

sysml2kit is not a dependency: the input is duck-typed, so callers can pass
either the pydantic objects or plain dicts.
"""

from collections.abc import Iterable, Mapping
from typing import Any

from phased_array_systems.requirements.core import Requirement, RequirementSet
from phased_array_systems.types import ComparisonOp, MetricsDict, Severity

_OPS: tuple[ComparisonOp, ...] = (">=", "<=", "==", ">", "<")
_SEVERITIES: tuple[Severity, ...] = ("must", "should", "nice")


def _get(spec: Any, key: str) -> Any:
    if isinstance(spec, Mapping):
        return spec.get(key)
    return getattr(spec, key, None)


def requirement_from_spec(spec: Any) -> Requirement:
    """Convert one sysml2kit RequirementSpec (object or dict) to a Requirement.

    Raises ValueError when the spec has no operator-form threshold (a
    requirement without a metricKey threshold cannot be checked here).
    """
    op = _get(spec, "op")
    value = _get(spec, "value")
    if op not in _OPS or value is None:
        raise ValueError(f"spec {_get(spec, 'id')!r} has no operator-form threshold (op={op!r})")
    severity = _get(spec, "severity")
    return Requirement(
        id=str(_get(spec, "id")),
        name=str(_get(spec, "name") or _get(spec, "id")),
        metric_key=str(_get(spec, "metric_key")),
        op=op,
        value=float(value),
        units=_get(spec, "units"),
        severity=severity if severity in _SEVERITIES else "must",
    )


def requirement_set_from_specs(
    specs: Iterable[Any], *, skip_unthresholded: bool = True
) -> RequirementSet:
    """Build a RequirementSet from sysml2kit requirement specs.

    Args:
        specs: RequirementSpec objects or their dict form.
        skip_unthresholded: When True (default), specs without an
            operator-form threshold are skipped; when False they raise.

    Returns:
        A RequirementSet ready for ``verify(metrics)``.
    """
    req_set = RequirementSet()
    for spec in specs:
        try:
            req_set.add(requirement_from_spec(spec))
        except ValueError:
            if not skip_unthresholded:
                raise
    return req_set


def run_study(payload: dict[str, Any]) -> MetricsDict:
    """Evaluate a study-config payload; the sysml2kit verification engine.

    The payload is a study configuration as a dict (the same shape
    ``load_config`` reads from YAML). Registered under the
    ``sysml2kit.engines`` entry-point group as ``phased-array-systems``, so a
    SysML v2 model whose analysis carries a ``verificationBinding`` naming
    this engine runs a phased-array study and gets the flat metrics back.
    """
    from phased_array_systems.evaluate import evaluate_config
    from phased_array_systems.io.schema import StudyConfig

    return evaluate_config(StudyConfig.model_validate(payload))


def _peak_sidelobe_db(pattern_db: Any) -> float:
    """Peak sidelobe relative to the main beam, by local-maximum detection.

    A sidelobe is a local maximum of the pattern other than the main beam,
    so the peak sidelobe is the second-highest local maximum. Walking the
    samples in descending order, the first one with no already-visited
    neighbour starts a new lobe; the first such sample after the global
    peak is that second maximum. Ported from aedl's array_pattern
    evaluator, which replaced a fixed angular exclusion radius (the main
    lobe widens with scan and taper, so any fixed radius eventually sits
    inside it).

    Grid conventions: rows are theta, columns are phi over a full turn
    with the endpoint duplicated, so column wrap skips the duplicate.
    """
    import numpy as np

    n_theta, n_phi = pattern_db.shape
    span = n_phi - 1 if n_phi > 1 else 1

    order = np.argsort(pattern_db, axis=None)[::-1]
    rows, cols = np.unravel_index(order, pattern_db.shape)
    peak_db = float(pattern_db[rows[0], cols[0]])

    visited = np.zeros(pattern_db.shape, dtype=bool)
    for n, (i, j) in enumerate(zip(rows, cols, strict=True)):
        if visited[i, j]:
            continue
        has_higher_neighbour = False
        for di in (-1, 0, 1):
            ii = i + di
            if not 0 <= ii < n_theta:
                continue
            for dj in (-1, 0, 1):
                if di == 0 and dj == 0:
                    continue
                if visited[ii, (j + dj) % span]:
                    has_higher_neighbour = True
                    break
            if has_higher_neighbour:
                break
        if not has_higher_neighbour and n > 0:
            return float(pattern_db[i, j]) - peak_db
        visited[i, j] = True
        if n_phi > 1 and j in (0, span):
            visited[i, 0] = visited[i, span] = True

    return float("-inf")


def _directivity_dbi(theta_g: Any, phi_g: Any, pattern_db: Any) -> float:
    """Full-sphere directivity from a pattern in dB on a regular theta/phi grid."""
    import numpy as np

    power = 10.0 ** (pattern_db / 10.0)
    integrand = power * np.sin(theta_g)
    total = np.trapezoid(np.trapezoid(integrand, phi_g[0, :], axis=1), theta_g[:, 0], axis=0)
    return float(10.0 * np.log10(4.0 * np.pi * np.max(power) / total))


def _integrate_pattern(arch: Any, scenario: Any, n_theta: int, n_phi: int) -> tuple[float, float]:
    """(directivity_dbi, peak_sidelobe_db) from a full-pattern integration.

    Builds the steered, tapered (and phase-quantized, when configured)
    weight set and integrates the total pattern over the sphere, so taper
    loss, quantization pattern effects, the element factor, and scan all
    land in the gain by integration rather than analytic composition.
    """
    import numpy as np
    import phased_array as pa

    from phased_array_systems.constants import C
    from phased_array_systems.models.antenna.adapter import _build_taper_weights

    array = arch.array
    wavelength_m = C / scenario.freq_hz
    geom = pa.create_rectangular_array(
        array.nx, array.ny, array.dx_lambda, array.dy_lambda, wavelength=wavelength_m
    )
    k = 2 * np.pi / wavelength_m

    taper_type = getattr(array, "taper_type", "uniform")
    taper_sll_db = getattr(array, "taper_sll_db", -30.0)
    weights = _build_taper_weights(taper_type, array.nx, array.ny, taper_sll_db).astype(complex)
    scan_deg = float(getattr(scenario, "scan_angle_deg", 0.0))
    weights *= pa.steering_vector(k, geom.x, geom.y, scan_deg, 0.0)
    phase_bits = getattr(array, "phase_bits", None)
    if phase_bits is not None:
        weights = pa.quantize_phase(weights, n_bits=phase_bits)

    # The element model raises cos(theta) to a fractional power, which is
    # invalid behind the array; the library replaces those samples itself,
    # so only the warning needs quieting.
    with np.errstate(invalid="ignore"):
        theta, phi, pattern_db = pa.compute_full_pattern(
            geom.x,
            geom.y,
            weights,
            k,
            n_theta=n_theta,
            n_phi=n_phi,
            theta_range=(0.0, np.pi),
            element_pattern_func=pa.element_pattern,
            cos_exp_theta=float(getattr(array, "element_cos_exp", 1.5)),
        )
    theta_g, phi_g = np.meshgrid(theta, phi, indexing="ij")
    return _directivity_dbi(theta_g, phi_g, pattern_db), _peak_sidelobe_db(pattern_db)


def _opensatcom_margin(gain_dbi: float, arch: Any, scenario: Any) -> float | None:
    """Independent link margin with the integrated gain injected, or None.

    Recomputes the link in opensatcom (FSPL + P.676 gas + P.618 rain) with
    the integrated gain as a parametric antenna, mirroring aedl's
    crosscheck. Returns None when opensatcom is not installed.
    """
    try:
        from opensatcom.antenna.parametric import ParametricAntenna
        from opensatcom.core.models import (
            LinkInputs,
            PropagationConditions,
            RFChainModel,
            Scenario,
            Terminal,
        )
        from opensatcom.link.engine import DefaultLinkEngine
        from opensatcom.propagation.composite import CompositePropagation
        from opensatcom.propagation.fspl import FreeSpacePropagation
        from opensatcom.propagation.gas import GaseousAbsorptionP676
        from opensatcom.propagation.rain import RainAttenuationP618
    except ImportError:
        return None

    os_scenario = Scenario(
        name="pattern-crosscheck",
        direction="uplink",
        freq_hz=float(scenario.freq_hz),
        bandwidth_hz=float(scenario.bandwidth_hz),
        polarization="RHCP",
        required_metric="ebn0_db",
        required_value=float(scenario.required_snr_db),
    )
    rx_temp_k = float(scenario.rx_noise_temp_k)
    tx = Terminal("terminal", 0.0, 0.0, 0.0)
    rx = Terminal("satellite", 0.0, 0.0, float(scenario.range_m), system_noise_temp_k=rx_temp_k)
    total_tx_w = float(arch.rf.tx_power_w_per_elem) * int(arch.array.n_elements)
    rf = RFChainModel(
        tx_power_w=total_tx_w,
        tx_losses_db=float(arch.rf.feed_loss_db) + float(arch.rf.system_loss_db),
        rx_noise_temp_k=rx_temp_k,
    )
    propagation = CompositePropagation(
        [FreeSpacePropagation(), GaseousAbsorptionP676(), RainAttenuationP618()]
    )
    inputs = LinkInputs(
        tx_terminal=tx,
        rx_terminal=rx,
        scenario=os_scenario,
        tx_antenna=ParametricAntenna(gain_dbi=gain_dbi),
        rx_antenna=ParametricAntenna(gain_dbi=float(scenario.rx_antenna_gain_db or 0.0)),
        propagation=propagation,
        rf_chain=rf,
    )
    rain_mmh = float(getattr(scenario, "rain_rate_mmh", 0.0))
    cond = PropagationConditions(rain_rate_mm_per_hr=rain_mmh or None)
    out = DefaultLinkEngine().evaluate_snapshot(
        elev_deg=float(getattr(scenario, "elevation_deg", 90.0)),
        az_deg=0.0,
        range_m=float(scenario.range_m),
        inputs=inputs,
        cond=cond,
    )
    # ebn0 over the full bandwidth equals SNR in that bandwidth, matching
    # the PAS margin definition (snr in bandwidth minus required snr).
    return float(out.ebn0_db) - float(scenario.required_snr_db)


def run_pattern_study(payload: dict[str, Any]) -> MetricsDict:
    """Pattern-integration verification engine (entry point ``phased-array-systems-pattern``).

    Takes the same study-config payload as ``run_study`` plus an optional
    ``pattern`` section (``n_theta``, ``n_phi``; default 361 x 721). Where
    ``run_study`` composes gain analytically (directivity minus scan, taper,
    and quantization losses), this engine integrates the full radiation
    pattern and re-runs the link budget with the integrated gain, so the
    link margin actually responds to pattern-level effects. Emitted extras:

    - ``directivity_dbi``: full-sphere integrated directivity (replaces
      ``g_peak_db`` in the link recompute),
    - ``sll_db``: peak sidelobe over the full sphere by local-maximum
      detection (the cut-based value only sees one plane),
    - ``crosscheck_gain_disagreement_db``: |analytic gain - integrated gain|,
    - ``opensatcom_link_margin_db`` / ``crosscheck_margin_disagreement_db``:
      independent opensatcom link recompute, when opensatcom is installed.
    """
    from phased_array_systems.evaluate import evaluate_case
    from phased_array_systems.io.schema import StudyConfig
    from phased_array_systems.scenarios import CommsLinkScenario

    payload = dict(payload)
    pattern_params = dict(payload.pop("pattern", None) or {})
    n_theta = int(pattern_params.get("n_theta", 361))
    n_phi = int(pattern_params.get("n_phi", 721))

    config = StudyConfig.model_validate(payload)
    arch = config.get_architecture()
    scenario = config.get_scenario()
    if scenario is None:
        raise ValueError("pattern study payload must define a scenario")

    metrics: MetricsDict = dict(evaluate_case(arch, scenario, case_id=config.name))

    directivity_dbi, sll_db = _integrate_pattern(arch, scenario, n_theta, n_phi)
    analytic_gain = float(metrics["g_peak_db"])  # type: ignore[arg-type]
    metrics["crosscheck_gain_disagreement_db"] = abs(analytic_gain - directivity_dbi)
    metrics["g_peak_db"] = directivity_dbi
    metrics["directivity_dbi"] = directivity_dbi
    metrics["sll_db"] = sll_db

    if isinstance(scenario, CommsLinkScenario):
        from phased_array_systems.models.comms import CommsLinkModel

        metrics.update(CommsLinkModel().evaluate(arch, scenario, dict(metrics)))
        crosscheck = _opensatcom_margin(directivity_dbi, arch, scenario)
        if crosscheck is not None:
            metrics["opensatcom_link_margin_db"] = crosscheck
            metrics["crosscheck_margin_disagreement_db"] = abs(
                float(metrics["link_margin_db"]) - crosscheck  # type: ignore[arg-type]
            )

    requirements = config.get_requirement_set()
    if requirements is not None and len(requirements) > 0:
        report = requirements.verify(metrics)
        metrics["verification.passes"] = 1.0 if report.passes else 0.0
        metrics["verification.must_pass_count"] = float(report.must_pass_count)
        metrics["verification.must_total_count"] = float(report.must_total_count)
        metrics["verification.failed_ids"] = (
            ",".join(report.failed_ids) if report.failed_ids else ""
        )
    return metrics
