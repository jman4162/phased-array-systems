"""Golden-case regression test.

Locks the full metrics dictionary for a representative digital-beamforming
radar case. Any model change that shifts these numbers must update the
snapshot deliberately (regenerate with `python tests/test_golden_case.py`).
"""

import json
import math
from pathlib import Path

import pytest

from phased_array_systems.architecture import (
    Architecture,
    ArrayConfig,
    CostConfig,
    DigitalConfig,
    RFChainConfig,
)
from phased_array_systems.evaluate import evaluate_case
from phased_array_systems.scenarios import RadarDetectionScenario

GOLDEN_PATH = Path(__file__).parent / "data" / "golden_dbf_case.json"

# Metrics excluded from comparison (timing, identifiers, non-numeric)
EXCLUDED_KEYS = {"meta.runtime_s", "meta.case_id"}


def build_golden_case():
    """The reference DBF radar case: subarray-digital X-band array."""
    arch = Architecture(
        array=ArrayConfig(
            nx=32,
            ny=32,
            dx_lambda=0.5,
            dy_lambda=0.5,
            max_subarray_nx=8,
            max_subarray_ny=8,
            taper_type="taylor",
            taper_sll_db=-30.0,
        ),
        rf=RFChainConfig(
            tx_power_w_per_elem=4.0,
            rx_power_w_per_elem=0.2,
            pa_efficiency=0.35,
            noise_figure_db=3.0,
            feed_loss_db=1.0,
            rx_stages=[
                {"name": "lna", "gain_db": 20.0, "nf_db": 1.5, "iip3_dbm": -5.0},
                {"name": "mixer", "gain_db": -7.0, "nf_db": 7.0, "iip3_dbm": 15.0},
                {"name": "if_amp", "gain_db": 30.0, "nf_db": 4.0, "iip3_dbm": 20.0},
            ],
        ),
        cost=CostConfig(cost_per_elem_usd=250.0, nre_usd=500_000.0),
        digital=DigitalConfig(
            digitization_level="subarray",
            adc_enob=11.0,
            adc_jitter_ps_rms=0.2,
            oversampling_ratio=2.5,
            n_beams=8,
            fpga_throughput_gops=2000.0,
        ),
    )
    scenario = RadarDetectionScenario(
        freq_hz=10e9,
        bandwidth_hz=50e6,
        range_m=15e3,
        target_rcs_dbsm=10.0,
        pfa=1e-6,
        pd_required=0.9,
        n_pulses=16,
        integration_type="noncoherent",
        duty_cycle=0.1,
    )
    return arch, scenario


def compute_golden_metrics() -> dict:
    arch, scenario = build_golden_case()
    metrics = evaluate_case(arch, scenario)
    return {
        k: v
        for k, v in metrics.items()
        if k not in EXCLUDED_KEYS and isinstance(v, (int, float)) and math.isfinite(v)
    }


class TestGoldenCase:
    def test_snapshot_exists(self):
        assert GOLDEN_PATH.exists(), (
            f"Golden snapshot missing: {GOLDEN_PATH}. "
            "Generate it with `python tests/test_golden_case.py`."
        )

    def test_metrics_match_snapshot(self):
        expected = json.loads(GOLDEN_PATH.read_text())
        actual = compute_golden_metrics()

        missing = set(expected) - set(actual)
        added = set(actual) - set(expected)
        assert not missing, f"Metrics disappeared vs snapshot: {sorted(missing)}"
        assert not added, f"New metrics not in snapshot: {sorted(added)}"

        for key, value in expected.items():
            assert actual[key] == pytest.approx(value, rel=1e-9, abs=1e-12), (
                f"Metric '{key}' drifted: snapshot={value}, actual={actual[key]}"
            )


if __name__ == "__main__":
    GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    GOLDEN_PATH.write_text(json.dumps(compute_golden_metrics(), indent=2, sort_keys=True) + "\n")
    print(f"Wrote {GOLDEN_PATH}")
