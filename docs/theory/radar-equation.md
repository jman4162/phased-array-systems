# Radar Equation

Derivation and application of the radar range equation.

## Overview

The radar equation relates transmitter power, antenna gain, target characteristics, and receiver sensitivity to determine detection capability.

## Basic Radar Equation

### Power Density at Target

Power density at range $R$ from an isotropic radiator:

$$
S_i = \frac{P_t}{4\pi R^2}
$$

With transmit antenna gain $G_t$:

$$
S_t = \frac{P_t G_t}{4\pi R^2}
$$

### Power Reflected by Target

The target intercepts and re-radiates power proportional to its radar cross section (RCS) $\sigma$:

$$
P_{reflected} = S_t \cdot \sigma = \frac{P_t G_t \sigma}{4\pi R^2}
$$

### Power Density at Receiver

The reflected power spreads again over $4\pi R^2$:

$$
S_r = \frac{P_t G_t \sigma}{(4\pi)^2 R^4}
$$

### Received Power

The receiver antenna with effective area $A_e$ captures:

$$
P_r = S_r \cdot A_e = \frac{P_t G_t \sigma A_e}{(4\pi)^2 R^4}
$$

Using $A_e = G_r \lambda^2 / 4\pi$:

$$
P_r = \frac{P_t G_t G_r \lambda^2 \sigma}{(4\pi)^3 R^4}
$$

For monostatic radar ($G_t = G_r = G$):

$$
P_r = \frac{P_t G^2 \lambda^2 \sigma}{(4\pi)^3 R^4}
$$

## SNR Form

Including noise and losses:

$$
SNR = \frac{P_t G^2 \lambda^2 \sigma}{(4\pi)^3 R^4 k T_s B_n L_s}
$$

Where:

- $P_t$ = Peak transmit power (W)
- $G$ = Antenna gain (linear)
- $\lambda$ = Wavelength (m)
- $\sigma$ = Target RCS (m²)
- $R$ = Range (m)
- $k$ = Boltzmann constant = 1.38×10⁻²³ J/K
- $T_s$ = System noise temperature (K)
- $B_n$ = Noise bandwidth (Hz)
- $L_s$ = System losses (linear)

## Range Form

Solving for range at minimum detectable SNR:

$$
R_{max} = \left[\frac{P_t G^2 \lambda^2 \sigma}{(4\pi)^3 k T_s B_n L_s \cdot SNR_{min}}\right]^{1/4}
$$

## Pulse Integration

### Coherent Integration

For $N$ coherently integrated pulses:

$$
SNR_N = N \cdot SNR_1
$$

The integration gain is $N$ (linear) or $10\log_{10}(N)$ dB.

### Non-Coherent Integration

For non-coherent integration:

$$
SNR_N \approx \sqrt{N} \cdot SNR_1
$$

More precisely, the integration gain depends on the required $P_d$ and $P_{fa}$.

## Detection Theory

### Single-Pulse Detection

For a Gaussian noise background and non-fluctuating target (Swerling 0), the detection probability relates to SNR through:

$$
P_d = \frac{1}{2}\text{erfc}\left[\text{erfc}^{-1}(2P_{fa}) - \sqrt{SNR}\right]
$$

### Required SNR

For given $P_d$ and $P_{fa}$:

$$
SNR_{req} \approx \ln\left(\frac{1}{P_{fa}}\right) + \ln\left(\frac{1}{1-P_d}\right)
$$

More accurate:

| $P_d$ | $P_{fa} = 10^{-6}$ | $P_{fa} = 10^{-9}$ |
|-----------|------------------------|------------------------|
| 0.5 | 10.8 dB | 12.6 dB |
| 0.9 | 13.1 dB | 14.9 dB |
| 0.99 | 16.4 dB | 18.2 dB |

## Swerling Target Models

| Model | PDF | Decorrelation |
|-------|-----|---------------|
| 0 | Constant (non-fluctuating) | - |
| 1 | Exponential (Rayleigh amplitude) | Scan-to-scan |
| 2 | Exponential | Pulse-to-pulse |
| 3 | Chi-squared, 4 DOF | Scan-to-scan |
| 4 | Chi-squared, 4 DOF | Pulse-to-pulse |

### SNR Penalty

Fluctuating targets require additional SNR:

| Model | Typical Penalty vs. SW0 |
|-------|-------------------------|
| SW1 | +3 to +8 dB (depends on $P_d$) |
| SW2 | +2 to +5 dB |
| SW3 | +1 to +3 dB |
| SW4 | +1 to +2 dB |

## Power-Aperture Product

Radar performance fundamentally scales with:

$$
PA = P_t \cdot A = P_t \cdot \frac{G\lambda^2}{4\pi}
$$

For a given target and detection requirement:

$$
R_{max}^4 \propto PA
$$

Trade-off: Higher power OR larger aperture.

## Example Calculation

**Given:**
- Frequency: 10 GHz ($\lambda$ = 0.03 m)
- Array: 16×16 elements, G = 30 dBi
- TX power: 10 W/element, 256 elements → 2560 W peak
- Target RCS: 1 m²
- Range: 100 km
- Noise temp: 400 K
- Losses: 4 dB ($L_s$ = 2.51)
- Pulse width: 10 μs → $B_n$ ≈ 100 kHz

**Calculate:**

1. **Wavelength:** $\lambda$ = 0.03 m

2. **Gain (linear):** $G$ = 10^(30/10) = 1000

3. **Numerator:**
$$
P_t G^2 \lambda^2 \sigma = 2560 \times 1000^2 \times 0.03^2 \times 1 = 2.3 \times 10^6
$$

4. **Denominator:**
$$
(4\pi)^3 R^4 k T_s B_n L_s = 1984 \times 10^{20} \times 1.38 \times 10^{-23} \times 400 \times 10^5 \times 2.51
$$
$$
= 2.74 \times 10^6
$$

5. **SNR (single pulse):**
$$
SNR = \frac{2.3 \times 10^6}{2.74 \times 10^6} = 0.84 = -0.75 \text{ dB}
$$

6. **With 10-pulse coherent integration:**
$$
SNR_{10} = -0.75 + 10 = 9.25 \text{ dB}
$$

7. **Required SNR** for $P_d$ = 0.9, $P_{fa}$ = 10⁻⁶, SW1 ≈ 17 dB

8. **SNR Margin:**
$$
M = 9.25 - 17 = -7.75 \text{ dB} \quad \text{(insufficient)}
$$

Need more power, more elements, or shorter range.

## Range Dependencies

| Quantity | Range Dependence |
|----------|------------------|
| $P_r$ | $R^{-4}$ |
| $SNR$ | $R^{-4}$ |
| Double range | -12 dB SNR |
| Half range | +12 dB SNR |

## See Also

- [Phased Array Fundamentals](phased-arrays.md)
- [Link Budget Equations](link-budget-equations.md)
- [User Guide: Radar Detection](../user-guide/radar-detection.md)
