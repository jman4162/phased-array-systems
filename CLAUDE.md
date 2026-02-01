# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`phased-array-systems` is an open-source Python package for phased array antenna system design, optimization, and performance visualization for wireless communications and radar applications. It implements an MBSE/MDAO workflow: requirements → architecture → analytical models → trade studies → Pareto selection → reporting.

**Core dependency:** `phased-array-modeling>=1.2.0` (provides array geometries, steering, tapering, impairments, and pattern visualization)

**Project status:** v0.4.0 - All 4 implementation phases complete. See `package_design_and_requirements.txt` for the original SDD.

## Build & Development Commands

```bash
# Installation
pip install -e .                            # Editable install
pip install -e ".[dev]"                     # Development deps (pytest, ruff, mypy)
pip install -e ".[plotting]"                # Visualization (plotly, kaleido)

# Testing
pytest tests/                               # Run all tests
pytest tests/test_comms_link_budget.py -v   # Run specific test file
pytest tests/ --cov=phased_array_systems    # With coverage

# Linting & Formatting
ruff check .
ruff format .
mypy src/phased_array_systems

# CLI
pasys run config.yaml                       # Single case evaluation
pasys doe config.yaml                       # DOE batch study
pasys pareto results.parquet --x cost_usd --y eirp_dbw  # Pareto analysis
pasys report results.parquet -o report.html # Generate HTML report
```

## Architecture

### Layer Structure
- **Layer 0:** `phased-array-modeling` (external) - EM/pattern computations
- **Layer 1:** This package - system models, trade studies, optimization
- **Layer 2:** Interfaces - Python API, CLI, config I/O

### Package Layout (`src/phased_array_systems/`)
- `requirements/` - Constraint/objective definitions, verification reports
- `architecture/` - ArrayConfig, RFChainConfig, PowerThermalConfig, CostConfig
- `models/antenna/` - Adapter wrapping `phased-array-modeling`, pattern metrics extraction
- `models/comms/` - Link budget (SNR, margin, EIRP), propagation models
- `models/radar/` - Radar equation, PD/PFA threshold helpers, integration gains
- `models/swapc/` - Power, thermal, and cost models
- `trades/` - DOE generation, batch runner, Pareto extraction, optimization
- `viz/` - Plots (Pareto, scatter-matrix), HTML/Markdown report generation
- `io/` - Config loading (YAML/JSON), results export (Parquet/CSV)
- `cli.py` - `pasys` command entrypoint

### Core Contracts

**ModelBlock Protocol:**
```python
class ModelBlock(Protocol):
    name: str
    def evaluate(self, arch: Architecture, scenario: Scenario, context: dict) -> dict:
        """Returns flat metrics dict"""
```

**Canonical Metrics Dictionary** (universal exchange format):
- Antenna: `g_peak_db`, `beamwidth_az_deg`, `beamwidth_el_deg`, `sll_db`, `scan_loss_db`
- Comms: `eirp_dbw`, `path_loss_db`, `snr_rx_db`, `link_margin_db`
- Radar: `snr_single_pulse_db`, `snr_required_db`, `snr_margin_db`, `pd`, `pfa`
- SWaP-C: `prime_power_w`, `weight_kg`, `cost_usd`
- Metadata: `meta.case_id`, `meta.runtime_s`, `meta.seed`, `meta.error`

### Data Flow
```
Config (YAML/JSON) → Pydantic validation → [Architecture + Scenario + RequirementSet]
    → DOE case generation → Batch evaluation (parallel, cached)
    → Requirement verification → Pareto extraction → Visualization/Reports
```

## Design Principles

1. **Requirements as first-class objects** - Every run produces pass/fail + margins with traceability
2. **Trade-space first** - DOE + Pareto over single-point designs; grey-out infeasible cases
3. **Flat metrics dictionary** - All models return consistent `dict[str, float]` for interchange
4. **Config-driven reproducibility** - Stable case IDs, seed control, version stamping
5. **Safe configs** - No `eval()`, data-driven configs only
6. **Case-level error handling** - DOE runs never crash for single-case failures

## Implementation Phases

All phases are complete as of v0.4.0:

1. **Phase 1 (MVP):** ✅ Complete
   - Pydantic schemas for Architecture, Scenario, RequirementSet
   - YAML/JSON config loader with validation
   - Requirements verification with pass/fail and margin reporting
   - Antenna adapter wrapping `phased-array-modeling`
   - Comms link budget model (EIRP, path loss, SNR, margins)

2. **Phase 2:** ✅ Complete
   - DOE generator with full-factorial and Latin hypercube sampling
   - Batch runner with parallel execution and resume capability
   - Pareto extraction for multi-objective optimization
   - Interactive plots (Pareto fronts, scatter matrices)
   - Parquet/CSV export for results

3. **Phase 3:** ✅ Complete
   - Radar equation model (SNR, detection range)
   - Detection threshold helpers (PD/PFA calculations)
   - Integration gain for pulse integration
   - Radar trade study examples

4. **Phase 4:** ✅ Complete
   - `pasys` CLI with run, doe, pareto, and report commands
   - HTML and Markdown report generation
   - Ready for PyPI publish

## Future Goals

**Interactive Web Application:** The package is designed to eventually power an interactive Streamlit or Vercel webapp for browser-based trade studies and visualization. Keep the core logic decoupled from CLI/reporting concerns to facilitate web integration.
