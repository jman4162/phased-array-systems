# pasys optimize

Optimize a design over the config's design space, either scalarized (scipy)
or multi-objective (NSGA-II).

## Synopsis

```bash
pasys optimize <config> --objective <metric> [options]
```

## Description

The `optimize` command searches the design space defined in the config's
`doe.variables` section. With the scipy methods it minimizes or maximizes a
single scalarized objective; with `--method nsga2` it returns the full
Pareto front for up to two objectives (requires the `[mdao]` extra).
Requirements in the config act as constraints: normalized penalties for the
scipy methods, constraint domination for NSGA-II.

## Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `config` | Yes | Path to configuration file (YAML or JSON) |

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `--objective` | (required) | Metric key to optimize |
| `--sense` | `maximize` | `maximize` or `minimize` |
| `--method` | `de` | `de`, `da`, `minimize`, or `nsga2` |
| `--objective2` | | Second objective for nsga2, as `metric:sense` |
| `--max-iter` | `200` | Maximum iterations (scipy methods) |
| `--generations` | `100` | NSGA-II generations |
| `--population` | `50` | NSGA-II population size |
| `--seed` | `42` | Random seed |
| `--output`, `-o` | | Save result (JSON; Parquet for nsga2) |

## Methods

- `de` — differential evolution: global, handles integer variables natively;
  the default and the recommended scipy method.
- `da` — dual annealing: global, continuous relaxation of integers.
- `minimize` — L-BFGS-B: local; only useful for all-continuous spaces.
- `nsga2` — multi-objective NSGA-II via pymoo: returns the nondominated
  set with full metrics per point instead of a single design. Install with
  `pip install "phased-array-systems[mdao]"`.

## Examples

Scalarized run:

```bash
pasys optimize config.yaml --objective eirp_dbw --sense maximize --method de
```

Pareto front for EIRP vs cost:

```bash
pasys optimize config.yaml --objective eirp_dbw --method nsga2 \
    --objective2 cost_usd:minimize --generations 100 --population 50 \
    -o pareto.parquet
```

The Parquet output has the same schema as DOE results, so `pasys report`
and `pasys pareto` work on it directly.
