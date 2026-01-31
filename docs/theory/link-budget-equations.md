# Link Budget Equations

Complete derivation of communications link budget calculations.

## Overview

A link budget accounts for all gains and losses in a communications link, from transmitter to receiver.

## Link Budget Equation

The fundamental equation:

$$
P_{rx} = P_{tx} + G_{tx} - L_{tx} - L_{path} + G_{rx} - L_{rx}
$$

All quantities in dB.

## EIRP (Effective Isotropic Radiated Power)

EIRP is the power that would be radiated by an isotropic antenna to produce the same field intensity:

$$
EIRP = P_{tx} + G_{tx} - L_{tx}
$$

Where:

- $P_{tx}$ = Transmitter power output (dBW)
- $G_{tx}$ = Transmit antenna gain (dBi)
- $L_{tx}$ = Transmit losses (feed, radome, etc.) (dB)

### For Phased Arrays

$$
P_{tx} = 10\log_{10}(N \cdot P_{elem})
$$

Where $N$ is element count and $P_{elem}$ is power per element in watts.

## Path Loss

### Free Space Path Loss (FSPL)

$$
L_{FSPL} = 20\log_{10}\left(\frac{4\pi d f}{c}\right)
$$

Or equivalently:

$$
L_{FSPL} = 32.45 + 20\log_{10}(f_{MHz}) + 20\log_{10}(d_{km})
$$

Or:

$$
L_{FSPL} = 92.45 + 20\log_{10}(f_{GHz}) + 20\log_{10}(d_{km})
$$

### Example: 10 GHz, 100 km

$$
L_{FSPL} = 92.45 + 20\log_{10}(10) + 20\log_{10}(100) = 92.45 + 20 + 40 = 152.45 \text{ dB}
$$

### Additional Losses

Total path loss:

$$
L_{path} = L_{FSPL} + L_{atm} + L_{rain} + L_{pol} + L_{misc}
$$

| Loss Type | Typical Range |
|-----------|---------------|
| Atmospheric | 0.1-2 dB (depends on f, elevation) |
| Rain fade | 0-20 dB (depends on f, availability) |
| Polarization | 0-3 dB (mismatch) |

## Received Power

$$
P_{rx} = EIRP - L_{path} + G_{rx}
$$

## Noise Power

### Thermal Noise

$$
N = kTB
$$

Where:

- $k$ = Boltzmann constant = 1.38×10⁻²³ J/K
- $T$ = System noise temperature (K)
- $B$ = Bandwidth (Hz)

In dB:

$$
N_{dBW} = 10\log_{10}(kTB) = -228.6 + 10\log_{10}(T) + 10\log_{10}(B)
$$

### System Noise Temperature

$$
T_{sys} = T_{ant} + T_{rx}
$$

Where:

$$
T_{rx} = T_0(F - 1)
$$

- $T_0$ = Reference temperature (290 K)
- $F$ = Noise figure (linear)

### Noise Figure

$$
F_{dB} = 10\log_{10}(F) = 10\log_{10}\left(1 + \frac{T_{rx}}{T_0}\right)
$$

Total noise power including noise figure:

$$
N_{dBW} = 10\log_{10}(kT_0B) + NF_{dB}
$$

## Signal-to-Noise Ratio

$$
SNR = P_{rx} - N
$$

Expanding:

$$
SNR = EIRP - L_{path} + G_{rx} - 10\log_{10}(kT_0B) - NF
$$

## Link Margin

$$
M = SNR - SNR_{required}
$$

Positive margin indicates the link closes with room to spare.

## G/T Figure of Merit

For receive systems, G/T characterizes sensitivity:

$$
\frac{G}{T} = G_{rx} - 10\log_{10}(T_{sys})
$$

Units: dB/K

## Complete Link Budget Example

**Given:**
- Frequency: 10 GHz
- Range: 100 km
- TX array: 8×8, 1 W/element, 65% efficiency
- TX losses: 1.5 dB
- RX antenna gain: 30 dBi
- RX noise figure: 3 dB
- RX noise temp: 290 K
- Bandwidth: 10 MHz
- Required SNR: 10 dB
- Atmospheric loss: 0.5 dB

**Calculation:**

1. **TX Power:**
$$
P_{tx} = 10\log_{10}(64 \times 1) = 18.1 \text{ dBW}
$$

2. **TX Gain:**
$$
G_{tx} = 10\log_{10}(0.65 \times \pi \times 64) = 21.2 \text{ dB}
$$

3. **EIRP:**
$$
EIRP = 18.1 + 21.2 - 1.5 = 37.8 \text{ dBW}
$$

4. **Path Loss:**
$$
L_{path} = 152.4 + 0.5 = 152.9 \text{ dB}
$$

5. **Received Power:**
$$
P_{rx} = 37.8 - 152.9 + 30 = -85.1 \text{ dBW}
$$

6. **Noise Power:**
$$
N = 10\log_{10}(1.38 \times 10^{-23} \times 290 \times 10^7) + 3 = -131.0 \text{ dBW}
$$

7. **SNR:**
$$
SNR = -85.1 - (-131.0) = 45.9 \text{ dB}
$$

8. **Link Margin:**
$$
M = 45.9 - 10 = 35.9 \text{ dB}
$$

## Trade-offs

### EIRP Improvements

| Change | EIRP Gain |
|--------|-----------|
| Double TX power | +3 dB |
| Double elements (2×) | +6 dB (gain + power) |
| Double aperture | +6 dB |

### Reducing Path Loss

- Lower frequency (but larger antenna for same gain)
- Shorter range ($L \propto d^2$)

### Improving Receiver

| Change | Effect |
|--------|--------|
| Higher G/T | Better sensitivity |
| Lower NF | +1 dB NF reduction = +1 dB SNR |
| Narrower BW | Lower noise (but also signal BW) |

## See Also

- [Phased Array Fundamentals](phased-arrays.md)
- [Radar Equation](radar-equation.md)
- [User Guide: Link Budget](../user-guide/link-budget.md)
