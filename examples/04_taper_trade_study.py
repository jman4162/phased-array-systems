#!/usr/bin/env python3
"""
Example 04: Taper Trade Study

This example demonstrates how to:
1. Compare different amplitude taper types across array sizes
2. Evaluate SLL vs. gain trade-offs for each taper
3. Show how taper choice affects beamwidth and sidelobe levels
4. Visualize the Pareto frontier of SLL vs. peak gain

Taper types: uniform, taylor, chebyshev, hamming, cosine, gaussian
"""

import pandas as pd

from phased_array_systems.architecture import (
    Architecture,
    ArrayConfig,
    CostConfig,
    RFChainConfig,
)
from phased_array_systems.evaluate import evaluate_case
from phased_array_systems.scenarios import CommsLinkScenario


def main():
    print("=" * 60)
    print("Taper Trade Study: SLL vs. Gain vs. Beamwidth")
    print("=" * 60)

    # Fixed scenario
    scenario = CommsLinkScenario(
        freq_hz=10e9,
        bandwidth_hz=10e6,
        range_m=50e3,
        required_snr_db=10.0,
        path_loss_model="fspl",
    )

    # Sweep parameters
    taper_types = ["uniform", "taylor", "chebyshev", "hamming", "cosine", "gaussian"]
    array_sizes = [4, 8, 16]

    results = []

    for nx in array_sizes:
        for taper in taper_types:
            arch = Architecture(
                array=ArrayConfig(
                    nx=nx,
                    ny=nx,
                    dx_lambda=0.5,
                    dy_lambda=0.5,
                    taper_type=taper,
                    taper_sll_db=-30.0,
                    enforce_subarray_constraint=False,
                ),
                rf=RFChainConfig(tx_power_w_per_elem=1.0),
                cost=CostConfig(cost_per_elem_usd=100.0),
            )

            metrics = evaluate_case(arch, scenario, case_id=f"{nx}x{nx}_{taper}")

            results.append(
                {
                    "case_id": f"{nx}x{nx}_{taper}",
                    "nx": nx,
                    "n_elements": nx * nx,
                    "taper_type": taper,
                    "g_peak_db": metrics.get("g_peak_db", 0),
                    "sll_db": metrics.get("sll_db", 0),
                    "beamwidth_az_deg": metrics.get("beamwidth_az_deg", 0),
                    "taper_loss_db": metrics.get("taper_loss_db", 0),
                    "eirp_dbw": metrics.get("eirp_dbw", 0),
                    "link_margin_db": metrics.get("link_margin_db", 0),
                    "cost_usd": metrics.get("cost_usd", 0),
                }
            )

    df = pd.DataFrame(results)

    # Display results grouped by array size
    for nx in array_sizes:
        subset = df[df["nx"] == nx]
        print(f"\n--- {nx}x{nx} Array ({nx * nx} elements) ---")
        print(f"{'Taper':<12} {'Gain(dB)':>9} {'SLL(dB)':>9} {'BW(deg)':>9} {'Taper Loss':>11}")
        print("-" * 55)
        for _, row in subset.iterrows():
            print(
                f"{row['taper_type']:<12} {row['g_peak_db']:>9.2f} {row['sll_db']:>9.2f} "
                f"{row['beamwidth_az_deg']:>9.2f} {row['taper_loss_db']:>11.2f}"
            )

    # Summary: best SLL and best gain for each array size
    print("\n" + "=" * 60)
    print("Summary: Trade-offs by Array Size")
    print("=" * 60)
    for nx in array_sizes:
        subset = df[df["nx"] == nx]
        best_sll = subset.loc[subset["sll_db"].idxmin()]
        best_gain = subset.loc[subset["g_peak_db"].idxmax()]
        print(f"\n{nx}x{nx} Array:")
        print(
            f"  Best SLL:  {best_sll['taper_type']} "
            f"(SLL={best_sll['sll_db']:.1f} dB, Gain={best_sll['g_peak_db']:.1f} dB)"
        )
        print(
            f"  Best Gain: {best_gain['taper_type']} "
            f"(Gain={best_gain['g_peak_db']:.1f} dB, SLL={best_gain['sll_db']:.1f} dB)"
        )

    print(f"\nTotal cases evaluated: {len(df)}")
    return df


if __name__ == "__main__":
    main()
