# Pareto Optimization

Theory of multi-objective optimization and Pareto analysis.

## Overview

In engineering design, we often face conflicting objectives (e.g., minimize cost while maximizing performance). Pareto optimization provides a framework for understanding these trade-offs.

## Multi-Objective Optimization

### Problem Formulation

A multi-objective optimization problem:

$$
\begin{aligned}
\text{minimize} \quad & \mathbf{f}(\mathbf{x}) = [f_1(\mathbf{x}), f_2(\mathbf{x}), ..., f_k(\mathbf{x})] \\
\text{subject to} \quad & \mathbf{g}(\mathbf{x}) \leq 0 \\
& \mathbf{x} \in \mathcal{X}
\end{aligned}
$$

Where:

- $\mathbf{x}$ = design variables
- $\mathbf{f}$ = objective functions
- $\mathbf{g}$ = constraints
- $\mathcal{X}$ = feasible design space

### Single vs. Multi-Objective

| Single Objective | Multi-Objective |
|------------------|-----------------|
| One best solution | Set of trade-off solutions |
| Global optimum | Pareto frontier |
| Unique | Non-unique |

## Dominance

### Definition

Design $\mathbf{a}$ **dominates** design $\mathbf{b}$ (written $\mathbf{a} \prec \mathbf{b}$) if:

1. $f_i(\mathbf{a}) \leq f_i(\mathbf{b})$ for all objectives $i$ (at least as good)
2. $f_j(\mathbf{a}) < f_j(\mathbf{b})$ for at least one objective $j$ (strictly better)

### Example

Consider cost minimization and EIRP maximization (converted to minimization as -EIRP):

| Design | Cost | -EIRP | Dominated By |
|--------|------|-------|--------------|
| A | 20k | -42 | None (Pareto) |
| B | 30k | -48 | None (Pareto) |
| C | 25k | -40 | A |
| D | 35k | -46 | B |

Design A dominates C because: cost(A) < cost(C) and -EIRP(A) < -EIRP(C).

## Pareto Optimality

### Definition

A design $\mathbf{x}^*$ is **Pareto optimal** (or non-dominated) if there exists no other feasible design that dominates it.

The set of all Pareto optimal designs forms the **Pareto frontier** (or Pareto front).

### Properties

1. **Non-unique**: Multiple Pareto-optimal solutions
2. **Trade-off**: Improving one objective requires sacrificing another
3. **Incomparable**: No Pareto solution is better than another in all objectives

### Mathematical Definition

$$
\mathcal{P} = \{\mathbf{x}^* \in \mathcal{X} : \nexists \mathbf{x} \in \mathcal{X} \text{ such that } \mathbf{x} \prec \mathbf{x}^*\}
$$

## Pareto Frontier

### Characteristics

- Boundary of achievable objective space
- Shape depends on problem (convex, concave, or non-convex)
- All points represent valid optimal trade-offs

### Visualization (2 objectives)

```
Performance ↑
    │    ●  ← Pareto frontier
    │   ●
    │  ●   ○ ← Dominated
    │ ●   ○
    │●   ○ ○
    └──────────→ Cost
```

## Ranking Methods

Since all Pareto solutions are optimal, additional criteria are needed to rank them.

### Weighted Sum

$$
\min_{\mathbf{x}} \sum_{i=1}^{k} w_i f_i(\mathbf{x})
$$

Where $\sum w_i = 1$.

Advantages:

- Simple
- Single-objective problem

Limitations:

- Cannot find solutions on non-convex regions
- Sensitive to weight choice

### TOPSIS

Technique for Order Preference by Similarity to Ideal Solution.

1. Normalize objectives
2. Define ideal point: $\mathbf{f}^+$ (best of each)
3. Define anti-ideal: $\mathbf{f}^-$ (worst of each)
4. Calculate distances:
   $$
   d^+ = \sqrt{\sum_i w_i (f_i - f_i^+)^2}
   $$
   $$
   d^- = \sqrt{\sum_i w_i (f_i - f_i^-)^2}
   $$
5. Rank by relative closeness:
   $$
   C = \frac{d^-}{d^+ + d^-}
   $$

Higher $C$ is better (closer to ideal, farther from anti-ideal).

## Hypervolume

The hypervolume indicator measures Pareto front quality.

### Definition

Volume of objective space dominated by the Pareto front, bounded by a reference point:

$$
HV = \text{Vol}\left(\bigcup_{i=1}^{|\mathcal{P}|} \{\mathbf{f} : \mathbf{f}_i \prec \mathbf{f} \prec \mathbf{r}\}\right)
$$

Where $\mathbf{r}$ is the reference point.

### Properties

- Larger hypervolume = better Pareto front
- Accounts for both convergence and diversity
- Computationally expensive for many objectives

### 2D Example

```
Performance ↑
    │    ● r (reference)
    │   █│
    │  ██│ ← Hypervolume
    │ ███│
    │████│
    └──────────→ Cost
```

## Knee Points

The "knee" of the Pareto front represents designs with the best trade-off ratio.

### Detection

For normalized objectives, the knee minimizes:

$$
d = \sqrt{f_1^2 + f_2^2 + ... + f_k^2}
$$

### Significance

- Maximum "bang for buck"
- Often a good compromise solution
- Insensitive to small weight changes

## Algorithm Considerations

### Pareto Extraction Complexity

For $n$ designs and $k$ objectives:

- Naive: $O(n^2 k)$
- Efficient algorithms: $O(n \log^{k-1} n)$

### Epsilon-Dominance

Relaxed dominance for diversity:

$\mathbf{a}$ $\varepsilon$-dominates $\mathbf{b}$ if:

$$
f_i(\mathbf{a}) \leq (1 + \varepsilon) f_i(\mathbf{b}) \quad \forall i
$$

Reduces Pareto set size while maintaining coverage.

## Application to Phased Arrays

### Common Objectives

| Objective | Direction | Metric |
|-----------|-----------|--------|
| Cost | Minimize | `cost_usd` |
| EIRP | Maximize | `eirp_dbw` |
| Power | Minimize | `prime_power_w` |
| Mass | Minimize | `weight_kg` |
| Link Margin | Maximize | `link_margin_db` |

### Typical Trade-offs

1. **Cost vs. Performance**: More elements = higher cost, better performance
2. **Power vs. Performance**: Higher TX power = better performance, more cooling
3. **Size vs. Performance**: Larger aperture = better gain, larger platform

### Example Analysis

```python
from phased_array_systems.trades import extract_pareto, rank_pareto

objectives = [
    ("cost_usd", "minimize"),
    ("eirp_dbw", "maximize"),
]

pareto = extract_pareto(feasible, objectives)

# Rank with different weight scenarios
scenarios = {
    "Cost-focused": [0.8, 0.2],
    "Balanced": [0.5, 0.5],
    "Performance-focused": [0.2, 0.8],
}

for name, weights in scenarios.items():
    ranked = rank_pareto(pareto, objectives, weights=weights)
    best = ranked.iloc[0]
    print(f"{name}: {best['case_id']}, ${best['cost_usd']:,.0f}, {best['eirp_dbw']:.1f} dBW")
```

## Best Practices

1. **Verify feasibility first**: Filter infeasible designs before Pareto extraction
2. **Choose meaningful objectives**: Avoid redundant or correlated objectives
3. **Consider stakeholders**: Different weights for different decision-makers
4. **Present the frontier**: Show trade-offs, not just one solution
5. **Document decisions**: Record rationale for final selection

## See Also

- [User Guide: Pareto Analysis](../user-guide/pareto-analysis.md)
- [User Guide: Trade Studies](../user-guide/trade-studies.md)
- [API Reference: Trades](../api/trades.md)
