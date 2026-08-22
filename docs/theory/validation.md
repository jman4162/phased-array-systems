# Model Validation

Every physics model with published reference data is validated against
that data in CI (`tests/test_validation.py`). The table below lists the
model, its source, the reference points checked, and the asserted
tolerance. Models without an external reference are checked against
independent hand assemblies of their governing equations or exact
closed-form identities.

| Model | Reference | Checked against | Tolerance |
|---|---|---|---|
| Gaseous attenuation (line-by-line) | ITU-R P.676-13, Annex 1 | γ at 10, 22.235, 60, 94, 118.75, 183.31 GHz, standard surface conditions, cross-checked with ITU-Rpy | 2% |
| Rain specific attenuation k, α | ITU-R P.838-3, Tables 1–4 | k/α at 10, 20, 40, 100 GHz, H and V polarization | 0.1% |
| Sea clutter σ⁰ | NRL model, Gregers-Hansen & Mittal, NRL/MR/5310-12-9346 (2012); fits Nathanson tables within ~2.3 dB | Closed-form spot value (9.3 GHz, SS3, 1°, HH = −43.8 dB); VV > HH at low grazing; monotonicity | 0.05 dB (spot) |
| Ground clutter σ⁰ | Barton constant-γ model, published median γ per terrain | γ·sin ψ identity; terrain ordering | exact |
| CA-CFAR loss | Gregers-Hansen universal curve; Richards ch. 16 | 2.0 dB at N=16, 0.97 dB at N=32 (Pfa = 1e-6); monotonicity in N and Pfa | 0.1 dB |
| Detection probability (Swerling 0) | Marcum Q via noncentral χ² | `scipy.stats.ncx2.sf` identity; required SNR 13.18 dB at Pd=0.9/Pfa=1e-6 | exact / 0.15 dB |
| Detection probability (Swerling 1–4) | Gamma-mixture of noncentral χ² | Swerling 1 closed form Pfa^(1/(1+SNR)); Swerling 2 gamma closed form; SW1−SW0 penalty 7–9.5 dB at Pd=0.9 | 1e-6 |
| Albersheim's equation | Richards, *Fundamentals of Radar Signal Processing* | 13.1 dB (n=1), ~5.0 dB (n=10) at Pd=0.9/Pfa=1e-6; agreement with exact inversion | 0.2–0.3 dB |
| Radar range equation | Independent hand assembly | Full `RadarModel` vs Pt·G²λ²σ/((4π)³R⁴LkT_sysB); R⁻⁴ and σ scaling laws | 1e-6 dB |
| System noise temperature | T_sys = T_ant + T₀(F−1) | Identity with kTB+NF at 290 K; satcom case T_ant=60 K, NF=1 dB → T_sys=135.1 K | exact |
| Friis cascade | Pozar, *Microwave Engineering* | 3-stage textbook chain; stage contributions sum to 100% | exact |
| ADC quantization SNR | 6.02·ENOB + 1.76 dB | 12-bit → 74.0 dB | 0.1 dB |
| ADC jitter SNR | −20·log₁₀(2πf·t_j) | 1 ps at 1 GHz → 44.03 dB | 0.02 dB |
| Phase quantization loss | Mailloux ch. 7 | 3 bits → 0.223 dB, Ruze form | 0.01 dB |
| Taper loss | scipy window functions | Computed from actual windows (no fitted curves); Taylor −30 dB → 0.69 dB | exact |
| Search timeline | Beam-packing identity | Frame time = ceil(Ω_search/Ω_beam)·(dwell+overhead), hand-reproduced | 1e-9 |
| Aperture power density | Unit-cell geometry + energy balance | (lambda/2)^2 cell at 10 GHz = 2.2469 cm^2 hand value; f^2 scaling X to Ka = 9x; total/aperture equals per-element/cell | exact |
| Power-aperture product | Barton/Skolnik search relation | A_e = G lambda^2/4pi; required P*A scales as R^4 and 1/t_s | exact |
| Clutter Doppler spread | Skolnik ch. 15 | sigma_c = 2 sigma_v/lambda; 1.16 km/hr at 1.3 GHz -> 2.79 Hz, sigma_omega = 0.0438 rad | 0.01 Hz |
| MTI improvement factor | Richards FRSP Eqs. (5.52)/(5.54) p. 247 | General quadratic form over binomial weights vs both published closed forms; two-pulse 30.2 dB, three-pulse 57.3 dB at sigma_omega = 0.0438 | 5e-8 (rel) / 0.1 dB |
| MTI signal gain | Richards FRSP p. 246 | G = sum w_k^2 by Parseval: 2 (3.0 dB) two-pulse, 6 (7.8 dB) three-pulse | exact |
| Clutter cell RCS | Independent worked case (ARSR-3, L-band ATC) | A_c = R theta_az (c tau/2) with sigma0 = -20 dB -> 3637 m^2 = 35.6 dBsm; required attenuation 47.6 dB | 0.5% / 0.05 dB |
| Range measurement accuracy | Curry, *Radar System Performance Modeling* 2e, Eq. (8.6) p. 168 | Worked example B=1 MHz, S/N=15 dB -> 18.9 m; 32%/10% of resolution at POMR p. 690 SNR points | 0.1 m / 0.005 |
| Angle measurement accuracy | Curry Eq. (8.8) p. 170; POMR Eq. (18.63) p. 706 | Worked example theta=1 deg, S/N=12 dB -> 1.9 mrad, k_m=1.6; validity floor SNR>13 dB recorded | 0.05 mrad |
| Scan broadening | Curry Eq. (8.9) p. 171 | 1 deg beam at 30 deg scan -> 1.15 deg, sigma 1.9 -> 2.2 mrad | 0.01 deg |
| Velocity accuracy | Curry Eq. (8.13) p. 172 (via Barton & Ward pp. 101-103) | Independent hand assembly lambda/(2 tau sqrt(2 SNR)) | 1e-12 |
| Tracking index and gains | POMR Eqs. (19.47)/(19.54)-(19.56) pp. 731-732; Kalata 1984 | Kalata relation identity; Gamma round-trip; Gamma=1 -> alpha=0.75, beta=0.50; alpha->1, beta->2 asymptotes (Fig. 19-14) | exact / 1e-10 |
| Process noise from maneuver | POMR Eqs. (19.63)/(19.66) p. 734 | Published worked example A=40 m/s^2, T=1 s, sigma_w=120 m -> Gamma_D=0.33, kappa=0.91, sigma_v=36.4 | 0.005 / 0.1 |
| Steady-state covariance (total) | POMR Eq. (19.53) p. 731 | Fixed-gain covariance recursion (Joseph form) iterated to convergence with process noise, sharing no code | 1e-9 / 1e-7 |
| Steady-state covariance (sensor-noise only) | Mahafza Eq. (11.94) ch. 11 | Same recursion with Q=0; canary asserts the incorrect circulating form (VRR>1) is not used | 1e-9 |
| Thermal-reliability coupling | Energy balance + Arrhenius | T_j = T_amb + R_th·(P_DC−P_RF)/N hand value; MTBF monotone in duty cycle | exact |

## Documented approximations

Where a model is deliberately simpler than the full reference, the
limitation is stated in the module docstring:

- **Slant-path atmospherics**: specific attenuation over
  min(range, equivalent-height/sin el) with h_O₂ = 6.1 km,
  h_H₂O = 2.4 km (away-from-line values); the layered integration of
  P.676 Annex 1 §2 is not implemented.
- **Effective rain path**: ITU-R P.530 distance factor applied to the
  scenario rain rate directly (P.530 defines it for the 0.01%-exceeded
  rate). **This is a terrestrial model and unsuitable for slant paths**:
  P.530 assumes the whole path sits in rain, while a satellite link exits
  the rain layer within a few kilometers of altitude. On a 28 GHz LEO
  link at 8 mm/h the P.530 form over the full slant range predicts tens
  of dB where ITU-R P.618 predicts under 1 dB (measured against
  opensatcom's P.618 implementation during AEDL t3-001 calibration,
  2026-08-11). For earth-space links, take rain from a P.618
  implementation and pass it in via `rain_loss_db`.
- **Cross-polarized sea clutter**: copolarized NRL value −10 dB (the NRL
  model has no cross-pol term; spread in the literature is 5–15 dB).
- **OS/GO/SO CFAR losses**: published homogeneous-clutter deltas on the
  CA universal curve, not per-type analytic curves.
- **Constant-γ ground clutter** is frequency-independent by
  construction; terrain γ values are medians with several dB of
  real-world spread.
