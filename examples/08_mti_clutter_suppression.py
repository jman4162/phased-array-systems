"""MTI canceller selection for a ground-based radar in clutter.

Reproduces the ARSR-3 L-band air traffic control case: how much clutter
attenuation the geometry demands, what each binomial canceller delivers, and
which is the shortest that suffices. The final block runs the same geometry
through the full detection chain to show what the filter is worth.

Run:
    python examples/08_mti_clutter_suppression.py
"""

import math

from phased_array_systems import Architecture, ArrayConfig, RFChainConfig, evaluate_case
from phased_array_systems.models.radar.clutter import compute_resolution_cell_area
from phased_array_systems.models.radar.mti import (
    blind_speed_ms,
    clutter_spectral_std_hz,
    mti_clutter_attenuation,
    mti_improvement_factor,
    mti_signal_gain,
    normalized_clutter_spread_rad,
    required_clutter_attenuation_db,
    unambiguous_range_m,
)
from phased_array_systems.scenarios import RadarDetectionScenario

C = 299792458.0
FREQ_HZ = 1.3e9
LAMBDA_M = C / FREQ_HZ
PRF_HZ = 400.0
PULSE_WIDTH_S = 2e-6
AZ_BEAMWIDTH_DEG = 1.25
SIGMA0_DB = -20.0
CLUTTER_V_STD_MS = 1.16 * 1000.0 / 3600.0
TARGET_RCS_DBSM = 3.0
TARGET_RANGE_M = 55.56e3
REQUIRED_SCR_DB = 15.0


def main() -> None:
    print("ARSR-3 L-band ATC radar, wooded-hill clutter\n")
    print(f"  wavelength          {LAMBDA_M:.4f} m")
    print(f"  unambiguous range   {unambiguous_range_m(PRF_HZ) / 1e3:.0f} km")
    print(f"  first blind speed   {blind_speed_ms(PRF_HZ, LAMBDA_M):.1f} m/s")

    range_res_m = C * PULSE_WIDTH_S / 2.0
    cell_area = compute_resolution_cell_area(TARGET_RANGE_M, range_res_m, AZ_BEAMWIDTH_DEG)
    clutter_rcs = cell_area * 10 ** (SIGMA0_DB / 10)
    clutter_dbsm = 10 * math.log10(clutter_rcs)
    ca_req = required_clutter_attenuation_db(TARGET_RCS_DBSM, clutter_dbsm, REQUIRED_SCR_DB)

    print(f"\n  clutter cell area   {cell_area:.3e} m^2")
    print(f"  clutter RCS         {clutter_rcs:.0f} m^2 = {clutter_dbsm:.1f} dBsm")
    print(f"  target RCS          {TARGET_RCS_DBSM:.1f} dBsm")
    print(f"  required S/C        {REQUIRED_SCR_DB:.0f} dB")
    print(f"  -> attenuation need {ca_req:.1f} dB")

    sigma_omega = normalized_clutter_spread_rad(
        clutter_spectral_std_hz(CLUTTER_V_STD_MS, LAMBDA_M), PRF_HZ
    )
    print(f"\n  clutter spread      sigma_omega = {sigma_omega:.4f} rad\n")

    header = f"  {'N':>2}  {'I dB':>7}  {'G dB':>6}  {'CA dB':>7}   verdict"
    print(header)
    print("  " + "-" * (len(header) - 2))
    for n in (2, 3, 4):
        i_db = 10 * math.log10(mti_improvement_factor(n, sigma_omega))
        g_db = 10 * math.log10(mti_signal_gain(n))
        ca_db = 10 * math.log10(mti_clutter_attenuation(n, sigma_omega))
        verdict = "meets requirement" if ca_db >= ca_req else "insufficient"
        print(f"  {n:>2}  {i_db:>7.1f}  {g_db:>6.1f}  {ca_db:>7.1f}   {verdict}")

    print("\n  The three-pulse canceller is the shortest that suffices.")

    # What the filter is actually worth, through the full detection chain.
    arch = Architecture(
        array=ArrayConfig(nx=32, ny=32, dx_lambda=0.5, dy_lambda=0.5),
        rf=RFChainConfig(tx_power_w_per_elem=10.0, pa_efficiency=0.30, noise_figure_db=3.0),
    )
    print(f"\n  {'MTI':>5}  {'SCR dB':>7}  {'SCNR dB':>8}  {'Pd':>6}")
    print("  " + "-" * 32)
    for n_pulse in (None, 2, 3):
        scenario = RadarDetectionScenario(
            freq_hz=FREQ_HZ,
            bandwidth_hz=1.0 / PULSE_WIDTH_S,
            range_m=TARGET_RANGE_M,
            target_rcs_dbsm=TARGET_RCS_DBSM,
            n_pulses=10,
            prf_hz=PRF_HZ,
            clutter_type="ground",
            terrain_type="rural",
            mti_n_pulse=n_pulse,
            clutter_velocity_std_ms=CLUTTER_V_STD_MS,
        )
        m = evaluate_case(arch, scenario)
        label = "off" if n_pulse is None else str(n_pulse)
        print(f"  {label:>5}  {m['scr_db']:>7.1f}  {m['scnr_db']:>8.1f}  {m['pd_achieved']:>6.3f}")

    print("\n  Without the canceller the target is undetectable in its own clutter.")


if __name__ == "__main__":
    main()
