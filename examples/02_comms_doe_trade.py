#!/usr/bin/env python3
"""
Example 02: DOE Trade Study for Communications Arrays

This example demonstrates how to:
1. Define a design space with variable bounds
2. Generate a Design of Experiments (DOE)
3. Run batch evaluation with progress tracking
4. Filter feasible designs based on requirements
5. Extract the Pareto frontier
6. Visualize the trade space
7. Export results

This is the full DOE workflow for exploring design trade-offs.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # Use non-interactive backend for headless environments

import matplotlib.pyplot as plt

from phased_array_systems.io import export_results
from phased_array_systems.requirements import Requirement, RequirementSet
from phased_array_systems.scenarios import CommsLinkScenario
from phased_array_systems.trades import (
    BatchRunner,
    DesignSpace,
    extract_pareto,
    filter_feasible,
    generate_doe,
    rank_pareto,
)
from phased_array_systems.viz import pareto_plot, scatter_matrix


def main():
    print("=" * 70)
    print("Communications Array DOE Trade Study")
    print("=" * 70)

    # =========================================================================
    # 1. Define the Scenario (fixed for all cases)
    # =========================================================================
    scenario = CommsLinkScenario(
        freq_hz=10e9,  # 10 GHz
        bandwidth_hz=10e6,  # 10 MHz
        range_m=100e3,  # 100 km
        required_snr_db=10.0,
        scan_angle_deg=0.0,
        rx_antenna_gain_db=0.0,
        rx_noise_temp_k=290.0,
    )

    print(f"\nScenario: {scenario.freq_hz / 1e9:.1f} GHz, {scenario.range_m / 1e3:.0f} km range")

    # =========================================================================
    # 2. Define Requirements
    # =========================================================================
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
                name="Positive Link Margin",
                metric_key="link_margin_db",
                op=">=",
                value=0.0,
                severity="must",
            ),
            Requirement(
                id="REQ-003",
                name="Maximum Cost",
                metric_key="cost_usd",
                op="<=",
                value=100000.0,
                severity="must",
            ),
        ],
        name="Trade Study Requirements",
    )

    print(f"\nRequirements: {len(requirements)} defined")

    # =========================================================================
    # 3. Define Design Space
    # =========================================================================
    design_space = (
        DesignSpace(name="Comms Array Design Space")
        # Array dimensions (must be powers of 2 for sub-array constraints)
        .add_variable("array.nx", type="categorical", values=[4, 8, 16])
        .add_variable("array.ny", type="categorical", values=[4, 8, 16])
        # Disable sub-array constraint for DOE flexibility (or use power-of-2 values)
        .add_variable("array.enforce_subarray_constraint", type="categorical", values=[True])
        # Fixed array parameters
        .add_variable("array.geometry", type="categorical", values=["rectangular"])
        .add_variable("array.dx_lambda", type="float", low=0.5, high=0.5)
        .add_variable("array.dy_lambda", type="float", low=0.5, high=0.5)
        .add_variable("array.scan_limit_deg", type="float", low=60.0, high=60.0)
        # RF chain parameters (variable)
        .add_variable("rf.tx_power_w_per_elem", type="float", low=0.5, high=3.0)
        .add_variable("rf.pa_efficiency", type="float", low=0.2, high=0.5)
        # Fixed RF parameters
        .add_variable("rf.noise_figure_db", type="float", low=3.0, high=3.0)
        .add_variable("rf.n_tx_beams", type="int", low=1, high=1)
        .add_variable("rf.feed_loss_db", type="float", low=1.0, high=1.0)
        .add_variable("rf.system_loss_db", type="float", low=0.0, high=0.0)
        # Cost parameters (variable)
        .add_variable("cost.cost_per_elem_usd", type="float", low=75.0, high=150.0)
        .add_variable("cost.nre_usd", type="float", low=10000.0, high=10000.0)
        .add_variable("cost.integration_cost_usd", type="float", low=5000.0, high=5000.0)
    )

    print(f"\nDesign Space: {design_space.n_dims} variables")
    print("  Variable ranges:")
    for var in design_space.variables:
        if var.type == "categorical":
            print(f"    {var.name}: {var.values}")
        elif var.low != var.high:
            print(f"    {var.name}: [{var.low}, {var.high}]")

    # =========================================================================
    # 4. Generate DOE
    # =========================================================================
    print("\n" + "-" * 70)
    print("Generating DOE...")

    n_samples = 100
    doe = generate_doe(design_space, method="lhs", n_samples=n_samples, seed=42)

    print(f"Generated {len(doe)} cases using Latin Hypercube Sampling")

    # =========================================================================
    # 5. Run Batch Evaluation
    # =========================================================================
    print("\n" + "-" * 70)
    print("Running batch evaluation...")

    runner = BatchRunner(scenario, requirements)

    def progress_callback(completed, total):
        pct = completed / total * 100
        if completed % 10 == 0 or completed == total:
            print(f"  Progress: {completed}/{total} ({pct:.0f}%)")

    results = runner.run(doe, n_workers=1, progress_callback=progress_callback)

    # Check for errors
    n_errors = results["meta.error"].notna().sum()
    if n_errors > 0:
        print(f"\nWarning: {n_errors} cases had errors")

    # =========================================================================
    # 6. Filter Feasible Designs
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
    # 7. Extract Pareto Frontier
    # =========================================================================
    print("\n" + "-" * 70)
    print("Extracting Pareto frontier...")

    # Minimize cost, maximize EIRP
    objectives = [
        ("cost_usd", "minimize"),
        ("eirp_dbw", "maximize"),
    ]

    pareto = extract_pareto(feasible, objectives)
    print(f"Pareto-optimal designs: {len(pareto)}")

    # Rank Pareto points
    ranked_pareto = rank_pareto(pareto, objectives, weights=[0.5, 0.5])

    print("\nTop 5 Pareto-optimal designs:")
    print("-" * 60)
    top_5 = ranked_pareto.head(5)
    for _, row in top_5.iterrows():
        print(
            f"  {row['case_id']}: "
            f"Cost=${row['cost_usd']:,.0f}, "
            f"EIRP={row['eirp_dbw']:.1f} dBW, "
            f"Margin={row['link_margin_db']:.1f} dB, "
            f"Array={int(row['array.nx'])}x{int(row['array.ny'])}"
        )

    # =========================================================================
    # 8. Visualize Results
    # =========================================================================
    print("\n" + "-" * 70)
    print("Generating visualizations...")

    # Create output directory
    output_dir = Path("./results/comms_doe")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Pareto plot: Cost vs EIRP
    fig1 = pareto_plot(
        results,
        x="cost_usd",
        y="eirp_dbw",
        pareto_front=pareto,
        feasible_mask=feasible_mask,
        color_by="link_margin_db",
        title="Cost vs EIRP Trade Space",
        x_label="Total Cost (USD)",
        y_label="EIRP (dBW)",
    )
    fig1.savefig(output_dir / "pareto_cost_eirp.png", dpi=150, bbox_inches="tight")
    print("  Saved: pareto_cost_eirp.png")

    # Pareto plot: Cost vs Link Margin
    fig2 = pareto_plot(
        results,
        x="cost_usd",
        y="link_margin_db",
        pareto_front=extract_pareto(
            feasible, [("cost_usd", "minimize"), ("link_margin_db", "maximize")]
        ),
        feasible_mask=feasible_mask,
        color_by="eirp_dbw",
        title="Cost vs Link Margin Trade Space",
        x_label="Total Cost (USD)",
        y_label="Link Margin (dB)",
    )
    fig2.savefig(output_dir / "pareto_cost_margin.png", dpi=150, bbox_inches="tight")
    print("  Saved: pareto_cost_margin.png")

    # Scatter matrix of key metrics
    fig3 = scatter_matrix(
        feasible,
        columns=["cost_usd", "eirp_dbw", "link_margin_db", "prime_power_w"],
        color_by="n_elements",
        title="Trade Space Scatter Matrix (Feasible Designs)",
    )
    fig3.savefig(output_dir / "scatter_matrix.png", dpi=150, bbox_inches="tight")
    print("  Saved: scatter_matrix.png")

    plt.close("all")

    # =========================================================================
    # 9. Export Results
    # =========================================================================
    print("\n" + "-" * 70)
    print("Exporting results...")

    # Export all results
    export_results(results, output_dir / "all_results.parquet")
    print(f"  Saved: all_results.parquet ({len(results)} cases)")

    # Export feasible results
    export_results(feasible, output_dir / "feasible_results.parquet")
    print(f"  Saved: feasible_results.parquet ({len(feasible)} cases)")

    # Export Pareto front
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
            f"    Array size: {int(best['array.nx'])}x{int(best['array.ny'])} ({int(best['n_elements'])} elements)"
        )
        print(f"    TX power/element: {best['rf.tx_power_w_per_elem']:.2f} W")
        print(f"    EIRP: {best['eirp_dbw']:.1f} dBW")
        print(f"    Link margin: {best['link_margin_db']:.1f} dB")
        print(f"    Total cost: ${best['cost_usd']:,.0f}")
        print(f"    Prime power: {best['prime_power_w']:.0f} W")

    print("\n" + "=" * 70)

    return results, pareto, ranked_pareto


if __name__ == "__main__":
    results, pareto, ranked = main()
