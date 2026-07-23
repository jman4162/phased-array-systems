# phased-array-systems

[![CI](https://github.com/jman4162/phased-array-systems/actions/workflows/ci.yml/badge.svg)](https://github.com/jman4162/phased-array-systems/actions/workflows/ci.yml)
[![Documentation](https://img.shields.io/badge/docs-mkdocs-blue.svg)](https://jman4162.github.io/phased-array-systems)
[![Streamlit App](https://img.shields.io/badge/Streamlit-Live_Demo-FF4B4B?logo=streamlit)](https://phased-array-systems.streamlit.app)
[![PyPI version](https://badge.fury.io/py/phased-array-systems.svg)](https://badge.fury.io/py/phased-array-systems)
[![Downloads](https://img.shields.io/pypi/dm/phased-array-systems)](https://pypi.org/project/phased-array-systems/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Phased array antenna system design, optimization, and performance visualization for wireless communications and radar applications.

**[Documentation](https://jman4162.github.io/phased-array-systems)** |
**[Live Demo](https://phased-array-systems.streamlit.app)** |
**[Getting Started](https://jman4162.github.io/phased-array-systems/getting-started/quickstart/)** |
**[API Reference](https://jman4162.github.io/phased-array-systems/api/)**

## Why phased-array-systems?

- **Model-Based Workflow**: MBSE/MDAO approach from requirements through optimized designs
- **Requirements-Driven**: Every evaluation produces pass/fail with margins and traceability
- **Trade-Space Exploration**: constraint-aware DOE generation and Pareto analysis
- **Multi-Objective Optimization**: NSGA-II Pareto fronts (pymoo) plus scipy scalarized solvers
- **Validated Physics**: ITU-R P.676/P.838 propagation, NRL sea clutter, exact Swerling detection statistics, each tested against its published source
- **Digital Beamforming Trades**: element vs subarray vs analog digitization drives ADC count, data rate, compute, and power
- **System Models**: comms link budget, radar detection + search timeline, RF cascade, digital beamformer, thermal-coupled reliability
- **Reproducible**: config-driven workflow with seed control, provenance stamps, and checkpoint/resume

## Workflow

```
Config (YAML/JSON) → Architecture + Scenario → DOE Generation → Batch Evaluation
       ↓                                                              ↓
  Requirements ───────────────────────────────────────────→ Verification
                                                                   ↓
                                                           Pareto Extraction
                                                                   ↓
              Reports ← Visualization ← Optimization ←────────────┘
```

## Features

- **Requirements as first-class objects**: every run produces pass/fail + margins with traceability
- **Trade-space exploration**: DOE (grid/random/LHS) with rejection sampling against architecture constraints, plus Pareto extraction, TOPSIS ranking, and hypervolume
- **Multi-objective optimization**: NSGA-II returns the nondominated set directly; scipy solvers (DE, dual annealing, L-BFGS-B) with normalized constraint penalties remain for scalarized runs
- **Global sensitivity**: Sobol S1/ST indices (SALib) alongside one-at-a-time sweeps
- **Communications & Radar**: link budgets with ITU-R P.676-13 line-by-line gaseous and P.838-3 rain attenuation; radar detection with exact Swerling 0-4 statistics, NRL sea clutter, analytic CFAR loss, and search-timeline revisit metrics
- **Digital beamforming**: digitization level (element/subarray/analog), jitter-aware ADC SNR, system dynamic range with array processing gain, beamformer data-rate and compute budgets
- **RF cascade analysis**: Friis noise figure, IIP3, SFDR, MDS for cascaded receiver chains
- **TRM reliability**: MTBF with Arrhenius derating driven by estimated junction temperature, availability, graceful degradation
- **Validation suite**: models checked against published references in CI (see the docs' validation table)
- **Flat metrics dictionary**: all models return a consistent flat dict for interchange
- **Interactive reports**: self-contained HTML with embedded plotly trade plots
- **CLI and Python API**: use from the command line or integrate into scripts

## Installation

```bash
pip install phased-array-systems

# Multi-objective optimization + Sobol sensitivity (pymoo, SALib)
pip install "phased-array-systems[mdao]"

# Interactive plots and report embeds (plotly)
pip install "phased-array-systems[plotting]"

# Development dependencies
pip install "phased-array-systems[dev]"
```

## Quick Start

### Single Case Evaluation

```python
from phased_array_systems import Architecture, ArrayConfig, RFChainConfig
from phased_array_systems import CommsLinkScenario, evaluate_case

# Define architecture
arch = Architecture(
    array=ArrayConfig(nx=8, ny=8, dx_lambda=0.5, dy_lambda=0.5),
    rf=RFChainConfig(tx_power_w_per_elem=1.0, pa_efficiency=0.3),
)

# Define scenario
scenario = CommsLinkScenario(
    freq_hz=10e9,
    bandwidth_hz=10e6,
    range_m=100e3,
    required_snr_db=10.0,
)

# Evaluate
metrics = evaluate_case(arch, scenario)
print(f"EIRP: {metrics['eirp_dbw']:.1f} dBW")
print(f"Link Margin: {metrics['link_margin_db']:.1f} dB")
```

### DOE Trade Study

```python
from phased_array_systems import DesignSpace, generate_doe, BatchRunner, extract_pareto

# Define design space
space = (
    DesignSpace()
    .add_variable("array.nx", "int", low=4, high=16)
    .add_variable("array.ny", "int", low=4, high=16)
    .add_variable("rf.tx_power_w_per_elem", "float", low=0.5, high=3.0)
)

# Generate DOE
doe = generate_doe(space, method="lhs", n_samples=100, seed=42)

# Run batch evaluation
runner = BatchRunner(scenario)
results = runner.run(doe)

# Extract Pareto frontier
pareto = extract_pareto(results, [
    ("cost_usd", "minimize"),
    ("eirp_dbw", "maximize"),
])
```

### Design Optimization

```python
from phased_array_systems import optimize_design, DesignSpace, CommsLinkScenario

scenario = CommsLinkScenario(
    freq_hz=10e9, bandwidth_hz=10e6, range_m=100e3, required_snr_db=10.0,
)
space = (
    DesignSpace()
    .add_variable("array.nx", "categorical", values=[4, 8, 16])
    .add_variable("array.ny", "categorical", values=[4, 8, 16])
    .add_variable("rf.tx_power_w_per_elem", "float", low=0.5, high=3.0)
)

result = optimize_design(
    space=space, scenario=scenario,
    objective="eirp_dbw", sense="maximize", method="de", seed=42,
)
print(f"Best EIRP: {result.best_metrics['eirp_dbw']:.1f} dBW")
```

## Examples

See the `examples/` directory:
- `01_comms_single_case.py` - Single case evaluation
- `02_comms_doe_trade.py` - Full DOE trade study workflow
- `03_radar_detection_trade.py` - Radar detection analysis and trade study
- `04_taper_trade_study.py` - Amplitude taper comparison (SLL vs gain)
- `05_optimization.py` - Design optimization with constraint handling
- `06_dbf_architecture_trade.py` - Digital beamforming architecture trade (element vs subarray vs analog digitization)

### Tutorial Notebooks

Try the interactive tutorials in Google Colab:

- Trade study basics: [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/jman4162/phased-array-systems/blob/main/notebooks/tutorial_phased_array_trade_study.ipynb)
- DBF architecture trade: [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/jman4162/phased-array-systems/blob/main/notebooks/tutorial_dbf_architecture_trade.ipynb)
- MDAO workflow (NSGA-II + Sobol): [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/jman4162/phased-array-systems/blob/main/notebooks/tutorial_mdao_workflow.ipynb)

## Package Structure

```
phased_array_systems/
├── architecture/     # Array, RF chain, cost configurations
├── scenarios/        # CommsLinkScenario, RadarDetectionScenario
├── requirements/     # Requirement definitions and verification
├── models/
│   ├── antenna/      # Phased array adapter and metrics
│   ├── comms/        # Link budget, propagation models
│   ├── radar/        # Radar equation, detection, integration
│   ├── rf/           # Cascaded RF chain analysis (NF, IIP3, SFDR)
│   ├── digital/      # ADC/DAC, bandwidth, scheduling models
│   └── swapc/        # Power and cost models
├── trades/           # DOE, batch runner, Pareto analysis
├── viz/              # Plotting utilities
└── io/               # Config loading, results export
```

## Development

```bash
# Clone the repository
git clone https://github.com/jman4162/phased-array-systems.git
cd phased-array-systems

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run linting
ruff check .
```

## CLI

```bash
# Single case evaluation
pasys run config.yaml

# DOE batch study (checkpoint every 10 cases; resume after interruption)
pasys doe config.yaml -n 100 --method lhs --cache results/cache.parquet --resume

# Scalarized optimization (differential evolution)
pasys optimize config.yaml --objective eirp_dbw --sense maximize

# Multi-objective Pareto front (NSGA-II; needs the [mdao] extra)
pasys optimize config.yaml --objective eirp_dbw --method nsga2 \
    --objective2 cost_usd:minimize -o pareto.parquet

# Sensitivity: one-at-a-time or Sobol global indices
pasys sensitivity config.yaml --sens-method sobol --samples 256

# Extract Pareto frontier from DOE results
pasys pareto results.parquet -x cost_usd -y eirp_dbw --plot

# Generate report
pasys report results.parquet --format html
```

## Documentation

Full documentation is available at **[jman4162.github.io/phased-array-systems](https://jman4162.github.io/phased-array-systems)**:

- [Getting Started](https://jman4162.github.io/phased-array-systems/getting-started/quickstart/) - Installation and quickstart
- [User Guide](https://jman4162.github.io/phased-array-systems/user-guide/) - Detailed usage guides
- [Tutorials](https://jman4162.github.io/phased-array-systems/tutorials/) - Step-by-step walkthroughs
- [API Reference](https://jman4162.github.io/phased-array-systems/api/) - Complete API documentation
- [Theory](https://jman4162.github.io/phased-array-systems/theory/) - Background equations and theory

## Interactive Demo

[![Streamlit App](https://img.shields.io/badge/Streamlit-Demo-FF4B4B?logo=streamlit)](https://phased-array-systems.streamlit.app)

Try the interactive Streamlit demo app featuring:
- **Single Case Calculator**: Evaluate array configurations with real-time metrics
- **Trade Study**: DOE generation with Pareto optimization
- **RF Cascade Analyzer**: Cascaded noise figure, gain, and linearity analysis
- **Radar Detection**: SNR calculation and detection probability curves

Run locally:
```bash
cd app
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Citation

If you use phased-array-systems in academic work, please cite:

```bibtex
@software{phased_array_systems,
  title = {phased-array-systems: Phased Array Antenna System Design and Optimization},
  author = {John Hodge},
  year = {2026},
  url = {https://github.com/jman4162/phased-array-systems}
}
```

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License - see [LICENSE](LICENSE) for details.
