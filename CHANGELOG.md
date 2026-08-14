# Changelog

All notable changes to phased-array-systems will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.12.0] - 2026-08-13

### Added

- **Aperture power density.** Nothing in the package computed power per unit
  area: `ArrayConfig` is wavelength-normalized and carries no frequency, so a
  physical aperture in m2 was never formed. `PowerModel` now emits
  `aperture_area_m2`, `cell_area_cm2`, `heat_dissipation_w`,
  `heat_flux_w_per_cm2`, and radiated power density at peak and average.
  At half-wave spacing the cell is (lambda/2)^2, so heat flux rises as f^2 at
  fixed per-element dissipation: the same T/R module is an air-cooled design at
  X-band and a liquid-cooled one at Ka-band, which no other metric reveals.
  Heat flux is quoted on average power (cold-plate time constants are seconds,
  a PRI is microseconds); the junction does not average that way and no peak
  junction claim is made.
- **Cooling feasibility** (`Architecture.cooling`, `data/cooling.yaml`,
  `models/swapc/cooling.py`). `thermal_resistance_c_per_w` is an assertion
  about a cooling solution; this checks it against the flux the design actually
  produces, emitting `cooling_class`, `max_heat_flux_w_per_cm2`,
  `cooling_margin_w_per_cm2`, `cooling_feasible`. Thresholds are
  order-of-magnitude regime gates, each recording whether its number was
  **quoted** from a primary source or is a judgment gate consistent with one;
  the forced-air and cold-plate anchors are quoted verbatim from DARPA
  CS MANTECH 2013.
- **Junction temperature limit.** `tj_max_c` sat in the technology catalog
  unread, so a design could run its junction past the rated maximum and be
  penalized only indirectly through Arrhenius derating. New
  `ReliabilityConfig.tj_max_c` (falling back to the catalog when
  `Architecture.trm` names a technology) emits `junction_temp_max_c`,
  `junction_temp_margin_c`, `junction_temp_ok`.
- **Power-aperture product** (`models/radar/search.py`):
  `effective_aperture_m2` (A_e = G lambda^2/4pi, the direction never computed
  before), `power_aperture_product_w_m2`, and for search scenarios the required
  product from the Barton/Skolnik relation plus `power_aperture_margin_db`.
  It pairs with heat flux deliberately: P*A (W*m^2) says how much power and
  aperture the mission demands, heat flux (W/cm^2) constrains how tightly that
  power may be packaged, and the two are dimensional inverses.

### Fixed

- `compute_thermal_load` was dead code with zero callers while `evaluate`
  inlined a divergent copy of the same energy balance beside it. There is now
  one balance: `PowerModel` calls it and the junction-temperature feed-forward
  consumes the result. Junction temperature is numerically unchanged, pinned by
  a regression test.

### Changed

- Golden snapshot regenerated for eight added metric keys. **Additive only:**
  no existing value moved, verified by diffing the snapshot before and after.

## [0.11.0] - 2026-08-11

RF and digital front-end depth: T/R modules, the nonlinearity chain, the
DAC path, load-pull against EdgeFEM active-impedance scans, and a cited
technology catalog. All new behavior is opt-in; with default configs the
only metric drift is the adc_bits fix noted below.

### Added
- **T/R module abstraction**: `TRComponent` and `TRModuleConfig`
  (`Architecture.trm`). One component list (reliability vocabulary: lna,
  pa, phase_shifter, attenuator, switch, control_asic) derives the RF
  aggregates the models already consume — rx/tx stages, composite noise
  figure, RX DC power, TX output P1dB. Explicit `RFChainConfig` fields
  always override; an equivalence test pins that a TRM reproducing the
  explicit aggregates yields identical metrics.
- **Nonlinearity chain**: `cascade_p1db` (reciprocal-sum cascaded P1dB),
  `rapp_compression_db` (Rapp soft limiter, exactly 1 dB at P1dB by
  construction), `compression_check` (per-stage headroom and binding
  stage), `sndr_with_imd3` (thermal SNR + two-tone IM3 -> SNDR, EVM).
  `cascade_analysis` reports ip1db/op1db/headroom/compressed. TX chains:
  `RFChainConfig.tx_stages` runs the same cascade with headroom checked at
  the commanded drive level. Link budget: `tx_backoff_db` and
  `pa_op1db_dbm_per_elem` (Rapp-compressed EIRP), and
  `nonlinear_impairments=True` scores `link_margin_db` against SNDR when
  the RX cascade provides IIP3 (emits `sndr_rx_db`, `imd3_dbc`,
  `evm_rms_pct`).
- **DAC path**: `DigitalConfig.dac_enob/dac_fom_fj/dac_full_scale_dbm/
  dac_backoff_db`; DAC power joins the DC budget (Walden-form estimate,
  same caveats as the ADC); TX beamformer stream rate mirrors RX
  (`tx_bf_data_rate_gbps`); `dac_output_power` finally has a caller.
- **Load-pull + active impedance** (`models/rf/loadpull.py`):
  `LoadPullModel` (analytic elliptical contours; documented small-mismatch
  simplifications) and `LoadPullTable` (measured contours from CSV — the
  measurement seam); `load_scan_csv` reads EdgeFEM's `export_scan_csv`
  artifact (producer-owned contract, revision 2; golden fixture vendored
  under `tests/fixtures/edgefem/` with a refresh script); `eirp_vs_scan`
  aggregates per-element degradation into EIRP delta, PAE drop, and worst
  VSWR per scan angle.
- **Technology catalog** (`data/technologies.yaml`,
  `models/rf/technology.py`): SiGe / GaAs / GaN / CMOS / LDMOS survey and
  review ranges, every number carrying a fetched citation (source, url,
  access date, quote); `docs/technology-catalog.md` is generated from it.
  `TRModuleConfig.technology` fills lna NF/IIP3 and pa P1dB midpoints for
  components left at defaults.

### Fixed
- `bits_per_sample` for beamformer data rate used `int(adc_enob) * 2`,
  conflating ENOB with the physical word width a stream actually moves.
  Now `adc_bits` (explicit) or `ceil(adc_enob) + 2` sizes the stream.
  **Golden case drift**: `bf_data_rate_gbps` 110 -> 130 (22 -> 26
  bits/sample at the reference 11-ENOB ADC).

### Documentation
- `compute_rain_loss` is a terrestrial (P.530 effective-path) model and is
  now documented as unsuitable for slant paths, in the docstring and in
  `docs/theory/validation.md`: at 28 GHz / 8 mm/h it overpredicts an
  earth-space rain loss by an order of magnitude versus ITU-R P.618
  (finding from the AEDL t3-001 calibration). Use `rain_loss_db` to inject
  a P.618 value for satcom scenarios.

## [0.10.1] - 2026-08-11

### Fixed
- `n_failed_elements` reported the survivors: the failure mask is True for
  failed elements and the metric counted the zeros, so a 2% failure rate on
  256 elements reported 251 "failures". The applied physics (zeroed weights)
  was correct; only the reported count was inverted.

## [0.10.0] - 2026-08-10

### Fixed
- `compute_sidelobe_level` reported a sample on the main-lobe skirt instead
  of a sidelobe. It excluded the main beam out to one half-power beamwidth
  each side of the peak, but the first null of a tapered aperture sits at
  roughly 1.3 to 1.8 times the HPBW, and further as the taper deepens. The
  main lobe is now excluded out to its first null on each side. Pass
  `main_lobe_width_deg` to force a fixed angular exclusion window instead.

  **This changes reported `sll_db` values, in some cases by more than 20 dB.**
  A 32x32 Taylor -35 dB design at broadside previously reported -14.0 dB and
  now reports -35.2 dB. The golden-case snapshot moved from -16.56 dB to
  -30.39 dB. Any recorded trade study, Pareto front, or requirement
  verification that used `sll_db` should be re-run.

  Two reported symptoms came from the same cause and are also fixed.
  `sll_db` was non-monotonic in taper depth (-25 dB design read -17.5,
  -35 dB read -14.0, -45 dB read -14.7), because a deeper taper widens the
  beam and steepens the skirt, moving the first unmasked sample to a
  different point on it. And `sll_db` was nearly insensitive to `phase_bits`
  off broadside, because quantization lobes near -25 dB sat far below the
  skirt reading. A 32x32 Taylor -35 dB design scanned to 45 degrees now
  reports -4.96, -16.14, -28.64 and -32.26 dB for 2-bit, 3-bit, 6-bit and
  ideal phase control. At broadside every steering phase is zero, so
  quantization remains a no-op there, which is correct.

  This also closes a disagreement between the two code paths: the analytic
  fallback used when `phased-array-modeling` is absent returns the taper
  design SLL floored by the quantization error floor, so it read about
  -35 dB where the full-pattern path read about -14 dB. The two now agree to
  0.24 dB on that case.

## [0.9.0] - 2026-07-22

### Added
- True multi-objective optimization: `optimize_pareto()` (trades/moo.py)
  runs mixed-variable NSGA-II via pymoo and returns the nondominated set
  with full metrics; must-severity requirements become normalized
  inequality constraints. CLI: `pasys optimize --method nsga2`
- Optional `[mdao]` extra (pymoo, SALib); core install unchanged
- Constraint-aware DOE: `generate_doe(validate="architecture")` rejection-
  samples against Architecture construction with adaptive oversampling,
  eliminating per-case construction errors from batch studies
- Sobol global sensitivity: `sobol_sensitivity()` with S1/ST indices and
  confidence intervals; `pasys sensitivity --sens-method sobol`
- Search timeline metrics: radar scenarios accept prf_hz, search extents,
  beam overhead, and frame budget; antenna beamwidths and n_pulses/PRF
  dwell time drive dwell_time_ms, n_beam_positions, search_frame_time_s,
  search_update_rate_hz, timeline_occupancy
- Thermal-reliability coupling: `reliability.thermal_resistance_c_per_w`
  + `ambient_temp_c` estimate junction temperature from dissipated power
  and feed the Arrhenius MTBF derating (new junction_temp_c metric)
- Interactive plotly plots (`viz/interactive.py`, [plotting] extra) and
  self-contained interactive Pareto embeds in HTML reports

### Changed
- Weighted-sum optimizer penalty normalizes margins by requirement scale
  (mixed-unit requirements previously biased the penalty)
- `interleaved_timeline` uses deterministic priority-weighted round-robin
  instead of the placeholder priority sort
- mypy analysis target is 3.12 (numpy 2.2+ stubs); runtime 3.10 support
  unchanged, still tested in CI

## [0.8.0] - 2026-07-22

### Added
- `models/propagation/` package: full ITU-R P.676-13 Annex 1 line-by-line
  gaseous attenuation (44 O2 + 35 H2O vendored spectroscopic lines) and
  ITU-R P.838-3 rain k/alpha for H and V polarization; ITU-R P.530
  effective rain path length; all coefficient data vendored, no new
  dependencies
- NRL sea clutter model (Gregers-Hansen & Mittal 2012, fitted to the
  Nathanson tables) and Barton constant-gamma ground clutter
- `swerling` field on `RadarDetectionScenario`; required SNR, integration
  gain, and achieved Pd all use the exact detection statistics
- `models/antenna/errors.py`: Ruze gain loss, phase-quantization RMS and
  loss, average sidelobe floor, beam-pointing estimate; wired into both
  antenna adapter paths so `phase_bits` and taper affect metrics in
  analytic mode
- `generate_taper_weights()` from scipy window functions; taper losses
  computed from real windows
- Reproducibility: `evaluate_case(seed=...)` threads the element-failure
  RNG seed; `meta.seed`, `meta.package_version`, `meta.pam_version`
  stamped per case; batch results sorted by case_id; `pasys doe --cache
  PATH --resume`
- Validation suite (`tests/test_validation.py`, 35 tests) asserting
  models against their published sources; `docs/theory/validation.md`
  documents every reference and tolerance
- mypy at zero errors, enforced as a blocking CI step

### Changed (numeric results shift)
- Atmospheric and rain losses now come from the real ITU models (the
  previous 2-line/polynomial fits were hand-set approximations);
  elevation handling uses equivalent-height slant columns (the previous
  scale factor always evaluated to 1)
- Required radar SNR uses the exact Marcum-Q inversion instead of
  Albersheim (golden case: 13.115 -> 13.183 dB, margin -0.24 dB)
- One noise convention: `rx_noise_temp_k` is antenna temperature and
  T_sys = T_ant + 290*(F-1); identical at 290 K, corrects low-sky-temp
  satcom cases; the radar equation now honors cascaded NF like the comms
  path (golden case: +1.16 dB SNR with its 1.84 dB cascade)
- CA-CFAR loss follows the analytic universal curve, so Pfa now matters
  (N=16 at 1e-6: 2.0 dB, unchanged; other Pfa values shift)
- Clutter sigma0 values shift to the published models
- `friis_noise_figure` reports `stage_contribution_pct` (sums to 100)
  and `stage_nf_delta_db` instead of per-stage dB values that did not
  sum; `cascade_analysis` key renamed to `stage_nf_contribution_pct`

### Removed
- `compute_cost_per_db` (USD per dB is not a meaningful ratio)
- `swerling_snr_adjustment` and `cfar_required_snr_adjustment` empirical
  step tables (superseded by exact statistics and the universal curve)
- Hand-fit taper-loss polynomials, GIT-style clutter constants, and the
  fabricated rain-cell extent model

## [0.7.0] - 2026-07-22

### Added
- `digitization_level` (element / subarray / analog) on `DigitalConfig`; ADC count, beamformer data rate, compute, and power now follow the digitized channel count (`Architecture.n_digital_channels`) instead of assuming one ADC per element
- ADC aperture-jitter model: `adc_effective_snr()` combines quantization and jitter noise; new `adc_jitter_ps_rms` and `adc_input_freq_hz` config fields and `adc_enob_effective` metric
- System dynamic range metric `dynamic_range_system_db` including the 10*log10(N_channels) array processing gain
- Digital section power in the DC budget: ADC power from the Walden figure of merit (`adc_fom_fj`) and beamformer power from `dsp_efficiency_gops_per_w`
- Receive chain power per element (`rf.rx_power_w_per_elem`) and radar transmit `duty_cycle` in the power model; new metrics `rf_avg_power_w`, `pa_dc_power_w`, `rx_dc_power_w`, `adc_power_w`, `dsp_power_w`
- Exact Swerling 1-4 detection probabilities via gamma-mixture of the noncentral chi-square detector statistics
- Example `06_dbf_architecture_trade.py` and config `dbf_architecture_doe.yaml`: digitization-level trade study with Pareto extraction
- Golden-case regression test (`tests/test_golden_case.py` + `tests/data/golden_dbf_case.json`)

### Fixed
- `default_architecture_builder` silently dropped `digital.*` and `reliability.*` DOE variables, so batch studies could not vary digital or reliability parameters
- `augment_doe` reused the caller's seed and duplicated the original samples instead of drawing new points
- Swerling 0 Pd used a Gaussian-tail approximation with identical dead-code branches; replaced with the exact Marcum Q (noncentral chi-square survival function)
- Radar equation double-counted pulse integration: an empirical n^0.8 gain was added on top of Albersheim's own n-pulse law; required SNR and integration gain now come from a single consistent law

## [0.6.0] - 2026-03-21

### Added
- Design optimization module (`trades/optimization.py`) with `optimize_design()` using scipy solvers
- `OptimizationResult` dataclass with best architecture, metrics, convergence info, and optional history
- Three solver backends: `differential_evolution`, `dual_annealing`, `minimize` (L-BFGS-B)
- Weighted multi-objective scalarization and requirement-based constraint penalties
- CLI `pasys optimize` command with `--objective`, `--sense`, `--method`, `--max-iter` options
- Unit tests for RF cascade models (`test_rf_cascade.py`): Friis NF, IIP3/OIP3, SFDR, MDS, cascade analysis
- Unit tests for digital models (`test_digital.py`): converters, bandwidth, beamformer ops, scheduling
- Optimization tests (`test_optimization.py`): single/multi-objective, constraints, integer vars, CLI E2E
- Example script `05_optimization.py`: DOE baseline vs optimizer comparison

## [0.5.0] - 2026-03-21

### Added
- Digital beamformer integration: `DigitalConfig` for ADC ENOB, data rate, and FPGA processing margin
- Radar YAML configs: `radar_basic.yaml` and `radar_doe.yaml` examples
- CLI end-to-end tests for run, doe, report, pareto, and sensitivity commands
- I/O round-trip tests for Parquet, CSV, and JSON export/import
- Digital metrics in reports (HTML and Markdown): `adc_enob`, `bf_data_rate_gbps`, `processing_margin_db`

### Fixed
- CLI `pasys doe` command: was reading nonexistent `config.design_space` instead of `config.doe`
- CLI `pasys sensitivity` command: same `design_space` bug, now reads DOE variables correctly

## [0.4.0] - 2026-02-01

### Added
- Digital array model for digital beamforming calculations
- RF cascade model for noise figure and gain cascade analysis
- Documentation site with MkDocs Material
- API reference with mkdocstrings
- User guides for all major features
- Tutorials for communications and radar trade studies
- Theory documentation for phased arrays and link budgets

### Fixed
- Ruff linting errors in models module
- MathJax rendering in documentation
- Markdown list formatting in documentation

## [0.3.0] - 2024-01-15

### Added
- Radar detection model with pulse integration
- `RadarDetectionScenario` for radar trade studies
- Radar equation calculator with Swerling models
- Detection probability and false alarm rate computations
- CLI commands: `pasys run`, `pasys doe`, `pasys report`, `pasys pareto`
- HTML and Markdown report generation
- Example: `03_radar_detection_trade.py`

### Changed
- Improved Pareto extraction algorithm efficiency
- Enhanced visualization with 3D trade space plots

### Fixed
- Hypervolume calculation for 3+ objectives

## [0.2.0] - 2024-01-01

### Added
- Design of Experiments (DOE) generation with LHS, random, and grid methods
- `BatchRunner` for parallel evaluation with progress tracking
- Pareto frontier extraction and ranking (weighted sum, TOPSIS)
- Scatter matrix visualization
- Parquet and CSV export functionality
- Requirements verification with pass/fail and margins
- `DesignSpace` for defining variable bounds and types

### Changed
- Refactored architecture configuration to use Pydantic v2
- Improved error handling for batch evaluation

### Fixed
- Array gain calculation for non-square arrays
- Case ID generation collision in augmented DOE

## [0.1.0] - 2023-12-15

### Added
- Initial release
- `Architecture` configuration: `ArrayConfig`, `RFChainConfig`, `CostConfig`
- `CommsLinkScenario` for communications link analysis
- Communications link budget model (`CommsLinkModel`)
- Free space path loss propagation model
- Power and cost models for SWaP-C analysis
- `Requirement` and `RequirementSet` for requirements management
- Pareto plot visualization
- YAML/JSON configuration loading
- Example: `01_comms_single_case.py`
- Example: `02_comms_doe_trade.py`
- Tutorial Jupyter notebook

### Dependencies
- Requires `phased-array-modeling>=1.2.0`
- Python 3.10+

[Unreleased]: https://github.com/jman4162/phased-array-systems/compare/v0.6.0...HEAD
[0.6.0]: https://github.com/jman4162/phased-array-systems/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/jman4162/phased-array-systems/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/jman4162/phased-array-systems/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/jman4162/phased-array-systems/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/jman4162/phased-array-systems/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/jman4162/phased-array-systems/releases/tag/v0.1.0
