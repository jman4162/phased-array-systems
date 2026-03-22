#!/usr/bin/env python3
"""
Example 05: Design Optimization

This example demonstrates how to:
1. Define a design space and scenario
2. Run a DOE to establish a baseline
3. Use optimize_design() to find the optimum
4. Compare DOE-best vs optimizer-best
"""

from phased_array_systems.requirements import Requirement, RequirementSet
from phased_array_systems.scenarios import CommsLinkScenario
from phased_array_systems.trades import (
    BatchRunner,
    DesignSpace,
    generate_doe,
    optimize_design,
)


def main():
    print("=" * 70)
    print("Design Optimization Example")
    print("=" * 70)

    # 1. Define scenario and requirements
    scenario = CommsLinkScenario(
        freq_hz=10e9,
        bandwidth_hz=10e6,
        range_m=100e3,
        required_snr_db=10.0,
        scan_angle_deg=0.0,
        rx_antenna_gain_db=0.0,
        rx_noise_temp_k=290.0,
    )

    requirements = RequirementSet(
        requirements=[
            Requirement(
                id="REQ-001",
                name="Minimum EIRP",
                metric_key="eirp_dbw",
                op=">=",
                value=35.0,
                severity="must",
            ),
            Requirement(
                id="REQ-002",
                name="Maximum Cost",
                metric_key="cost_usd",
                op="<=",
                value=100000.0,
                severity="must",
            ),
        ],
    )

    # 2. Define design space
    design_space = (
        DesignSpace(name="Comms Optimization")
        .add_variable("array.nx", type="categorical", values=[4, 8, 16])
        .add_variable("array.ny", type="categorical", values=[4, 8, 16])
        .add_variable("array.enforce_subarray_constraint", type="categorical", values=[True])
        .add_variable("array.geometry", type="categorical", values=["rectangular"])
        .add_variable("rf.tx_power_w_per_elem", type="float", low=0.5, high=3.0)
        .add_variable("rf.pa_efficiency", type="float", low=0.2, high=0.5)
        .add_variable("rf.noise_figure_db", type="float", low=3.0, high=3.0)
        .add_variable("cost.cost_per_elem_usd", type="float", low=75.0, high=150.0)
    )

    # 3. Run DOE baseline (10 samples)
    print("\nStep 1: DOE baseline (10 samples)...")
    doe = generate_doe(design_space, method="lhs", n_samples=10, seed=42)
    runner = BatchRunner(scenario, requirements)
    results = runner.run(doe, n_workers=1)

    doe_best_eirp = results["eirp_dbw"].max()
    doe_best_idx = results["eirp_dbw"].idxmax()
    doe_best_cost = results.loc[doe_best_idx, "cost_usd"]

    print(f"  DOE best EIRP: {doe_best_eirp:.2f} dBW (cost: ${doe_best_cost:,.0f})")

    # 4. Run optimizer
    print("\nStep 2: Optimization (maximize EIRP with cost constraint)...")
    opt_result = optimize_design(
        design_space=design_space,
        scenario=scenario,
        objectives=[("eirp_dbw", "maximize")],
        requirements=requirements,
        method="differential_evolution",
        seed=42,
        max_iter=50,
    )

    opt_eirp = opt_result.best_metrics["eirp_dbw"]
    opt_cost = opt_result.best_metrics["cost_usd"]

    print(f"  Optimizer EIRP: {opt_eirp:.2f} dBW (cost: ${opt_cost:,.0f})")
    print(f"  Converged: {opt_result.converged}")
    print(f"  Evaluations: {opt_result.n_evaluations}")
    print(f"  Runtime: {opt_result.runtime_s:.1f}s")

    # 5. Compare
    print("\n" + "=" * 70)
    print("Comparison")
    print("=" * 70)
    improvement = opt_eirp - doe_best_eirp
    print(f"  DOE best:      EIRP={doe_best_eirp:.2f} dBW, Cost=${doe_best_cost:,.0f}")
    print(f"  Optimizer:     EIRP={opt_eirp:.2f} dBW, Cost=${opt_cost:,.0f}")
    print(f"  Improvement:   {improvement:+.2f} dB EIRP")

    arch = opt_result.best_architecture
    print(f"\n  Optimal array: {arch.array.nx}x{arch.array.ny} ({arch.n_elements} elements)")
    print(f"  TX power/elem: {arch.rf.tx_power_w_per_elem:.2f} W")
    print(f"  PA efficiency: {arch.rf.pa_efficiency:.2f}")

    return opt_result


if __name__ == "__main__":
    result = main()
