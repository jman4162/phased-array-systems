# Changelog

All notable changes to phased-array-systems will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
