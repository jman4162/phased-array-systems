# pasys sensitivity

Rank design-variable influence on output metrics, one-at-a-time or with
Sobol global indices.

## Synopsis

```bash
pasys sensitivity <config> [options]
```

## Description

The `sensitivity` command sweeps the variables in the config's
`doe.variables` section. The default one-at-a-time (OAT) mode sweeps each
variable across its range while holding the others at the architecture
baseline. Sobol mode (`--sens-method sobol`, requires the `[mdao]` extra)
computes variance-based S1 (first-order) and ST (total, including
interactions) indices from a Saltelli sample.

## Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `config` | Yes | Path to configuration file (YAML or JSON) |

## Options

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--sens-method` | | `oat` | `oat` or `sobol` |
| `--steps` | `-n` | `5` | Steps per parameter (OAT) |
| `--samples` | | `256` | Sobol base sample count (total runs = samples × (2D + 2)) |
| `--metric` | | `g_peak_db` | Metric to analyze |
| `--plot` | | | Generate tornado plots (OAT) |
| `--output` | `-o` | | Save results (CSV/Parquet) |

## Choosing a method

OAT is cheap and shows local trends, but misses interactions between
variables. Sobol attributes shares of the output variance to each input
(and, via ST−S1, to its interactions), at the cost of many more
evaluations.

Sobol needs a near-rectangular feasible domain: variables constrained by
the sub-array rules (like `array.nx`) should stay fixed in the config's
architecture section rather than being swept.

## Examples

```bash
# One-at-a-time tornado analysis
pasys sensitivity config.yaml -n 7 --metric link_margin_db --plot

# Sobol global indices
pasys sensitivity config.yaml --sens-method sobol --samples 256 \
    --metric eirp_dbw -o sobol.parquet
```
