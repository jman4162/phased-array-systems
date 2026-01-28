#!/usr/bin/env python3
"""
Example 03: Radar Detection Trade Study

This example demonstrates how to:
1. Define a phased array radar architecture
2. Define a radar detection scenario
3. Define detection requirements
4. Run a DOE trade study
5. Extract Pareto-optimal designs
6. Visualize the trade space

This shows the full workflow for radar system trade studies.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # Use non-interactive backend for headless environments

import matplotlib.pyplot as plt

from phased_array_systems.architecture import (
    Architecture,
    ArrayConfig,
    CostConfig,
    RFChainConfig,
)
from phased_array_systems.evaluate import evaluate_case_with_report
from phased_array_systems.io import export_results
from phased_array_systems.requirements import Requirement, RequirementSet
from phased_array_systems.scenarios import RadarDetectionScenario
from phased_array_systems.trades import (
    BatchRunner,
    DesignSpace,
    extract_pareto,
    filter_feasible,
    generate_doe,
    rank_pareto,
)
from phased_array_systems.viz import pareto_plot


def main():
    print("=" * 70)
    print("Phased Array Radar Detection Trade Study")
    print("=" * 70)

    # =========================================================================
    # 1. Define the Scenario (fixed for all cases)
    # =========================================================================
    scenario = RadarDetectionScenario(
        freq_hz=10e9,  # 10 GHz (X-band)
        bandwidth_hz=1e6,  # 1 MHz
        range_m=20e3,  # 20 km target range
        target_rcs_dbsm=10.0,  # 10 m^2 target (10 dBsm) - small aircraft
        pfa=1e-6,  # Probability of false alarm
        pd_required=0.9,  # 90% probability of detection
        n_pulses=16,  # 16 pulses integrated
        integration_type="noncoherent",
        rx_noise_temp_k=290.0,
    )

    print(f"\nScenario: {scenario.freq_hz/1e9:.1f} GHz, {scenario.range_m/1e3:.0f} km range")
    print(f"  Target RCS: {scenario.target_rcs_dbsm} dBsm ({scenario.target_rcs_m2:.1f} m²)")
    print(f"  Detection: Pd={scenario.pd_required}, Pfa={scenario.pfa:.0e}")
    print(f"  Integration: {scenario.n_pulses} pulses ({scenario.integration_type})")

    # =========================================================================
    # 2. Define Requirements
    # =========================================================================
    requirements = RequirementSet(
        requirements=[
            Requirement(
                id="REQ-001",
                name="Detection Range",
                metric_key="detection_range_m",
                op=">=",
                value=20000.0,  # Must detect at 20 km
                severity="must",
            ),
            Requirement(
                id="REQ-002",
                name="SNR Margin",
                metric_key="snr_margin_db",
                op=">=",
                value=3.0,  # 3 dB margin
                severity="must",
            ),
            Requirement(
                id="REQ-003",
                name="Maximum Cost",
                metric_key="cost_usd",
                op="<=",
                value=500000.0,  # $500k max
                severity="must",
            ),
            Requirement(
                id="REQ-004",
                name="Prime Power Limit",
                metric_key="prime_power_w",
                op="<=",
                value=50000.0,  # 50 kW max
                severity="should",
            ),
        ],
        name="Radar Requirements",
    )

    print(f"\nRequirements: {len(requirements)} defined")

    # =========================================================================
    # 3. Single Case Evaluation (baseline)
    # =========================================================================
    print("\n" + "-" * 70)
    print("Baseline Design Evaluation")
    print("-" * 70)

    baseline_arch = Architecture(
        array=ArrayConfig(nx=16, ny=16),
        rf=RFChainConfig(tx_power_w_per_elem=10.0, pa_efficiency=0.35),
        cost=CostConfig(cost_per_elem_usd=500.0, nre_usd=50000.0),
    )

    metrics, report = evaluate_case_with_report(baseline_arch, scenario, requirements)

    print(f"\nBaseline: {baseline_arch.array.nx}x{baseline_arch.array.ny} array")
    print(f"  Peak Power: {metrics['peak_power_w']:.0f} W ({metrics['peak_power_dbw']:.1f} dBW)")
    print(f"  Antenna Gain: {metrics['g_ant_db']:.1f} dB")
    print(f"  SNR (single pulse): {metrics['snr_single_pulse_db']:.1f} dB")
    print(f"  SNR (integrated): {metrics['snr_integrated_db']:.1f} dB")
    print(f"  SNR Required: {metrics['snr_required_db']:.1f} dB")
    print(f"  SNR Margin: {metrics['snr_margin_db']:.1f} dB")
    print(f"  Detection Range: {metrics['detection_range_m']/1e3:.1f} km")
    print(f"  Cost: ${metrics['cost_usd']:,.0f}")
    print(f"\n  Requirements: {'PASS' if report.passes else 'FAIL'}")

    # =========================================================================
    # 4. Define Design Space
    # =========================================================================
    print("\n" + "-" * 70)
    print("Setting up DOE Trade Study")
    print("-" * 70)

    design_space = (
        DesignSpace(name="Radar Array Trade Space")
        # Array dimensions (powers of 2)
        .add_variable("array.nx", type="categorical", values=[8, 16, 32])
        .add_variable("array.ny", type="categorical", values=[8, 16, 32])
        .add_variable("array.enforce_subarray_constraint", type="categorical", values=[True])
        # Fixed array parameters
        .add_variable("array.geometry", type="categorical", values=["rectangular"])
        .add_variable("array.dx_lambda", type="float", low=0.5, high=0.5)
        .add_variable("array.dy_lambda", type="float", low=0.5, high=0.5)
        # RF chain parameters (variable)
        .add_variable("rf.tx_power_w_per_elem", type="float", low=5.0, high=20.0)
        .add_variable("rf.pa_efficiency", type="float", low=0.25, high=0.45)
        # Fixed RF parameters
        .add_variable("rf.noise_figure_db", type="float", low=3.0, high=3.0)
        .add_variable("rf.n_tx_beams", type="int", low=1, high=1)
        .add_variable("rf.feed_loss_db", type="float", low=1.5, high=1.5)
        .add_variable("rf.system_loss_db", type="float", low=0.0, high=0.0)
        # Cost parameters (variable)
        .add_variable("cost.cost_per_elem_usd", type="float", low=300.0, high=700.0)
        .add_variable("cost.nre_usd", type="float", low=50000.0, high=50000.0)
        .add_variable("cost.integration_cost_usd", type="float", low=20000.0, high=20000.0)
    )

    print(f"\nDesign Space: {design_space.n_dims} variables")
    print("  Variable ranges:")
    for var in design_space.variables:
        if var.type == "categorical":
            print(f"    {var.name}: {var.values}")
        elif var.low != var.high:
            print(f"    {var.name}: [{var.low}, {var.high}]")

    # =========================================================================
    # 5. Generate DOE
    # =========================================================================
    print("\n" + "-" * 70)
    print("Generating DOE...")

    n_samples = 100
    doe = generate_doe(design_space, method="lhs", n_samples=n_samples, seed=42)

    print(f"Generated {len(doe)} cases using Latin Hypercube Sampling")

    # =========================================================================
    # 6. Run Batch Evaluation
    # =========================================================================
    print("\n" + "-" * 70)
    print("Running batch evaluation...")

    runner = BatchRunner(scenario, requirements)

    def progress_callback(completed, total):
        pct = completed / total * 100
        if completed % 20 == 0 or completed == total:
            print(f"  Progress: {completed}/{total} ({pct:.0f}%)")

    results = runner.run(doe, n_workers=1, progress_callback=progress_callback)

    # Check for errors
    n_errors = results["meta.error"].notna().sum()
    if n_errors > 0:
        print(f"\nWarning: {n_errors} cases had errors")

    # =========================================================================
    # 7. Filter Feasible Designs
    # =========================================================================
    print("\n" + "-" * 70)
    print("Filtering feasible designs...")

    feasible = filter_feasible(results, requirements)
    n_feasible = len(feasible)
    n_total = len(results)
    feasible_pct = n_feasible / n_total * 100

    print(f"Feasible designs: {n_feasible}/{n_total} ({feasible_pct:.1f}%)")

    # Create feasibility mask for plotting
    feasible_mask = results["verification.passes"] == 1.0

    # =========================================================================
    # 8. Extract Pareto Frontier
    # =========================================================================
    print("\n" + "-" * 70)
    print("Extracting Pareto frontier...")

    # Minimize cost, maximize detection range
    objectives = [
        ("cost_usd", "minimize"),
        ("detection_range_m", "maximize"),
    ]

    pareto = extract_pareto(feasible, objectives)
    print(f"Pareto-optimal designs: {len(pareto)}")

    # Rank Pareto points
    ranked_pareto = rank_pareto(pareto, objectives, weights=[0.5, 0.5])

    print("\nTop 5 Pareto-optimal designs:")
    print("-" * 70)
    top_5 = ranked_pareto.head(5)
    for _, row in top_5.iterrows():
        print(
            f"  {row['case_id']}: "
            f"Array={int(row['array.nx'])}x{int(row['array.ny'])}, "
            f"Range={row['detection_range_m']/1e3:.1f} km, "
            f"Margin={row['snr_margin_db']:.1f} dB, "
            f"Cost=${row['cost_usd']:,.0f}"
        )

    # =========================================================================
    # 9. Visualize Results
    # =========================================================================
    print("\n" + "-" * 70)
    print("Generating visualizations...")

    # Create output directory
    output_dir = Path("./results/radar_doe")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Pareto plot: Cost vs Detection Range
    fig1 = pareto_plot(
        results,
        x="cost_usd",
        y="detection_range_m",
        pareto_front=pareto,
        feasible_mask=feasible_mask,
        color_by="snr_margin_db",
        title="Cost vs Detection Range Trade Space",
        x_label="Total Cost (USD)",
        y_label="Detection Range (m)",
    )
    fig1.savefig(output_dir / "pareto_cost_range.png", dpi=150, bbox_inches="tight")
    print("  Saved: pareto_cost_range.png")

    # Pareto plot: Cost vs SNR Margin
    pareto_snr = extract_pareto(
        feasible, [("cost_usd", "minimize"), ("snr_margin_db", "maximize")]
    )
    fig2 = pareto_plot(
        results,
        x="cost_usd",
        y="snr_margin_db",
        pareto_front=pareto_snr,
        feasible_mask=feasible_mask,
        color_by="detection_range_m",
        title="Cost vs SNR Margin Trade Space",
        x_label="Total Cost (USD)",
        y_label="SNR Margin (dB)",
    )
    fig2.savefig(output_dir / "pareto_cost_snr.png", dpi=150, bbox_inches="tight")
    print("  Saved: pareto_cost_snr.png")

    # Power vs Detection Range
    fig3, ax3 = plt.subplots(figsize=(10, 7))
    scatter = ax3.scatter(
        feasible["prime_power_w"],
        feasible["detection_range_m"] / 1e3,
        c=feasible["cost_usd"],
        cmap="viridis",
        s=60,
        alpha=0.7,
    )
    ax3.scatter(
        pareto["prime_power_w"],
        pareto["detection_range_m"] / 1e3,
        facecolors="none",
        edgecolors="red",
        s=150,
        linewidths=2,
        label="Pareto Optimal",
    )
    cbar = plt.colorbar(scatter, ax=ax3)
    cbar.set_label("Cost (USD)")
    ax3.set_xlabel("Prime Power (W)", fontsize=12)
    ax3.set_ylabel("Detection Range (km)", fontsize=12)
    ax3.set_title("Power vs Detection Range", fontsize=14)
    ax3.legend()
    ax3.grid(True, alpha=0.3)
    fig3.savefig(output_dir / "power_vs_range.png", dpi=150, bbox_inches="tight")
    print("  Saved: power_vs_range.png")

    plt.close("all")

    # =========================================================================
    # 10. Export Results
    # =========================================================================
    print("\n" + "-" * 70)
    print("Exporting results...")

    export_results(results, output_dir / "all_results.parquet")
    print(f"  Saved: all_results.parquet ({len(results)} cases)")

    export_results(feasible, output_dir / "feasible_results.parquet")
    print(f"  Saved: feasible_results.parquet ({len(feasible)} cases)")

    export_results(ranked_pareto, output_dir / "pareto_front.csv", format="csv")
    print(f"  Saved: pareto_front.csv ({len(ranked_pareto)} cases)")

    # =========================================================================
    # Summary
    # =========================================================================
    print("\n" + "=" * 70)
    print("Trade Study Summary")
    print("=" * 70)
    print(f"  Total cases evaluated: {n_total}")
    print(f"  Feasible designs: {n_feasible} ({feasible_pct:.1f}%)")
    print(f"  Pareto-optimal designs: {len(pareto)}")
    print(f"\n  Output directory: {output_dir.absolute()}")

    # Best designs
    if len(ranked_pareto) > 0:
        best = ranked_pareto.iloc[0]
        print("\n  Best compromise design (equal weights):")
        print(f"    Case ID: {best['case_id']}")
        print(
            f"    Array size: {int(best['array.nx'])}x{int(best['array.ny'])} "
            f"({int(best['n_elements'])} elements)"
        )
        print(f"    TX power/element: {best['rf.tx_power_w_per_elem']:.1f} W")
        print(f"    Peak power: {best['peak_power_w']:.0f} W")
        print(f"    SNR margin: {best['snr_margin_db']:.1f} dB")
        print(f"    Detection range: {best['detection_range_m']/1e3:.1f} km")
        print(f"    Total cost: ${best['cost_usd']:,.0f}")
        print(f"    Prime power: {best['prime_power_w']:.0f} W")

    print("\n" + "=" * 70)

    return results, pareto, ranked_pareto


if __name__ == "__main__":
    results, pareto, ranked = main()
