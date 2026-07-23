# Changelog

For the full changelog, see:

**[CHANGELOG.md on GitHub](https://github.com/jman4162/phased-array-systems/blob/main/CHANGELOG.md)**

## Recent Changes

### [0.9.0] - 2026-07-22

**Added:**
- NSGA-II multi-objective optimization (`optimize_pareto`, optional `[mdao]` extra); requirements as constraints
- Constraint-aware DOE (`validate="architecture"`) — no more per-case construction errors
- Sobol global sensitivity indices (`--sens-method sobol`)
- Search timeline metrics (PRF + search volume -> revisit rate, occupancy); see [MDAO Tools](user-guide/mdao.md)
- Thermal-reliability coupling: dissipated power -> junction temperature -> Arrhenius MTBF
- Interactive plotly trade plots and self-contained report embeds

**Changed:**
- Weighted-sum penalty normalized by requirement scale; round-robin interleaved timeline

### [0.8.0] - 2026-07-22

**Added:**
- Real ITU-R P.676-13 (line-by-line) and P.838-3 propagation with vendored coefficient tables
- NRL sea clutter and Barton constant-gamma ground clutter (published models)
- Swerling 0-4 threading through required SNR, integration gain, and Pd
- Analytic error budget (quantization, RMS errors) wired into both antenna paths
- Validation suite vs published references; [validation table](theory/validation.md)
- Seed threading, provenance stamps, sorted batch results, `pasys doe --resume`
- mypy at zero errors, enforced in CI

**Changed (numbers shift):**
- Atmospheric/rain losses, clutter sigma0, CFAR loss vs Pfa, exact required SNR
  (golden margin -0.24 dB), radar honors cascaded NF (golden +1.16 dB SNR)

**Removed:**
- Hand-fit placeholder coefficients, `compute_cost_per_db`, empirical Swerling/CFAR step tables

### [0.7.0] - 2026-07-22

**Added:**
- Digitization-level trades (element / subarray / analog) driving ADC count, data rate, compute, and power
- ADC aperture-jitter SNR model and system dynamic range with array processing gain
- Digital-section and receive-chain power in the DC budget; radar duty cycle
- Exact Swerling 0-4 detection statistics (noncentral chi-square / gamma mixtures)
- DBF architecture trade example and golden-case regression test

**Fixed:**
- DOE runner dropped `digital.*`/`reliability.*` variables
- `augment_doe` repeated original samples when reusing a seed
- Radar equation double-counted pulse integration gain

### [0.4.0] - 2026-02-01

**Added:**
- Digital array model for digital beamforming calculations
- RF cascade model for noise figure and gain cascade analysis
- MkDocs documentation site with API reference, user guides, and tutorials

**Fixed:**
- Ruff linting errors in models module
- MathJax rendering in documentation

### [0.3.0] - 2024-01-15

**Added:**
- Radar detection model with pulse integration
- CLI commands: `pasys run`, `pasys doe`, `pasys report`, `pasys pareto`
- HTML and Markdown report generation

### [0.2.0] - 2024-01-01

**Added:**
- Design of Experiments (DOE) with LHS, random, and grid
- Pareto frontier extraction and TOPSIS ranking
- Requirements verification system

### [0.1.0] - 2023-12-15

**Added:**
- Initial release
- Architecture configuration
- Communications link budget model
- Basic visualization
