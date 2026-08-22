# MTI Clutter Suppression

The clutter model computes how much clutter a geometry produces; it does not say
how much of it a radar can remove. That leaves the detection chain broken in the
middle. A ground-based L-band radar looking at wooded hills sees roughly 33 dB
more clutter than target, which the detection model scores as hopeless — yet
such radars work, because they filter clutter in Doppler. This page covers the
step that closes the gap:

$$
\text{clutter RCS} \;\rightarrow\; \boxed{\text{MTI improvement factor}}
\;\rightarrow\; \text{post-MTI SCNR} \;\rightarrow\; \text{detection}
$$

and, through SNR, on into [track accuracy](track-accuracy.md).

## Clutter spectrum

Clutter is modeled as a zero-mean Gaussian Doppler spectrum. The spread is a
property of the scatterers — wind-blown foliage, sea-surface motion — and
Skolnik notes it is frequency-independent when expressed as a velocity, so the
velocity form is the input:

$$
\sigma_c = \frac{2\sigma_v}{\lambda}, \qquad
\sigma_\omega = \frac{2\pi\sigma_c}{\mathrm{PRF}}
$$

The same hillside therefore produces a wider Doppler spectrum, and is harder to
cancel, at higher frequency. Only $\sigma_\omega$ — the spread relative to the
PRF — enters the canceller math.

The normalized autocorrelation of that spectrum (Richards FRSP Eq. 5.53, valid
for $\sigma_\omega \ll \pi$) is

$$
\rho_c[k] = e^{-(\sigma_\omega k)^2/2}
$$

## Binomial cancellers

The canceller is the $(N-1)$th-difference FIR filter with weights
$w_k = (-1)^k \binom{N-1}{k}$: $[1,-1]$ for two pulses, $[1,-2,1]$ for three.
The weights sum to zero, so stationary clutter is rejected exactly.

This package computes the improvement factor from the general quadratic form

$$
I = \frac{\sum_k w_k^2}{\sum_i \sum_j w_i w_j \, \rho_c[i-j]}
$$

rather than from tabulated closed forms. It reduces to them exactly — FRSP
Eq. (5.52) $I = 1/(1-\rho[1])$ for $N=2$, Eq. (5.54)
$I = 1/(1 - \frac{4}{3}\rho[1] + \frac{1}{3}\rho[2])$ for $N=3$ — and extends to
$N > 3$ where no closed form is tabulated. It is also better conditioned: the
three-pulse closed form differences three terms all near unity, and loses
precision as the clutter spectrum narrows.

### Improvement factor, not clutter attenuation

Three quantities are reported and they are not interchangeable:

| Quantity | Meaning |
|---|---|
| $G = \sum_k w_k^2$ | average signal gain over Doppler (FRSP p. 246) |
| $CA$ | clutter power ratio across the filter (FRSP Eq. 5.43) |
| $I = G \cdot CA$ | improvement in signal-to-clutter ratio (Levanon 1988) |

$I$ is what the detection budget consumes, because it accounts for both the
filter's gain on the target and its rejection of clutter. Quoting $CA$ alone
understates the benefit by $G$ — 3.0 dB for a two-pulse canceller, 7.8 dB for a
three-pulse.

## Blind speeds

A target whose Doppler shift is a multiple of the PRF advances in phase by a
full cycle between pulses, is indistinguishable from stationary clutter, and is
cancelled with it:

$$
v_{blind} = \frac{n \cdot \mathrm{PRF} \cdot \lambda}{2}
$$

A single-PRF MTI is only usable where the anticipated target Doppler band sits
clear of these nulls.

## Worked case: ARSR-3

An L-band air traffic control radar — 1.3 GHz, PRF 400 Hz, 2 µs pulse, 1.25°
azimuth beam, wooded-hill clutter at $\sigma^0 = -20$ dB, clutter velocity
spread 1.16 km/hr, 2 m² target at 30 nmi, 15 dB required S/C.

| Step | Value |
|---|---|
| Unambiguous range $c/2\mathrm{PRF}$ | 375 km |
| First blind speed | 46.1 m/s (400 Hz, clear of the 50–350 Hz target band) |
| Clutter cell area $R\theta_{az}(c\tau/2)$ | 3.64 × 10⁵ m² |
| Clutter RCS | 3637 m² = 35.6 dBsm |
| Required attenuation | 15 − (3 − 35.6) = **47.6 dB** |
| $\sigma_c$, $\sigma_\omega$ | 2.79 Hz, 0.0438 rad |
| Two-pulse: $I$, $G$, $CA$ | 30.2 dB, 3.0 dB, **27.2 dB** — insufficient |
| Three-pulse: $I$, $G$, $CA$ | 57.3 dB, 7.8 dB, **49.5 dB** — sufficient |

The three-pulse canceller is the shortest binomial canceller that meets the
requirement. Every figure in this table is asserted in
`tests/test_radar_mti_oracles.py`, which also gives the clutter model its first
end-to-end worked case.

Running the same geometry through `evaluate_case` shows what the missing step
was worth: with no MTI the target is undetectable ($P_d = 0$), with a two-pulse
canceller it is detected.

## References

- Richards, *Fundamentals of Radar Signal Processing*: Eq. (5.43), p. 246,
  Eq. (5.53), Eqs. (5.52)/(5.54) p. 247.
- Skolnik, *Introduction to Radar Systems*, ch. 15.
- Levanon, *Radar Principles*, Wiley, 1988.
