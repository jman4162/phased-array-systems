# phased-array-systems

[![CI](https://github.com/jman4162/phased-array-systems/actions/workflows/ci.yml/badge.svg)](https://github.com/jman4162/phased-array-systems/actions/workflows/ci.yml)
[![Documentation](https://img.shields.io/badge/docs-mkdocs-blue.svg)](https://jman4162.github.io/phased-array-systems)
[![PyPI version](https://badge.fury.io/py/phased-array-systems.svg)](https://badge.fury.io/py/phased-array-systems)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Phased array antenna system design, optimization, and performance visualization for wireless communications and radar applications.

**[Documentation](https://jman4162.github.io/phased-array-systems)** |
**[Getting Started](https://jman4162.github.io/phased-array-systems/getting-started/quickstart/)** |
**[API Reference](https://jman4162.github.io/phased-array-systems/api/)**

## Why phased-array-systems?

- **Model-Based Workflow**: MBSE/MDAO approach from requirements through optimized designs
- **Requirements-Driven**: Every evaluation produces pass/fail with margins and traceability
- **Trade-Space Exploration**: DOE generation and Pareto analysis for systematic design exploration
- **Dual Application**: Supports both communications link budgets and radar detection scenarios
- **Reproducible**: Config-driven workflow with seed control and version stamping

## Workflow

```
Config (YAML/JSON) → Architecture + Scenario → DOE Generation → Batch Evaluation
       ↓                                                              ↓
  Requirements ───────────────────────────────────────────→ Verification
                                                                   ↓
                    Reports ← Visualization ← Pareto Extraction ←──┘
```

## Features

- **Requirements as first-class objects**: Every run produces pass/fail + margins with traceability
- **Trade-space exploration**: DOE + Pareto optimization over single-point designs
- **Communications & Radar**: Link budget analysis and radar detection modeling
- **Flat metrics dictionary**: All models return consistent `dict[str, float]` for interchange
- **Config-driven reproducibility**: Stable case IDs, seed control, version stamping
- **CLI and Python API**: Use from command line or integrate into scripts

## Installation

```bash
pip install phased-array-systems

# Development dependencies
pip install phased-array-systems[dev]

# Visualization extras
pip install phased-array-systems[plotting]
```

## Quick Start

### Single Case Evaluation

```python
from phased_array_systems.architecture import Architecture, ArrayConfig, RFChainConfig
from phased_array_systems.scenarios import CommsLinkScenario
from phased_array_systems.evaluate import evaluate_case

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
from phased_array_systems.trades import DesignSpace, generate_doe, BatchRunner, extract_pareto

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

## Examples

See the `examples/` directory:
- `01_comms_single_case.py` - Single case evaluation
- `02_comms_doe_trade.py` - Full DOE trade study workflow
- `03_radar_detection_trade.py` - Radar detection analysis and trade study

### Tutorial Notebook

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/jman4162/phased-array-systems/blob/main/notebooks/tutorial_phased_array_trade_study.ipynb)

Try the interactive tutorial in Google Colab!

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

# DOE batch study
pasys doe config.yaml -n 100 --method lhs

# Generate report
pasys report results.parquet --format html

# Extract Pareto frontier
pasys pareto results.parquet -x cost_usd -y eirp_dbw --plot
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
