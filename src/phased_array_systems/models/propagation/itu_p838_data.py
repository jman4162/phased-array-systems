"""Coefficient tables for ITU-R P.838-3 (03/2005).

Tables 1-4 of Recommendation ITU-R P.838-3: constants for the
frequency-dependent regression coefficients k and alpha in the rain
specific-attenuation model gamma_R = k * R^alpha, for horizontal (H) and
vertical (V) linear polarization.

Each entry: (a_j, b_j, c_j) Gaussian terms plus (m, c) linear terms of
    log10 k = sum a_j exp(-((log10 f - b_j)/c_j)^2) + m_k log10 f + c_k
    alpha   = sum a_j exp(-((log10 f - b_j)/c_j)^2) + m_a log10 f + c_a

Source: https://www.itu.int/rec/R-REC-P.838-3-200503-I/en
"""

from __future__ import annotations

# Table 1: kH
KH_TERMS: tuple[tuple[float, float, float], ...] = (
    (-5.33980, -0.10008, 1.13098),
    (-0.35351, 1.26970, 0.45400),
    (-0.23789, 0.86036, 0.15354),
    (-0.94158, 0.64552, 0.16817),
)
KH_M = -0.18961
KH_C = 0.71147

# Table 2: kV
KV_TERMS: tuple[tuple[float, float, float], ...] = (
    (-3.80595, 0.56934, 0.81061),
    (-3.44965, -0.22911, 0.51059),
    (-0.39902, 0.73042, 0.11899),
    (0.50167, 1.07319, 0.27195),
)
KV_M = -0.16398
KV_C = 0.63297

# Table 3: alphaH
AH_TERMS: tuple[tuple[float, float, float], ...] = (
    (-0.14318, 1.82442, -0.55187),
    (0.29591, 0.77564, 0.19822),
    (0.32177, 0.63773, 0.13164),
    (-5.37610, -0.96230, 1.47828),
    (16.1721, -3.29980, 3.43990),
)
AH_M = 0.67849
AH_C = -1.95537

# Table 4: alphaV
AV_TERMS: tuple[tuple[float, float, float], ...] = (
    (-0.07771, 2.33840, -0.76284),
    (0.56727, 0.95545, 0.54039),
    (-0.20238, 1.14520, 0.26809),
    (-48.2991, 0.791669, 0.116226),
    (48.5833, 0.791459, 0.116479),
)
AV_M = -0.053739
AV_C = 0.83433
