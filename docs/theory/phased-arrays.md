# Phased Array Fundamentals

Theory of phased array antenna operation.

## Overview

A phased array is an antenna system that uses multiple radiating elements with controlled phase and amplitude to electronically steer the beam without mechanical movement.

## Array Factor

The array factor describes the radiation pattern contribution from element positioning:

$$
AF(\theta, \phi) = \sum_{n=1}^{N} a_n e^{j(k \mathbf{r}_n \cdot \hat{\mathbf{r}} + \alpha_n)}
$$

Where:

- $a_n$ = amplitude weight of element $n$
- $k = 2\pi/\lambda$ = wavenumber
- $\mathbf{r}_n$ = position of element $n$
- $\hat{\mathbf{r}}$ = unit vector in observation direction
- $\alpha_n$ = phase of element $n$

### Linear Array

For a uniform linear array along the z-axis with spacing $d$:

$$
AF(\theta) = \sum_{n=0}^{N-1} e^{jn(kd\cos\theta + \beta)}
$$

Where $\beta$ is the progressive phase shift.

Closed form:

$$
AF(\theta) = \frac{\sin(N\psi/2)}{\sin(\psi/2)}, \quad \psi = kd\cos\theta + \beta
$$

### Rectangular Planar Array

For an $N_x \times N_y$ array:

$$
AF(\theta, \phi) = AF_x(\theta, \phi) \cdot AF_y(\theta, \phi)
$$

$$
AF_x = \frac{\sin(N_x \psi_x / 2)}{\sin(\psi_x / 2)}, \quad \psi_x = kd_x \sin\theta\cos\phi + \beta_x
$$

$$
AF_y = \frac{\sin(N_y \psi_y / 2)}{\sin(\psi_y / 2)}, \quad \psi_y = kd_y \sin\theta\sin\phi + \beta_y
$$

## Antenna Gain

### Directivity

The directivity is the ratio of radiation intensity in a given direction to the average:

$$
D = \frac{4\pi U(\theta, \phi)}{P_{rad}}
$$

Peak directivity for a uniform array (boresight):

$$
D_0 \approx \frac{4\pi A_{eff}}{\lambda^2} = \frac{4\pi}{\lambda^2} \cdot N_x d_x \cdot N_y d_y \cdot \lambda^2 = 4\pi N_x d_x N_y d_y
$$

### Gain

Gain includes efficiency:

$$
G = \eta_a \cdot D
$$

Where aperture efficiency $\eta_a$ typically ranges from 0.5 to 0.8.

For uniform amplitude and half-wavelength spacing ($d = 0.5\lambda$):

$$
G \approx \eta_a \cdot \pi \cdot N_x \cdot N_y
$$

In dB:

$$
G_{dB} = 10\log_{10}(\eta_a \cdot \pi \cdot N)
$$

For $\eta_a = 0.65$ and $N = 64$ elements:

$$
G_{dB} = 10\log_{10}(0.65 \cdot \pi \cdot 64) \approx 22.1 \text{ dB}
$$

## Beamwidth

### Half-Power Beamwidth (HPBW)

For a uniform linear array:

$$
\theta_{3dB} \approx \frac{0.886 \lambda}{N d \cos\theta_0}
$$

At boresight ($\theta_0 = 0$) with $d = 0.5\lambda$:

$$
\theta_{3dB} \approx \frac{1.77}{N} \text{ radians} = \frac{101°}{N}
$$

For a rectangular array:

$$
\theta_{3dB,x} \approx \frac{101°}{N_x}, \quad \theta_{3dB,y} \approx \frac{101°}{N_y}
$$

### Examples

| Array | Elements | HPBW |
|-------|----------|------|
| 8×8 | 64 | 12.6° × 12.6° |
| 16×16 | 256 | 6.3° × 6.3° |
| 32×32 | 1024 | 3.2° × 3.2° |

## Beam Steering

Electronic beam steering is achieved by applying a progressive phase shift:

$$
\beta_x = -kd_x \sin\theta_0 \cos\phi_0
$$
$$
\beta_y = -kd_y \sin\theta_0 \sin\phi_0
$$

Where $(\theta_0, \phi_0)$ is the desired beam direction.

### Scan Loss

When scanning off boresight, gain is reduced:

$$
G(\theta) \approx G_0 \cos^p(\theta)
$$

Where $p$ depends on element pattern (typically $p \approx 1.2-1.5$).

Approximate scan loss:

| Scan Angle | Approximate Loss |
|------------|------------------|
| 0° | 0 dB |
| 30° | 1-2 dB |
| 45° | 2-3 dB |
| 60° | 3-5 dB |

## Grating Lobes

Grating lobes appear when element spacing exceeds $\lambda$. To avoid grating lobes when scanning to angle $\theta_0$:

$$
d < \frac{\lambda}{1 + |\sin\theta_0|}
$$

For $\theta_0 = 60°$:

$$
d < \frac{\lambda}{1 + \sin(60°)} = \frac{\lambda}{1.866} \approx 0.54\lambda
$$

This is why half-wavelength spacing ($d = 0.5\lambda$) is common.

## Sidelobe Level

For a uniform amplitude array, the first sidelobe is approximately -13.2 dB below the main lobe.

### Tapering

Amplitude tapering reduces sidelobes at the cost of beamwidth and gain:

| Taper | First SLL | Beamwidth Factor | Efficiency |
|-------|-----------|------------------|------------|
| Uniform | -13.2 dB | 1.0 | 1.0 |
| Hamming | -42 dB | 1.36 | 0.73 |
| Taylor -25 dB | -25 dB | 1.1 | 0.95 |
| Taylor -35 dB | -35 dB | 1.2 | 0.87 |

## Power and EIRP

### Total Radiated Power

$$
P_{rad} = N \cdot P_{elem} \cdot \eta_{feed}
$$

Where:

- $N$ = number of elements
- $P_{elem}$ = power per element
- $\eta_{feed}$ = feed network efficiency

### EIRP

Effective Isotropic Radiated Power:

$$
EIRP = P_{rad} \cdot G = N \cdot P_{elem} \cdot \eta_{feed} \cdot G
$$

In dB:

$$
EIRP_{dBW} = P_{rad,dBW} + G_{dB}
$$

## Example Calculation

For an 8×8 array with:

- $d_x = d_y = 0.5\lambda$
- $P_{elem} = 1$ W
- $\eta_a = 0.65$
- $\eta_{feed} = 0.8$

**Gain:**
$$
G = 0.65 \cdot \pi \cdot 64 = 130.7 = 21.2 \text{ dB}
$$

**Radiated Power:**
$$
P_{rad} = 64 \cdot 1 \cdot 0.8 = 51.2 \text{ W} = 17.1 \text{ dBW}
$$

**EIRP:**
$$
EIRP = 17.1 + 21.2 = 38.3 \text{ dBW}
$$

**Beamwidth:**
$$
\theta_{3dB} \approx \frac{101°}{8} = 12.6°
$$

## See Also

- [Link Budget Equations](link-budget-equations.md)
- [Radar Equation](radar-equation.md)
- [User Guide: Architecture](../user-guide/architecture.md)
