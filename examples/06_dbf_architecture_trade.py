#!/usr/bin/env python3
"""
Example 06: Digital Beamforming Architecture Trade Study

Trades digitization granularity (element / subarray / analog) against
ADC resolution, beam count, and subarray size for a wideband X-band array.

The core tension: element-level digitization maximizes system dynamic range
(+10*log10(N) processing gain) and beam flexibility, but pays for it in ADC
count, beamformer data rate, and DC power. This study quantifies that trade:

1. DOE over digitization level x ADC ENOB x n_beams x subarray size
2. Requirement checks (link margin, system dynamic range, prime power)
3. Pareto front: dynamic range vs prime power vs cost
"""

from phased_array_systems.requirements import Requirement, RequirementSet
from phased_array_systems.scenarios import CommsLinkScenario
from phased_array_systems.trades import (
    BatchRunner,
    DesignSpace,
    extract_pareto,
    filter_feasible,
    generate_doe,
)


def main():
    print("=" * 70)
    print("Digital Beamforming Architecture Trade Study")
    print("=" * 70)

    # 1. Wideband X-band comms scenario
    scenario = CommsLinkScenario(
        freq_hz=10e9,
        bandwidth_hz=200e6,
        range_m=50e3,
        required_snr_db=10.0,
        rx_antenna_gain_db=30.0,
        rx_noise_temp_k=290.0,
    )

    # 2. Requirements: usable link, wide instantaneous dynamic range,
    #    bounded prime power
    requirements = RequirementSet(
        requirements=[
            Requirement(
                id="REQ-001",
                name="Link margin",
                metric_key="link_margin_db",
                op=">=",
                value=3.0,
                severity="must",
            ),
            Requirement(
                id="REQ-002",
                name="System dynamic range",
                metric_key="dynamic_range_system_db",
                op=">=",
                value=80.0,
                severity="must",
            ),
            Requirement(
                id="REQ-003",
                name="Prime power",
                metric_key="prime_power_w",
                op="<=",
                value=6000.0,
                severity="must",
            ),
        ],
    )

    # 3. Design space: 32x32 array; sweep the digital architecture
    design_space = (
        DesignSpace(name="DBF Architecture")
        .add_variable("array.nx", type="categorical", values=[32])
        .add_variable("array.ny", type="categorical", values=[32])
        .add_variable("array.max_subarray_nx", type="categorical", values=[4, 8, 16])
        .add_variable("array.max_subarray_ny", type="categorical", values=[4, 8, 16])
        .add_variable("rf.tx_power_w_per_elem", type="float", low=1.0, high=1.0)
        .add_variable("rf.rx_power_w_per_elem", type="float", low=0.15, high=0.15)
        .add_variable(
            "digital.digitization_level",
            type="categorical",
            values=["element", "subarray", "analog"],
        )
        .add_variable("digital.adc_enob", type="float", low=8.0, high=14.0)
        .add_variable("digital.adc_jitter_ps_rms", type="float", low=0.15, high=0.15)
        .add_variable("digital.n_beams", type="categorical", values=[1, 4, 16])
        .add_variable("cost.cost_per_elem_usd", type="float", low=200.0, high=200.0)
    )

    # 4. Run the DOE
    print("\nRunning DOE (120 cases, LHS)...")
    doe = generate_doe(design_space, method="lhs", n_samples=120, seed=42)
    runner = BatchRunner(scenario, requirements)
    results = runner.run(doe, n_workers=1)

    n_errors = results["meta.error"].notna().sum() if "meta.error" in results else 0
    print(f"  Completed {len(results)} cases ({n_errors} errors)")

    # 5. Feasibility and per-level summary
    feasible = filter_feasible(results, requirements)
    print(f"  Feasible: {len(feasible)} / {len(results)}")

    print("\nPer digitization level (feasible cases):")
    cols = [
        "dynamic_range_system_db",
        "bf_data_rate_gbps",
        "adc_power_w",
        "dsp_power_w",
        "prime_power_w",
    ]
    summary = feasible.groupby("digital.digitization_level")[cols].mean()
    print(summary.round(1).to_string())

    # 6. Pareto front: dynamic range vs prime power vs cost
    pareto = extract_pareto(
        feasible,
        objectives=[
            ("dynamic_range_system_db", "maximize"),
            ("prime_power_w", "minimize"),
            ("cost_usd", "minimize"),
        ],
    )
    print(f"\nPareto-optimal designs: {len(pareto)}")
    show = [
        "digital.digitization_level",
        "digital.adc_enob",
        "digital.n_beams",
        "array.max_subarray_nx",
        "dynamic_range_system_db",
        "bf_data_rate_gbps",
        "prime_power_w",
        "cost_usd",
    ]
    print(pareto[show].round(1).to_string(index=False))

    return results, pareto


if __name__ == "__main__":
    main()
