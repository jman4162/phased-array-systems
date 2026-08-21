"""Tests for the sysml2kit requirement bridge.

The specs below mirror what sysml2kit's requirements_extract returns for the
sysml2kit-rf-library t3-001 satcom-terminal model; the bridge is duck-typed
so no sysml2kit import is needed here.
"""

from types import SimpleNamespace

import pytest

from phased_array_systems.interop import requirement_set_from_specs
from phased_array_systems.interop.sysml import requirement_from_spec

T3001_SPECS = [
    {
        "id": "REQ-LINK-MARGIN",
        "name": "WorstCaseLinkMargin",
        "metric_key": "worst_case_link_margin_db",
        "op": ">=",
        "value": 0.0,
        "units": "dB",
        "severity": "must",
    },
    {
        "id": "REQ-SLL",
        "name": "PatternSidelobes",
        "metric_key": "worst_case_pattern_sll_db",
        "op": "<=",
        "value": -16.0,
        "units": "dB",
        "severity": "must",
    },
    {
        "id": "REQ-POWER",
        "name": "PrimePowerCeiling",
        "metric_key": "prime_power_w",
        "op": "<=",
        "value": 450.0,
        "units": "W",
        "severity": "must",
    },
    {
        "id": "REQ-COST",
        "name": "UnitCostCeiling",
        "metric_key": "unit_cost_usd",
        "op": "<=",
        "value": 45000.0,
        "units": None,
        "severity": "must",
    },
    {
        "id": "REQ-GRATING",
        "name": "GratingLobeMargin",
        "metric_key": "grating_margin_lambda",
        "op": ">=",
        "value": 0.0,
        "units": None,
        "severity": "must",
    },
    {
        "id": "REQ-CLEARSKY-AGREE",
        "name": "ClearSkyAgreement",
        "metric_key": "crosscheck_clearsky_margin_disagreement_db",
        "op": "<=",
        "value": 1.2,
        "units": "dB",
        "severity": "should",
    },
]

PASSING_METRICS = {
    "worst_case_link_margin_db": 1.4,
    "worst_case_pattern_sll_db": -18.2,
    "prime_power_w": 412.0,
    "unit_cost_usd": 43050.0,
    "grating_margin_lambda": 0.06,
    "crosscheck_clearsky_margin_disagreement_db": 0.4,
}


def test_dict_specs_build_a_requirement_set():
    req_set = requirement_set_from_specs(T3001_SPECS)
    report = req_set.verify(PASSING_METRICS)
    assert report.passes
    assert len(report.results) == len(T3001_SPECS)


def test_failing_metric_fails_verification():
    req_set = requirement_set_from_specs(T3001_SPECS)
    metrics = dict(PASSING_METRICS, prime_power_w=460.0)
    report = req_set.verify(metrics)
    assert not report.passes
    assert "REQ-POWER" in report.failed_ids


def test_object_specs_accepted():
    spec = SimpleNamespace(**T3001_SPECS[0])
    req = requirement_from_spec(spec)
    assert req.id == "REQ-LINK-MARGIN"
    assert req.op == ">="
    assert req.value == 0.0


def test_severity_and_units_carry_through():
    req = requirement_from_spec(T3001_SPECS[5])
    assert req.severity == "should"
    assert req.units == "dB"


def test_unthresholded_spec_skipped_by_default():
    prose_only = {
        "id": "REQ-PROSE",
        "name": "ProseOnly",
        "metric_key": "n/a",
        "op": None,
        "value": None,
    }
    req_set = requirement_set_from_specs([*T3001_SPECS, prose_only])
    assert len(req_set.verify(PASSING_METRICS).results) == len(T3001_SPECS)


def test_unthresholded_spec_raises_when_strict():
    prose_only = {
        "id": "REQ-PROSE",
        "name": "ProseOnly",
        "metric_key": "n/a",
        "op": None,
        "value": None,
    }
    with pytest.raises(ValueError, match="REQ-PROSE"):
        requirement_set_from_specs([prose_only], skip_unthresholded=False)


MINIMAL_STUDY = {
    "name": "engine-smoke",
    "array": {"nx": 16, "ny": 16, "dx": 0.5, "dy": 0.5},
    "rf": {"tx_power_w_per_elem": 1.0},
    "scenario": {
        "type": "comms",
        "freq_hz": 28.0e9,
        "bandwidth_hz": 50.0e6,
        "range_m": 800.0e3,
        "required_snr_db": 6.0,
    },
}


def test_run_study_returns_flat_metrics():
    from phased_array_systems.interop import run_study

    metrics = run_study(MINIMAL_STUDY)
    assert isinstance(metrics, dict)
    for key in ("eirp_dbw", "link_margin_db", "prime_power_w"):
        assert key in metrics, f"missing {key}"
        assert isinstance(metrics[key], (int, float))


def test_engine_entry_point_registered():
    # Reads the installed distribution metadata, which proves packaging
    # exposes the engine (and works on Python 3.10, unlike tomllib).
    from importlib.metadata import entry_points

    eps = {ep.name: ep.value for ep in entry_points(group="sysml2kit.engines")}
    assert eps["phased-array-systems"] == "phased_array_systems.interop.sysml:run_study"


SCANNED_STUDY = {
    "name": "fidelity-smoke",
    "array": {
        "nx": 8,
        "ny": 8,
        "dx": 0.5,
        "dy": 0.5,
        "taper_type": "taylor",
        "taper_sll_db": -30.0,
    },
    "rf": {"tx_power_w_per_elem": 2.0},
    "scenario": {
        "type": "comms",
        "freq_hz": 20.0e9,
        "bandwidth_hz": 50.0e6,
        "range_m": 1000.0e3,
        "required_snr_db": 6.0,
        "scan_angle_deg": 30.0,
        "rx_antenna_gain_db": 35.0,
        "rx_noise_temp_k": 500.0,
    },
}


def test_antenna_fidelity_selects_method():
    from phased_array_systems.interop import run_study

    analytic = run_study({**SCANNED_STUDY, "antenna_fidelity": "analytic"})
    cuts = run_study({**SCANNED_STUDY, "antenna_fidelity": "pattern"})
    assert analytic["element_pattern_applied"] is False
    assert cuts["element_pattern_applied"] is True
    # The degeneracy both rungs share: gain is composed analytically in
    # each, so the link margin is identical even though sidelobes differ.
    assert analytic["link_margin_db"] == cuts["link_margin_db"]
    assert analytic["sll_db"] != cuts["sll_db"]


def test_adapter_rejects_unknown_fidelity():
    from phased_array_systems.models.antenna import PhasedArrayAdapter

    with pytest.raises(ValueError, match="antenna_fidelity"):
        PhasedArrayAdapter(antenna_fidelity="full-wave")


def test_run_pattern_study_breaks_margin_degeneracy():
    from phased_array_systems.interop import run_pattern_study, run_study

    analytic = run_study({**SCANNED_STUDY, "antenna_fidelity": "analytic"})
    pattern = run_pattern_study({**SCANNED_STUDY, "pattern": {"n_theta": 181, "n_phi": 361}})
    for key in ("directivity_dbi", "crosscheck_gain_disagreement_db"):
        assert key in pattern
    # Integrated gain feeds the link recompute, so the margin moves.
    assert pattern["link_margin_db"] != analytic["link_margin_db"]
    # ...but not far: integration and analytic composition should agree
    # to within a taper/quantization-level correction.
    assert pattern["crosscheck_gain_disagreement_db"] < 1.0


def test_pattern_engine_entry_point_registered():
    from importlib.metadata import entry_points

    eps = {ep.name: ep.value for ep in entry_points(group="sysml2kit.engines")}
    assert (
        eps["phased-array-systems-pattern"]
        == "phased_array_systems.interop.sysml:run_pattern_study"
    )
