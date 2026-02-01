# API Reference

Complete API documentation for phased-array-systems, auto-generated from source docstrings.

## Package Structure

```
phased_array_systems/
├── architecture/     # System configuration
├── scenarios/        # Operating conditions
├── requirements/     # Requirements management
├── models/
│   ├── antenna/      # Antenna metrics
│   ├── comms/        # Link budget
│   ├── radar/        # Radar detection
│   ├── digital/      # Digital array (ADC/DAC, bandwidth, scheduling)
│   ├── rf/           # RF cascade (noise figure, gain, dynamic range)
│   └── swapc/        # SWaP-C models
├── trades/           # DOE and Pareto
├── viz/              # Visualization
├── io/               # File I/O
└── reports/          # Report generation
```

## Quick Links

### Core Configuration

- [Architecture](architecture.md) - `ArrayConfig`, `RFChainConfig`, `CostConfig`, `Architecture`
- [Scenarios](scenarios.md) - `CommsLinkScenario`, `RadarDetectionScenario`
- [Requirements](requirements.md) - `Requirement`, `RequirementSet`, `VerificationReport`

### Models

- [Antenna](models/antenna.md) - Antenna adapter and metrics
- [Communications](models/comms.md) - Link budget model
- [Radar](models/radar.md) - Radar equation and detection
- [Digital](models/digital.md) - ADC/DAC, bandwidth, timeline scheduling
- [RF](models/rf.md) - Noise figure, gain cascade, dynamic range
- [SWaP-C](models/swapc.md) - Power and cost models

### Trade Studies

- [Trades](trades.md) - `DesignSpace`, `generate_doe`, `BatchRunner`, `extract_pareto`

### Output

- [Visualization](viz.md) - `pareto_plot`, `scatter_matrix`, `trade_space_plot`
- [I/O](io.md) - `load_config`, `export_results`
- [Reports](reports.md) - `HTMLReport`, `MarkdownReport`

## Common Patterns

### Single Case Evaluation

```python
from phased_array_systems.architecture import Architecture, ArrayConfig, RFChainConfig
from phased_array_systems.scenarios import CommsLinkScenario
from phased_array_systems.evaluate import evaluate_case

arch = Architecture(
    array=ArrayConfig(nx=8, ny=8),
    rf=RFChainConfig(tx_power_w_per_elem=1.0),
)

scenario = CommsLinkScenario(
    freq_hz=10e9, bandwidth_hz=10e6, range_m=100e3, required_snr_db=10.0
)

metrics = evaluate_case(arch, scenario)
```

### Trade Study

```python
from phased_array_systems.trades import (
    DesignSpace, generate_doe, BatchRunner, filter_feasible, extract_pareto
)

space = DesignSpace().add_variable("array.nx", "int", low=4, high=16)
doe = generate_doe(space, method="lhs", n_samples=100, seed=42)
runner = BatchRunner(scenario)
results = runner.run(doe)
pareto = extract_pareto(filter_feasible(results), [("cost_usd", "minimize"), ("eirp_dbw", "maximize")])
```

### Requirements Verification

```python
from phased_array_systems.requirements import Requirement, RequirementSet

requirements = RequirementSet(requirements=[
    Requirement("REQ-001", "Min EIRP", "eirp_dbw", ">=", 40.0),
])
report = requirements.verify(metrics)
```

## Type Annotations

The package uses type hints throughout. Key types:

```python
from phased_array_systems.types import (
    MetricsDict,        # dict[str, float | int | str | None]
    OptimizeDirection,  # Literal["minimize", "maximize"]
    ComparisonOp,       # Literal[">=", "<=", ">", "<", "=="]
    Severity,           # Literal["must", "should", "nice"]
)
```

## Version

```python
from phased_array_systems import __version__
print(__version__)
```
