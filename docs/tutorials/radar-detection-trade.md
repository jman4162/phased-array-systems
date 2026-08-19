# Tutorial: Radar Detection Trade Study

Design and optimize a phased array radar for target detection.

## Objective

By the end of this tutorial, you will:

- Configure a radar detection scenario
- Set radar-specific requirements
- Explore the power-aperture trade-off
- Analyze detection performance across designs

## Scenario

Design a search radar to detect a **1 m² target at 100 km** with:

- 90% detection probability
- 10⁻⁶ false alarm probability
- Budget constraint of $500,000

## Step 1: Setup

```python
"""Radar detection trade study tutorial."""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path

from phased_array_systems.architecture import Architecture, ArrayConfig, RFChainConfig, CostConfig
from phased_array_systems.scenarios import RadarDetectionScenario
from phased_array_systems.requirements import Requirement, RequirementSet
from phased_array_systems.evaluate import evaluate_case
from phased_array_systems.trades import (
    DesignSpace,
    generate_doe,
    BatchRunner,
    filter_feasible,
    extract_pareto,
    rank_pareto,
)
from phased_array_systems.viz import pareto_plot, scatter_matrix
from phased_array_systems.io import export_results
```

## Step 2: Define the Scenario

```python
scenario = RadarDetectionScenario(
    # Operating frequency
    freq_hz=10e9,              # X-band

    # Target characteristics
    target_rcs_dbsm=0.0,       # 1 m^2 RCS, expressed in dBsm
    range_m=100e3,             # 100 km detection range

    # Detection requirements
    pd_required=0.9,           # 90% detection probability
    pfa=1e-6,                  # 1e-6 false alarm rate

    # Waveform parameters
    bandwidth_hz=100e3,        # matched to a 10 us pulse
    prf_hz=1000,               # 1 kHz PRF

    # Integration
    n_pulses=10,               # Integrate 10 pulses
    integration_type="coherent",  # Coherent integration

    # Target model
    swerling=1,                # Swerling 1 (slow fluctuation)

    # Scan
    scan_angle_deg=0.0,        # Boresight
)

print(f"Radar Scenario:")
print(f"  Frequency: {scenario.freq_hz/1e9:.1f} GHz")
print(f"  Target RCS: {scenario.target_rcs_m2} m²")
print(f"  Range: {scenario.range_m/1e3:.0f} km")
print(f"  Required Pd: {scenario.pd_required}")
print(f"  Pfa: {scenario.pfa}")
print(f"  Integration: {scenario.n_pulses} pulses ({scenario.integration_type})")
```

## Step 3: Define Requirements

```python
requirements = RequirementSet(
    requirements=[
        Requirement(
            id="DET-001",
            name="Positive SNR Margin",
            metric_key="snr_margin_db",
            op=">=",
            value=0.0,
            units="dB",
            severity="must",
        ),
        Requirement(
            id="DET-002",
            name="5 dB SNR Margin",
            metric_key="snr_margin_db",
            op=">=",
            value=5.0,
            units="dB",
            severity="should",
        ),
        Requirement(
            id="COST-001",
            name="Maximum Cost",
            metric_key="cost_usd",
            op="<=",
            value=500000.0,
            units="USD",
            severity="must",
        ),
        Requirement(
            id="PWR-001",
            name="Maximum Power",
            metric_key="prime_power_w",
            op="<=",
            value=10000.0,
            units="W",
            severity="must",
        ),
    ],
    name="Radar Detection Requirements",
)

print(f"\nRequirements: {len(requirements)} defined")
for req in requirements:
    print(f"  {req.id}: {req.name}")
```

## Step 4: Define the Design Space

```python
design_space = (
    DesignSpace(name="Radar Array Trade Study")
    # Array size (power-of-2 for sub-array constraints)
    .add_variable("array.nx", type="categorical", values=[8, 16, 32])
    .add_variable("array.ny", type="categorical", values=[8, 16, 32])
    # TX power per element (significant range for radar)
    .add_variable("rf.tx_power_w_per_elem", type="float", low=5.0, high=30.0)
    # PA efficiency
    .add_variable("rf.pa_efficiency", type="float", low=0.15, high=0.35)
    # Cost per element (radar modules more expensive)
    .add_variable("cost.cost_per_elem_usd", type="float", low=200.0, high=500.0)
    # Fixed parameters
    .add_variable("array.geometry", type="categorical", values=["rectangular"])
    .add_variable("array.dx_lambda", type="float", low=0.5, high=0.5)
    .add_variable("array.dy_lambda", type="float", low=0.5, high=0.5)
    .add_variable("array.enforce_subarray_constraint", type="categorical", values=[True])
    .add_variable("rf.noise_figure_db", type="float", low=4.0, high=4.0)
    .add_variable("rf.n_tx_beams", type="int", low=1, high=1)
    .add_variable("rf.feed_loss_db", type="float", low=1.5, high=1.5)
    .add_variable("cost.nre_usd", type="float", low=50000.0, high=50000.0)
    .add_variable("cost.integration_cost_usd", type="float", low=25000.0, high=25000.0)
)

print(f"\nDesign Space: {design_space.n_dims} dimensions")
```

## Step 5: Quick Baseline Check

```python
# Evaluate a baseline design first
baseline = Architecture(
    array=ArrayConfig(nx=16, ny=16, dx_lambda=0.5, dy_lambda=0.5),
    rf=RFChainConfig(tx_power_w_per_elem=10.0, pa_efficiency=0.25, noise_figure_db=4.0),
    cost=CostConfig(cost_per_elem_usd=300.0, nre_usd=50000.0, integration_cost_usd=25000.0),
    name="Baseline 16x16",
)

baseline_metrics = evaluate_case(baseline, scenario)

print(f"\nBaseline Design: 16×16 array, 10 W/elem")
print(f"  Single-Pulse SNR: {baseline_metrics['snr_single_pulse_db']:.1f} dB")
print(f"  Integrated SNR: {baseline_metrics['snr_integrated_db']:.1f} dB")
print(f"  Required SNR: {baseline_metrics['snr_required_db']:.1f} dB")
print(f"  SNR Margin: {baseline_metrics['snr_margin_db']:.1f} dB")
print(f"  Cost: ${baseline_metrics['cost_usd']:,.0f}")
print(f"  Prime Power: {baseline_metrics['prime_power_w']:.0f} W")

# Check requirements
report = requirements.verify(baseline_metrics)
print(f"  Requirements: {'PASS' if report.passes else 'FAIL'}")
```

## Step 6: Run DOE

```python
n_samples = 100
seed = 42

doe = generate_doe(design_space, method="lhs", n_samples=n_samples, seed=seed)
print(f"\nGenerated {len(doe)} DOE cases")

runner = BatchRunner(scenario, requirements)

def progress(completed, total):
    if completed % 25 == 0 or completed == total:
        print(f"  Progress: {completed}/{total}")

print("\nRunning batch evaluation...")
results = runner.run(doe, n_workers=1, progress_callback=progress)
print(f"Completed: {len(results)} cases")
```

## Step 7: Analyze Results

```python
feasible_mask = results["verification.passes"] == 1.0
feasible = filter_feasible(results, requirements)

print(f"\nResults Summary:")
print(f"  Total cases: {len(results)}")
print(f"  Feasible: {len(feasible)} ({len(feasible)/len(results)*100:.1f}%)")

print(f"\nSNR Margin Range:")
print(f"  All: {results['snr_margin_db'].min():.1f} to {results['snr_margin_db'].max():.1f} dB")
if len(feasible) > 0:
    print(f"  Feasible: {feasible['snr_margin_db'].min():.1f} to {feasible['snr_margin_db'].max():.1f} dB")

print(f"\nCost Range:")
print(f"  All: ${results['cost_usd'].min():,.0f} to ${results['cost_usd'].max():,.0f}")
if len(feasible) > 0:
    print(f"  Feasible: ${feasible['cost_usd'].min():,.0f} to ${feasible['cost_usd'].max():,.0f}")
```

## Step 8: Pareto Analysis

```python
if len(feasible) > 0:
    objectives = [
        ("cost_usd", "minimize"),
        ("snr_margin_db", "maximize"),
    ]

    pareto = extract_pareto(feasible, objectives)
    ranked = rank_pareto(pareto, objectives, weights=[0.5, 0.5])

    print(f"\nPareto-optimal designs: {len(pareto)}")
    print("\nTop 5 Designs:")
    print("-" * 70)
    for i, (_, row) in enumerate(ranked.head(5).iterrows()):
        print(f"  #{i+1}: {row['case_id']}")
        print(f"      Array: {int(row['array.nx'])}×{int(row['array.ny'])} ({int(row['n_elements'])} elements)")
        print(f"      TX Power: {row['rf.tx_power_w_per_elem']:.1f} W/elem")
        print(f"      SNR Margin: {row['snr_margin_db']:.1f} dB")
        print(f"      Cost: ${row['cost_usd']:,.0f}")
        print(f"      Prime Power: {row['prime_power_w']:.0f} W")
else:
    print("\nNo feasible designs found. Consider relaxing requirements.")
    pareto = None
    ranked = None
```

## Step 9: Visualize

```python
output_dir = Path("./radar_tutorial_results")
output_dir.mkdir(exist_ok=True)

# Cost vs SNR Margin
fig1 = pareto_plot(
    results,
    x="cost_usd",
    y="snr_margin_db",
    pareto_front=pareto,
    feasible_mask=feasible_mask,
    color_by="n_elements",
    title="Cost vs SNR Margin Trade Space",
    x_label="Total Cost (USD)",
    y_label="SNR Margin (dB)",
)
fig1.savefig(output_dir / "pareto_cost_snr.png", dpi=150, bbox_inches="tight")

# Power vs Performance
fig2 = pareto_plot(
    results,
    x="prime_power_w",
    y="snr_margin_db",
    feasible_mask=feasible_mask,
    color_by="cost_usd",
    title="Power vs SNR Margin",
    x_label="Prime Power (W)",
    y_label="SNR Margin (dB)",
)
fig2.savefig(output_dir / "pareto_power_snr.png", dpi=150, bbox_inches="tight")

# Scatter matrix
if len(feasible) > 5:
    fig3 = scatter_matrix(
        feasible,
        columns=["cost_usd", "snr_margin_db", "prime_power_w", "n_elements"],
        color_by="snr_margin_db",
        title="Trade Space Correlations",
    )
    fig3.savefig(output_dir / "scatter_matrix.png", dpi=150, bbox_inches="tight")

plt.close("all")
print(f"\nFigures saved to: {output_dir}")
```

## Step 10: Power-Aperture Trade-off

```python
# Analyze power-aperture product
if len(feasible) > 0:
    feasible["power_aperture"] = feasible["prime_power_w"] * feasible["n_elements"]

    print("\nPower-Aperture Analysis:")
    print(f"  PA Product Range: {feasible['power_aperture'].min():.0f} to {feasible['power_aperture'].max():.0f}")

    # Group by array size
    for nx in [8, 16, 32]:
        subset = feasible[feasible["array.nx"] == nx]
        if len(subset) > 0:
            print(f"\n  {nx}×{nx} arrays ({nx*nx} elements):")
            print(f"    Count: {len(subset)}")
            print(f"    Avg SNR Margin: {subset['snr_margin_db'].mean():.1f} dB")
            print(f"    Avg Cost: ${subset['cost_usd'].mean():,.0f}")
```

## Step 11: Export Results

```python
export_results(results, output_dir / "all_results.parquet")
export_results(feasible, output_dir / "feasible_results.parquet")
if ranked is not None:
    export_results(ranked, output_dir / "pareto_ranked.csv", format="csv")

print(f"\nResults exported to: {output_dir}")
```

## Key Insights

### Power-Aperture Trade-off

The radar equation shows that SNR scales with:

\\[
SNR \propto P_t \cdot A^2 \propto P_t \cdot N^2
\\]

Where \\(N\\) is element count. This means:
- Doubling power → 3 dB improvement
- Doubling elements → 6 dB improvement (but higher cost)

### Array Size Selection

| Size | Elements | Typical Use |
|------|----------|-------------|
| 8×8 | 64 | Short range, low cost |
| 16×16 | 256 | Medium range, balanced |
| 32×32 | 1024 | Long range, high performance |

### Swerling Model Impact

- Swerling 0 (steady): Requires lowest SNR
- Swerling 1 (slow): Requires ~2-3 dB more
- Higher models: Additional SNR needed

## Next Steps

- [Communications Trade Study](comms-trade-study.md) - Compare with comms workflow
- [Sensitivity Analysis](sensitivity-analysis.md) - Parameter sensitivity
- [Theory: Radar Equation](../theory/radar-equation.md) - Detailed equations
