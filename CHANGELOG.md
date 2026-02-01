# Changelog

All notable changes to phased-array-systems will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.0] - 2026-02-01

### Added
- Digital array model for digital beamforming calculations
- RF cascade model for noise figure and gain cascade analysis
- Comprehensive documentation site with MkDocs Material
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

[Unreleased]: https://github.com/jman4162/phased-array-systems/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/jman4162/phased-array-systems/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/jman4162/phased-array-systems/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/jman4162/phased-array-systems/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/jman4162/phased-array-systems/releases/tag/v0.1.0
