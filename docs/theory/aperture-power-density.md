# Aperture power density

Three quantities in this package share the words "power" and "density" and mean
different things. Read this table first.

| Quantity | Units | Where | What it is |
|---|---|---|---|
| Aperture heat flux | W/cm² | `heat_flux_w_per_cm2` | Dissipated power per unit **array aperture area**. Selects the cooling technology. |
| Radiated power density | W/cm² | `radiated_power_density_*_w_per_cm2` | Radiated power per unit aperture area, at the aperture face. |
| Far-field power density | W/m² | [radar equation](radar-equation.md) | Flux at a distant target, `S = P_t G_t / 4πR²`. Falls as 1/R². |
| PA power density | W/mm | `data/technologies.yaml` | Semiconductor power per unit **gate periphery**. A device property, not an array one. |
| Power-aperture product | W·m² | `power_aperture_product_w_m2` | Mission figure of merit. Dimensionally the **inverse** of a power density. |

The clutter `resolution_cell_m2` in the radar models is a patch of ground, not
an array unit cell.

## Geometry

`ArrayConfig` stores spacing in wavelengths and carries no frequency, so the
physical scale comes from the scenario:

$$A_{cell} = d_x d_y \lambda^2, \qquad A_{ap} = N A_{cell} = (n_x d_x)(n_y d_y)\lambda^2$$

with `dx`, `dy` in wavelengths. The radiating aperture is `N·d` per axis, not
the `(N−1)·d` tip-to-tip extent of the element centres: each element owns a
full cell.

## Why it earns a metric

At half-wave spacing $A_{cell} = (\lambda/2)^2 = (c/2f)^2$, so at fixed
per-element dissipation

$$q'' = \frac{P_{diss,elem}}{A_{cell}} \propto f^2$$

Doubling frequency quadruples aperture heat flux. Moving a design from X-band
to Ka-band multiplies it by about nine with no other change. This is the whole
reason the quantity is worth computing: nothing else in a system model tells
you that the same T/R module, unchanged, is an air-cooled design at 10 GHz and
a liquid-cooled one at 30 GHz.

The junction-temperature model is a **per-device** normalization:

$$T_j = T_{amb} + R_{th}\frac{P_{diss}}{N}$$

Dividing by element count answers "how hot is one device"; dividing by aperture
area answers "can the cooling approach remove this flux". They are different
questions, and the second is invisible to the first: packing elements tighter
leaves junction dissipation unchanged while raising heat flux as $1/d^2$.

## Averaging convention

Heat flux is reported on **average** power. Cold-plate and coolant-loop time
constants are seconds; a radar PRI is microseconds, so the plate sees the
duty-cycle-averaged load.

The junction does not average that way. GaN junction thermal time constants are
comparable to pulse widths, so within a pulse the junction rises above its
pulse-averaged value, and the pulse-to-pulse swing drives thermo-mechanical
fatigue. This package has no thermal transient model and makes no peak-junction
claim. Radiated power density is reported at both peak and average because peak
is what matters for field strength and average is what matters for heat.

## Cooling feasibility

`ReliabilityConfig.thermal_resistance_c_per_w` is an *assertion* about a cooling
solution. Setting `Architecture.cooling` checks it: the design's heat flux is
compared against what the declared class can remove, from `data/cooling.yaml`.

| Class | Gate (W/cm²) | Basis |
|---|---|---|
| `natural_convection` | 0.05 | judgment |
| `forced_air` | 1.0 | **quoted** (DARPA MACE target: 10 K rise at 1 W/cm²) |
| `liquid_cold_plate` | 20 | judgment, bounded below the DARPA ACM figure |
| `microchannel_two_phase` | 100 | judgment |

These are order-of-magnitude regime gates, not cliffs. Every entry records
whether its number was **quoted** from the primary source or is an
engineering-judgment gate consistent with it; two are quoted verbatim from
Bar-Cohen, Maurer & Felbinger (CS MANTECH 2013), and the entries relying on
Mudawar's 2001 IEEE review are marked judgment because that PDF renders its
numerals as embedded objects that text extractors drop. The catalog says so.

Crossing a boundary is not a smooth penalty. Going from forced air to a liquid
cold plate adds pumps, a heat exchanger, plumbing, coolant mass, leak paths and
a maintenance burden. That discreteness is what makes the metric useful in a
trade study.

## Power-aperture product

For volume search (Barton, *Radar Equations for Modern Radar*, 2013; Skolnik,
*Introduction to Radar Systems*, 3rd ed.):

$$P_{avg} A_e = \frac{4\pi k T_s L (S/N) R^4 \Omega}{\sigma t_s}$$

Frequency and antenna gain do not appear. Search performance depends on the
product of average power and effective aperture, not on how the aperture is
partitioned into beams. Required power-aperture scales as $R^4$ and as
$\Omega/t_s$: halving the revisit time doubles what the mission demands.

The two metrics pull in opposite directions, which is why the package computes
both. Power-aperture says how much power and aperture the mission needs; heat
flux constrains how tightly that power may be packaged. Optimizing either alone
produces a design that is oversized or unbuildable.

## What is not modeled

Die-level and junction-level heat flux (two to four orders of magnitude higher,
governed by spreading resistance through the module) belong to MMIC and package
design. RF exposure limits are a siting output, not a design driver, and a
plane-wave power density cannot establish compliance in the reactive near field
of a large array. Multipaction requires hard vacuum and applies to space
missions only; air breakdown at the aperture face of a ground array is orders
of magnitude away and binds inside high-power feed components instead.
