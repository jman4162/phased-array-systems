# Track Accuracy

This package does not contain a tracker. It runs no recursion, holds no state,
and processes no detections; the design document lists a real-time DSP tracker
as a non-goal and that line stands. What it computes is the **steady-state**
result, which is algebra rather than recursion: under stationary noise and a
constant revisit interval, the Kalman filter settles to gains and a covariance
available in closed form. A designer needs that number long before any filter
exists.

The chain is:

$$
\text{SNR, } B \;\rightarrow\; \sigma_R
\qquad
\text{SNR, } \theta_{3dB} \;\rightarrow\; \sigma_\theta \;\rightarrow\; \sigma_{cr} = R\,\sigma_\theta
$$

$$
\sigma_w,\; T,\; A_{max} \;\rightarrow\; \Gamma \;\rightarrow\; (\alpha, \beta)
\;\rightarrow\; \sigma_{pos},\; \sigma_{vel}
$$

Every input already exists here, which is why the model belongs in this package
rather than in a tracking library: the array sets the beamwidth, the radar
equation sets the SNR, and the scheduler sets the revisit interval. Tracking
libraries take the measurement covariance as **given**; none of them derive it
from an aperture.

## Measurement accuracy

$$
\sigma_R = \frac{\Delta R}{\sqrt{2\,\mathrm{SNR}}}, \qquad
\Delta R = \frac{\alpha c}{2B}
$$

$$
\sigma_\theta = \frac{\theta_{3dB}}{k_m \sqrt{2\,\mathrm{SNR}}}, \qquad
\theta_\phi = \frac{\theta_B}{\cos\phi}
$$

with $k_m \approx 1.6$ the monopulse difference-pattern slope. The angle form is
derived for SNR > 13 dB; below that the monopulse ratio is a biased estimate of
the angle and the variance is optimistic. `monopulse_snr_ok` reports whether the
case sits above the floor rather than silently extrapolating.

Thermal angle error combines in quadrature with the hardware pointing error from
`models/antenna/errors.py`, so phase-shifter bits and calibration residue
propagate all the way through to track accuracy.

### The SNR convention

Two conventions appear in the literature and differ by a factor of two:

| Source | Form | SNR means |
|---|---|---|
| POMR Eq. (18.33) | $\sigma_R = \Delta R/\sqrt{\mathrm{SNR}}$ | $2E/N_0$, matched-filter peak |
| Curry Eq. (8.6) | $\sigma_R = \Delta R/\sqrt{2\,S/N}$ | $E/N_0$ |

They are algebraically identical. This package's range equation produces the
Curry/Barton $S/N$, so every function uses the $\sqrt{2\,\mathrm{SNR}}$ form.
POMR's angle relation already carries the factor of two, so range, angle, and
Doppler end up on one convention.

## Cross-range dominates

Angle accuracy is a fixed fraction of a beamwidth, so cross-range error grows
linearly with range while range error does not. At X-band, 50 km, 20 dB SNR,
10 MHz bandwidth and a 64x64 array:

| Quantity | Value |
|---|---|
| $\sigma_R$ | 1.04 m |
| $\sigma_\theta$ | 0.068° |
| $\sigma_{cr}$ | 59.5 m |

Cross-range error is **57x** the range error. Both terms carry
$1/\sqrt{\mathrm{SNR}}$, so more power or longer dwell improves each equally
and leaves the ratio untouched. Only the aperture changes the ratio, by
narrowing $\theta_{3dB}$. Bandwidth, which buys range resolution cheaply, does
nothing for cross-range at all.

## Tracking index and steady-state gains

The random tracking index (Kalata 1984; POMR Eq. 19.47) is the single number
that sets the steady-state filter:

$$
\Gamma = \frac{\sigma_v T^2}{\sigma_w}
$$

the ratio of position uncertainty from target maneuverability to that from the
sensor. The optimal gains follow in closed form and satisfy the Kalata relation
$\beta = 2(2-\alpha) - 4\sqrt{1-\alpha}$, with steady-state error

$$
\mathbf{P} = \sigma_w^2
\begin{bmatrix}
\alpha & \beta/T \\
\beta/T & \dfrac{\beta(2\alpha-\beta)}{2(1-\alpha)T^2}
\end{bmatrix}
$$

so $\sigma_{pos} = \sigma_w\sqrt{\alpha}$.

Rather than asking for a process-noise variance, the model takes a physical
maneuver ($A_{max}$, "the target pulls 4 g") and derives $\sigma_v$ through
POMR Eqs. (19.63)/(19.66).

### Two correct covariance formulas

POMR Eq. (19.53) and Mahafza Eq. (11.94) disagree numerically because they
answer different questions. Both are reproduced by the same fixed-gain
covariance recursion, and both are emitted:

| Metric | Formula | Meaning |
|---|---|---|
| `track_pos_rms_*_m` | POMR Eq. (19.53) | total error, maneuver included |
| `track_vrr_*` | Mahafza Eq. (11.94) | sensor-noise reduction, no maneuver |

A third form circulating in the literature,
$(2\alpha^2 + 2\beta + \alpha\beta)/(\alpha(4-2\alpha-\beta))$, is wrong: it
exceeds unity, claiming that filtering amplifies noise. A canary test asserts
this package does not implement it.

### What the index tells a designer

The filter is applied per coordinate, and the two axes usually land in different
regimes. For the 50 km case above against a 40 m/s² maneuver at 1 Hz revisit:

| Axis | $\sigma_w$ | $\Gamma$ | $\alpha$ | Track $\sigma_{pos}$ |
|---|---|---|---|---|
| Range | 1.04 m | 26.0 | 0.996 | 1.04 m |
| Cross-range | 59.5 m | 0.60 | 0.660 | 48.3 m |

On the range axis the index is high: the maneuver is enormous relative to a
one-metre measurement, so the filter must trust each measurement almost
completely and smoothing buys nothing. The precise range measurement is wasted
on a maneuvering target. On the coarse cross-range axis filtering does help,
improving 59.5 m to 48.3 m. Overall track quality is set by the aperture, not
the waveform — which is a statement about the array, and therefore belongs in
this package.

## References

- Richards, Scheer & Holm, *Principles of Modern Radar: Basic Principles*,
  SciTech, 2010. Ch. 18 (measurements), Ch. 19 (tracking, W. D. Blair).
- Curry, *Radar System Performance Modeling*, 2nd ed., Artech House, 2005, ch. 8.
- Kalata, "The Tracking Index", *IEEE Trans. AES* 20(2), 174–182, 1984,
  doi:10.1109/TAES.1984.310438.
- Mahafza, *Radar Systems Analysis and Design Using MATLAB*, ch. 11.
- Barton & Ward, *Handbook of Radar Measurement*, Artech House, 1984.
