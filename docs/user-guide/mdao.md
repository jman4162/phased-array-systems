# MDAO Tools

v0.9 adds multi-objective optimization, global sensitivity, constraint-aware
sampling, search-timeline metrics, and thermal-reliability coupling. The
optimization and sensitivity solvers need the optional extra:

```bash
pip install "phased-array-systems[mdao]"   # pymoo + SALib
```

## Multi-objective optimization (NSGA-II)

`optimize_pareto` returns the nondominated set directly instead of collapsing
objectives into a weighted sum:

```python
from phased_array_systems.trades import DesignSpace, optimize_pareto

space = (
    DesignSpace()
    .add_variable("array.nx", "categorical", values=[8, 16, 32])
    .add_variable("array.ny", "categorical", values=[8, 16, 32])
    .add_variable("rf.tx_power_w_per_elem", "float", low=0.5, high=2.0)
)
front = optimize_pareto(
    space,
    scenario,
    objectives=[("eirp_dbw", "maximize"), ("cost_usd", "minimize")],
    requirements=requirements,   # must-severity become constraints
    n_generations=100,
    pop_size=50,
    seed=42,
)
```

The result is a DataFrame with the same schema as batch-runner output, so
`pareto_plot`, reports, and exporters work unchanged. Requirements with
severity `must` enter as normalized inequality constraints handled by
constraint domination; no penalty weight to tune. Mixed variable types
(float/int/categorical) are handled natively.

CLI: `pasys optimize config.yaml --objective eirp_dbw --method nsga2
--objective2 cost_usd:minimize -o pareto.parquet`

## Constraint-aware DOE

Box sampling wastes points on architectures that fail construction (the
sub-array divisibility rules). Rejection sampling keeps only buildable rows:

```python
doe = generate_doe(space, n_samples=100, seed=42, validate="architecture")
```

Fixed fields the sampled variables don't cover go in `base_config`. Batches
re-draw deterministically until the target count is met; a warning fires if
the feasible fraction is too small.

## Sobol global sensitivity

One-at-a-time sweeps miss interactions. Sobol indices attribute output
variance to each input (S1 first-order, ST total including interactions):

```python
from phased_array_systems.trades import sobol_sensitivity

indices = sobol_sensitivity(
    space_numeric,               # float/int variables only
    scenario,
    metric_keys=["eirp_dbw", "prime_power_w"],
    base_config={"array.nx": 16, "array.ny": 16},
    n_base=256,
)
```

Variance-based methods need a near-rectangular feasible domain, so keep
constrained integers (like `array.nx` under the sub-array rule) in
`base_config` rather than sampling them. From the command line, run
`pasys sensitivity config.yaml --sens-method sobol`.

## Search timeline metrics

Setting `prf_hz` plus search extents on a radar scenario wires the antenna
beamwidths into revisit-rate metrics:

```yaml
scenario:
  type: radar
  # ...
  n_pulses: 16
  prf_hz: 2000.0
  search_az_extent_deg: 90.0
  search_el_extent_deg: 30.0
  beam_overhead_us: 10.0
  search_frame_time_ms: 2000.0   # optional budget
```

Emitted metrics: `dwell_time_ms`, `n_beam_positions`, `search_frame_time_s`,
`search_update_rate_hz`, and (with a frame budget) `timeline_occupancy` —
values above 1 mean the search task is oversubscribed, a natural `must`
requirement.

## Thermal-reliability coupling

With a thermal resistance configured, the TRM junction temperature is
estimated from the power model's dissipated heat and drives the Arrhenius
MTBF derating — so array size, TX power, and duty cycle affect reliability:

```yaml
reliability:
  thermal_resistance_c_per_w: 20.0   # junction-to-ambient per TRM
  ambient_temp_c: 25.0
```

The estimate is feed-forward (`junction_temp_c` metric); the static
`operating_temp_c` input still applies when no thermal resistance is given.

## Interactive plots

With the `[plotting]` extra installed, `viz.interactive` provides
`pareto_plot_interactive` and `trade_space_plot_interactive` (hover shows
case_id and metrics), and HTML reports embed a self-contained interactive
Pareto section when `ReportConfig.objectives` lists two objectives.
