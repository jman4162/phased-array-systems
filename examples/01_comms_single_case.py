#!/usr/bin/env python3
"""
Example 01: Single-Case Communications Link Budget Evaluation

This example demonstrates how to:
1. Define an architecture (array, RF chain, cost parameters)
2. Define a communications scenario
3. Define requirements
4. Evaluate the case and verify requirements
5. Inspect the results

This is the simplest usage pattern - evaluating a single design point.
"""

from phased_array_systems.architecture import (
    Architecture,
    ArrayConfig,
    CostConfig,
    RFChainConfig,
)
from phased_array_systems.evaluate import evaluate_case_with_report
from phased_array_systems.requirements import Requirement, RequirementSet
from phased_array_systems.scenarios import CommsLinkScenario


def main():
    # =========================================================================
    # 1. Define the Architecture
    # =========================================================================
    print("=" * 60)
    print("Phased Array Communications Link Budget Example")
    print("=" * 60)

    # Array configuration: 8x8 rectangular array with half-wavelength spacing
    array_config = ArrayConfig(
        geometry="rectangular",
        nx=8,
        ny=8,
        dx_lambda=0.5,
        dy_lambda=0.5,
        scan_limit_deg=60.0,
    )

    # RF chain configuration
    rf_config = RFChainConfig(
        tx_power_w_per_elem=1.0,  # 1W per element
        pa_efficiency=0.3,  # 30% PA efficiency
        noise_figure_db=3.0,  # 3 dB noise figure
        feed_loss_db=1.0,  # 1 dB feed network loss
    )

    # Cost configuration
    cost_config = CostConfig(
        cost_per_elem_usd=100.0,  # $100 per element
        nre_usd=10000.0,  # $10k NRE
        integration_cost_usd=5000.0,  # $5k integration
    )

    # Combine into architecture
    architecture = Architecture(
        array=array_config,
        rf=rf_config,
        cost=cost_config,
        name="8x8 X-band Array",
    )

    print(f"\nArchitecture: {architecture.name}")
    print(f"  Array: {array_config.nx}x{array_config.ny} = {architecture.n_elements} elements")
    print(
        f"  Sub-arrays: {array_config.n_subarrays_x}x{array_config.n_subarrays_y} = {array_config.n_subarrays} total"
    )
    print(f"  TX Power/Element: {rf_config.tx_power_w_per_elem} W")
    print(f"  Total TX Power: {architecture.n_elements * rf_config.tx_power_w_per_elem} W")

    # =========================================================================
    # 2. Define the Scenario
    # =========================================================================
    scenario = CommsLinkScenario(
        freq_hz=10e9,  # 10 GHz (X-band)
        bandwidth_hz=10e6,  # 10 MHz bandwidth
        range_m=100e3,  # 100 km range
        required_snr_db=10.0,  # 10 dB required SNR
        scan_angle_deg=0.0,  # Boresight pointing
        rx_antenna_gain_db=0.0,  # Isotropic receive antenna
        rx_noise_temp_k=290.0,  # Room temperature noise
        path_loss_model="fspl",  # Free space path loss
    )

    print("\nScenario:")
    print(f"  Frequency: {scenario.freq_hz / 1e9:.1f} GHz")
    print(f"  Bandwidth: {scenario.bandwidth_hz / 1e6:.1f} MHz")
    print(f"  Range: {scenario.range_m / 1e3:.1f} km")
    print(f"  Required SNR: {scenario.required_snr_db} dB")

    # =========================================================================
    # 3. Define Requirements
    # =========================================================================
    requirements = RequirementSet(
        requirements=[
            Requirement(
                id="REQ-001",
                name="Minimum EIRP",
                metric_key="eirp_dbw",
                op=">=",
                value=40.0,
                units="dBW",
                severity="must",
            ),
            Requirement(
                id="REQ-002",
                name="Positive Link Margin",
                metric_key="link_margin_db",
                op=">=",
                value=0.0,
                units="dB",
                severity="must",
            ),
            Requirement(
                id="REQ-003",
                name="Maximum Cost",
                metric_key="cost_usd",
                op="<=",
                value=50000.0,
                units="USD",
                severity="must",
            ),
            Requirement(
                id="REQ-004",
                name="Preferred Margin",
                metric_key="link_margin_db",
                op=">=",
                value=6.0,
                units="dB",
                severity="should",
            ),
        ],
        name="Comms Array Requirements",
    )

    print(f"\nRequirements: {len(requirements)} defined")
    for req in requirements:
        print(
            f"  [{req.severity.upper()}] {req.id}: {req.name} ({req.metric_key} {req.op} {req.value})"
        )

    # =========================================================================
    # 4. Evaluate the Case
    # =========================================================================
    print("\n" + "=" * 60)
    print("Evaluation Results")
    print("=" * 60)

    metrics, report = evaluate_case_with_report(
        architecture, scenario, requirements, case_id="CASE-001"
    )

    # Print key metrics
    print("\nAntenna Metrics:")
    print(f"  Peak Gain: {metrics['g_peak_db']:.2f} dB")
    print(f"  Directivity: {metrics['directivity_db']:.2f} dB")
    print(f"  Beamwidth (Az): {metrics['beamwidth_az_deg']:.2f} deg")
    print(f"  Beamwidth (El): {metrics['beamwidth_el_deg']:.2f} deg")
    print(f"  Sidelobe Level: {metrics['sll_db']:.2f} dB")
    print(f"  Scan Loss: {metrics['scan_loss_db']:.2f} dB")

    print("\nLink Budget:")
    print(f"  EIRP: {metrics['eirp_dbw']:.2f} dBW")
    print(f"  Path Loss: {metrics['path_loss_db']:.2f} dB")
    print(f"  RX Power: {metrics['rx_power_dbw']:.2f} dBW")
    print(f"  Noise Power: {metrics['noise_power_dbw']:.2f} dBW")
    print(f"  SNR: {metrics['snr_rx_db']:.2f} dB")
    print(f"  Link Margin: {metrics['link_margin_db']:.2f} dB")

    print("\nSWaP-C:")
    print(f"  RF Power: {metrics['rf_power_w']:.1f} W")
    print(f"  DC Power: {metrics['dc_power_w']:.1f} W")
    print(f"  Prime Power: {metrics['prime_power_w']:.1f} W")
    print(f"  Total Cost: ${metrics['cost_usd']:,.0f}")

    # =========================================================================
    # 5. Requirements Verification
    # =========================================================================
    print("\n" + "=" * 60)
    print("Requirements Verification")
    print("=" * 60)

    status = "PASS" if report.passes else "FAIL"
    print(f"\nOverall Status: {status}")
    print(f"Must Requirements: {report.must_pass_count}/{report.must_total_count} passed")
    print(f"Should Requirements: {report.should_pass_count}/{report.should_total_count} passed")

    print("\nDetailed Results:")
    for result in report.results:
        req = result.requirement
        status_str = "PASS" if result.passes else "FAIL"
        if result.actual_value is not None:
            print(
                f"  [{status_str}] {req.id}: {req.name}"
                f"\n         Actual: {result.actual_value:.2f}, "
                f"Required: {req.op} {req.value}, "
                f"Margin: {result.margin:+.2f}"
            )
        else:
            print(f"  [{status_str}] {req.id}: {result.error}")

    print(f"\nRuntime: {metrics['meta.runtime_s'] * 1000:.2f} ms")
    print("\n" + "=" * 60)

    return metrics, report


if __name__ == "__main__":
    main()
