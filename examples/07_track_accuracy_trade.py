"""Track accuracy versus aperture size.

Cross-range error is a fixed fraction of a beamwidth times the range. Growing
the array narrows the beam and raises the gain, so cross-range accuracy
improves on two counts while range accuracy improves only through SNR. This
sweep shows both measurement errors and the steady-state track error that
follows.

Run:
    python examples/07_track_accuracy_trade.py
"""

from phased_array_systems import (
    Architecture,
    ArrayConfig,
    RFChainConfig,
    evaluate_case,
)
from phased_array_systems.scenarios import RadarDetectionScenario


def main() -> None:
    header = (
        f"{'N':>7}  {'SNR dB':>7}  {'BW deg':>7}  {'sig_R m':>8}  "
        f"{'sig_CR m':>9}  {'Gamma':>7}  {'track m':>8}"
    )
    print("X-band, 50 km, 0 dBsm target, 4 g maneuver, 1 Hz track revisit")
    print("Transmit power is 10 W per element and is held fixed, so total")
    print("power grows with the array: 2.6 kW at 16^2 to 164 kW at 128^2.\n")
    print(header)
    print("-" * len(header))

    for n in (16, 32, 64, 128):
        arch = Architecture(
            array=ArrayConfig(nx=n, ny=n, dx_lambda=0.5, dy_lambda=0.5),
            rf=RFChainConfig(tx_power_w_per_elem=10.0, pa_efficiency=0.30, noise_figure_db=3.0),
        )
        scenario = RadarDetectionScenario(
            freq_hz=10e9,
            bandwidth_hz=10e6,
            range_m=50e3,
            target_rcs_dbsm=0.0,
            n_pulses=64,
            prf_hz=5000,
            integration_type="coherent",
            track_revisit_s=1.0,
            target_accel_max_ms2=40.0,
        )
        m = evaluate_case(arch, scenario)
        print(
            f"{n:>5}^2  {m['snr_integrated_db']:>7.1f}  {m['beamwidth_az_deg']:>7.2f}  "
            f"{m['sigma_range_m']:>8.2f}  {m['sigma_crossrange_az_m']:>9.1f}  "
            f"{m['track_index_crossrange']:>7.2f}  "
            f"{m['track_pos_rms_crossrange_m']:>8.1f}"
        )

    print(
        "\nBoth errors fall as the array grows. With per-element power fixed,\n"
        "transmit power and both antenna gains each rise with element count M,\n"
        "so SNR rises as M^3: +18 dB per doubling of a side, and every accuracy\n"
        "term carries 1/sqrt(SNR), giving 8x. Under fixed *total* power SNR\n"
        "would rise as M^2 and range accuracy would improve 4x per doubling.\n"
        "Cross-range falls faster by one further factor of N, because beamwidth\n"
        "narrows too, so the cross-range/range ratio halves on each doubling\n"
        "(115x, 57x, 29x). That ratio is SNR-independent, so it is the part of\n"
        "this sweep that is purely geometric.\n"
        "At fixed SNR the split is clean: bandwidth sets range accuracy,\n"
        "aperture sets cross-range, and cross-range dominates the track.\n"
        "\nTwo caveats the numbers do not carry. The 16^2 and 32^2 rows sit\n"
        "below MONOPULSE_SNR_FLOOR_DB (13 dB), where POMR Eq. (18.63) is\n"
        "optimistic and biased, and the 16^2 row is not detectable at all.\n"
        "All sigmas are thermal-noise terms only: Curry Eq. (8.5) adds fixed\n"
        "and bias errors in quadrature, which floor the 128^2 range figure well\n"
        "above 7 cm in any real radar."
    )


if __name__ == "__main__":
    main()
