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
  rate).
- **Cross-polarized sea clutter**: copolarized NRL value −10 dB (the NRL
  model has no cross-pol term; spread in the literature is 5–15 dB).
- **OS/GO/SO CFAR losses**: published homogeneous-clutter deltas on the
  CA universal curve, not per-type analytic curves.
- **Constant-γ ground clutter** is frequency-independent by
  construction; terrain γ values are medians with several dB of
  real-world spread.
