# Installation

This guide covers different installation methods for phased-array-systems.

## Requirements

- **Python**: 3.10 or later
- **Operating System**: Windows, macOS, or Linux
- **Dependencies**: Automatically installed with the package

## Quick Install

Install from PyPI using pip:

```bash
pip install phased-array-systems
```

## Installation Options

### Standard Installation

For basic usage with core dependencies:

```bash
pip install phased-array-systems
```

This installs:

- `phased-array-modeling>=1.2.0` - Array pattern computations
- `numpy>=1.24.0` - Numerical computations
- `scipy>=1.10.0` - Scientific computing
- `pydantic>=2.0` - Data validation
- `matplotlib>=3.7.0` - Plotting
- `pandas>=2.0.0` - Data manipulation
- `pyyaml>=6.0` - Configuration loading

### With Plotting Extras

For interactive Plotly visualizations:

```bash
pip install "phased-array-systems[mdao]"       # NSGA-II optimization + Sobol sensitivity
pip install phased-array-systems[plotting]
```

Additional packages:

- `plotly>=5.0` - Interactive plots
- `kaleido>=0.2` - Static image export

### Development Installation

For contributing or running tests:

```bash
pip install phased-array-systems[dev]
```

Additional packages:

- `pytest>=7.0` - Testing framework
- `pytest-cov>=4.0` - Coverage reporting
- `ruff>=0.1.0` - Linting and formatting
- `mypy>=1.0` - Type checking
- `pandas-stubs>=2.0` - Pandas type stubs

### Documentation Build

For building documentation locally:

```bash
pip install phased-array-systems[docs]
```

Additional packages:

- `mkdocs>=1.5` - Documentation generator
- `mkdocs-material>=9.4` - Material theme
- `mkdocstrings[python]>=0.24` - API docs from docstrings
- `mkdocs-jupyter>=0.24` - Jupyter notebook support

### Full Installation

Install everything:

```bash
pip install phased-array-systems[dev,plotting,docs]
```

## Installing from Source

### Clone and Install

```bash
# Clone the repository
git clone https://github.com/jman4162/phased-array-systems.git
cd phased-array-systems

# Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in editable mode with all extras
pip install -e ".[dev,plotting,docs]"
```

### Using a Virtual Environment

We recommend using a virtual environment to avoid conflicts:

=== "venv (Built-in)"

    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    pip install phased-array-systems
    ```

=== "conda"

    ```bash
    conda create -n pasys python=3.11
    conda activate pasys
    pip install phased-array-systems
    ```

=== "uv"

    ```bash
    uv venv
    source .venv/bin/activate
    uv pip install phased-array-systems
    ```

## Verifying Installation

After installation, verify everything works:

```python
import phased_array_systems
print(phased_array_systems.__version__)
```

Or run a quick test:

```python
from phased_array_systems.architecture import ArrayConfig

# Create a simple array configuration
array = ArrayConfig(nx=8, ny=8, dx_lambda=0.5, dy_lambda=0.5)
print(f"Array has {array.n_elements} elements")
```

Expected output:

```
Array has 64 elements
```

## CLI Verification

The package includes a command-line interface:

```bash
pasys --version
```

```bash
pasys --help
```

## Troubleshooting

### phased-array-modeling Not Found

If you see an error about `phased-array-modeling`:

```bash
pip install phased-array-modeling>=1.2.0
```

### Import Errors

Ensure you're using the correct Python environment:

```bash
which python  # On Windows: where python
python -c "import phased_array_systems; print('OK')"
```

### Permission Errors

On some systems, you may need to use `--user`:

```bash
pip install --user phased-array-systems
```

Or use a virtual environment (recommended).

### Version Conflicts

If you have conflicting packages, try a fresh environment:

```bash
python -m venv fresh_env
source fresh_env/bin/activate
pip install phased-array-systems
```

## Upgrading

To upgrade to the latest version:

```bash
pip install --upgrade phased-array-systems
```

## Uninstalling

To remove the package:

```bash
pip uninstall phased-array-systems
```

## Next Steps

- [Run the quickstart example](quickstart.md)
- [Learn core concepts](concepts.md)
- [Explore the user guide](../user-guide/index.md)
