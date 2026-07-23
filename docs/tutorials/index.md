# Tutorials

Step-by-step guides for common workflows with phased-array-systems.

## Available Tutorials

| Tutorial | Description | Level |
|----------|-------------|-------|
| [Communications Trade Study](comms-trade-study.md) | Complete DOE workflow for comms links | Beginner |
| [Radar Detection Trade](radar-detection-trade.md) | Radar system trade study | Intermediate |
| [Config-Driven Workflow](config-driven-workflow.md) | YAML-based analysis | Beginner |
| [Sensitivity Analysis](sensitivity-analysis.md) | Parameter sensitivity studies | Intermediate |

## Prerequisites

Before starting, ensure you have:

1. Installed phased-array-systems: `pip install phased-array-systems[plotting]`
2. Basic Python familiarity
3. Understanding of phased arrays (see [Core Concepts](../getting-started/concepts.md))

## Tutorial Structure

Each tutorial includes:

- **Objective**: What you'll learn
- **Setup**: Required imports and data
- **Steps**: Detailed walkthrough
- **Complete Code**: Full working example
- **Next Steps**: Related topics

## Quick Start Path

For new users, we recommend:

1. Start with [Communications Trade Study](comms-trade-study.md)
2. Try the [Config-Driven Workflow](config-driven-workflow.md)
3. Explore [Sensitivity Analysis](sensitivity-analysis.md)

For radar applications:

1. Start with [Radar Detection Trade](radar-detection-trade.md)

## Jupyter Notebooks

Interactive versions are available:

| Notebook | Covers | |
|---|---|---|
| Phased array trade study | Single case, DOE, Pareto basics | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/jman4162/phased-array-systems/blob/main/notebooks/tutorial_phased_array_trade_study.ipynb) |
| DBF architecture trade | Digitization level x ADC x beams -> Pareto with interactive plots | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/jman4162/phased-array-systems/blob/main/notebooks/tutorial_dbf_architecture_trade.ipynb) |
| MDAO workflow | Constraint-aware DOE -> NSGA-II -> Sobol -> report | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/jman4162/phased-array-systems/blob/main/notebooks/tutorial_mdao_workflow.ipynb) |

## Example Files

The tutorials reference example files in the repository:

```
examples/
├── 01_comms_single_case.py      # Single evaluation
├── 02_comms_doe_trade.py        # DOE workflow
└── 03_radar_detection_trade.py  # Radar analysis
```

Run them locally:

```bash
cd examples
python 01_comms_single_case.py
python 02_comms_doe_trade.py
```
