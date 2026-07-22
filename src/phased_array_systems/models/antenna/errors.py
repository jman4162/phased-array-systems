"""Analytic array error-budget models.

Closed-form effects of random amplitude/phase errors and phase-shifter
quantization on gain, sidelobe floor, and beam pointing, for uncorrelated
element-to-element errors.

References:
    - Mailloux, R.J., "Phased Array Antenna Handbook", 2nd Ed., ch. 7
    - Skolnik, M., "Radar Handbook", 3rd Ed. (quantization effects)
"""

from __future__ import annotations

import math


def phase_error_loss_db(sigma_phi_rad: float) -> float:
    """Gain loss from uncorrelated RMS phase error.

    G/G0 = exp(-sigma_phi^2) (Ruze; Mailloux eq. 7.32).

    Args:
        sigma_phi_rad: RMS phase error (radians)

    Returns:
        Gain loss in dB (positive)
    """
    return -10.0 * math.log10(math.exp(-(sigma_phi_rad**2)))


def amplitude_error_loss_db(sigma_a_frac: float) -> float:
    """Gain loss from uncorrelated fractional RMS amplitude error.

    G/G0 = 1/(1 + sigma_a^2) (Mailloux sec. 7.2).

    Args:
        sigma_a_frac: Fractional RMS amplitude error (e.g. 0.1 for 10%)

    Returns:
        Gain loss in dB (positive)
    """
    return 10.0 * math.log10(1.0 + sigma_a_frac**2)


def phase_quantization_rms_rad(n_bits: int) -> float:
    """RMS phase error of an ideal N-bit phase shifter.

    Uniform quantization over a step of 2*pi/2^N gives
    sigma = step/sqrt(12) = pi / (2^N * sqrt(3)).

    Args:
        n_bits: Number of phase shifter bits (>= 1)

    Returns:
        RMS phase error in radians
    """
    if n_bits < 1:
        raise ValueError("n_bits must be >= 1")
    return float(math.pi / (2**n_bits * math.sqrt(3.0)))


def phase_quantization_loss_db(n_bits: int) -> float:
    """Gain loss from N-bit phase quantization.

    Applies the Ruze gain loss to the quantization RMS phase error:
    loss ~= (pi^2/3) * 2^(-2N) nepers (Mailloux sec. 7.4; e.g. 0.22 dB
    at 3 bits, 0.06 dB at 4 bits).

    Args:
        n_bits: Number of phase shifter bits (>= 1)

    Returns:
        Gain loss in dB (positive)
    """
    return phase_error_loss_db(phase_quantization_rms_rad(n_bits))


def rms_sidelobe_floor_db(
    sigma_total_sq: float,
    n_elements: int,
    taper_efficiency: float = 1.0,
) -> float:
    """Average (RMS) sidelobe floor from uncorrelated errors.

    Relative to the main-beam peak:
        floor = sigma^2 / (N * eta_taper)
    (Mailloux eq. 7.38), where sigma^2 is the total error variance
    (phase in rad^2 plus fractional-amplitude variance).

    Args:
        sigma_total_sq: Total error variance (rad^2 + fractional^2)
        n_elements: Number of array elements
        taper_efficiency: Aperture taper efficiency (0-1]

    Returns:
        Average sidelobe floor in dB relative to the main beam (negative);
        -inf for zero error
    """
    if n_elements < 1:
        raise ValueError("n_elements must be >= 1")
    if sigma_total_sq <= 0:
        return float("-inf")
    return 10.0 * math.log10(sigma_total_sq / (n_elements * max(1e-9, taper_efficiency)))


def beam_pointing_rms_deg(
    sigma_phi_rad: float,
    n_elements: int,
    beamwidth_deg: float,
) -> float:
    """RMS beam pointing error from uncorrelated phase errors.

    sigma_theta ~= beamwidth * sigma_phi / (1.13 * sqrt(N))
    (Mailloux sec. 7.2 order-of-magnitude estimate for a filled array).

    Args:
        sigma_phi_rad: RMS phase error (radians)
        n_elements: Number of array elements
        beamwidth_deg: 3-dB beamwidth (degrees)

    Returns:
        RMS pointing error in degrees
    """
    if n_elements < 1:
        raise ValueError("n_elements must be >= 1")
    return beamwidth_deg * sigma_phi_rad / (1.13 * math.sqrt(n_elements))


def error_budget(
    n_elements: int,
    taper_efficiency: float = 1.0,
    phase_bits: int | None = None,
    phase_error_rms_deg: float = 0.0,
    amplitude_error_rms_frac: float = 0.0,
    beamwidth_deg: float | None = None,
) -> dict[str, float]:
    """Aggregate analytic error budget for an array.

    Combines phase-shifter quantization with random amplitude/phase
    errors (all uncorrelated element-to-element).

    Args:
        n_elements: Number of array elements
        taper_efficiency: Aperture taper efficiency (0-1]
        phase_bits: Phase shifter bits (None = ideal, no quantization)
        phase_error_rms_deg: Random RMS phase error (degrees)
        amplitude_error_rms_frac: Fractional RMS amplitude error
        beamwidth_deg: 3-dB beamwidth for pointing error (None skips it)

    Returns:
        Dictionary with:
            - error_gain_loss_db: Total gain loss from all error terms
            - phase_quantization_loss_db: Quantization share of the loss
            - rms_sidelobe_floor_db: Average sidelobe floor vs main beam
            - pointing_error_rms_deg: RMS pointing error (0.0 if
              beamwidth_deg is None)
    """
    sigma_phi_rand = math.radians(phase_error_rms_deg)
    sigma_phi_quant = phase_quantization_rms_rad(phase_bits) if phase_bits else 0.0
    sigma_phi_sq = sigma_phi_rand**2 + sigma_phi_quant**2
    sigma_amp_sq = amplitude_error_rms_frac**2

    quant_loss = phase_quantization_loss_db(phase_bits) if phase_bits else 0.0
    total_loss = phase_error_loss_db(math.sqrt(sigma_phi_sq)) + amplitude_error_loss_db(
        amplitude_error_rms_frac
    )

    sigma_total_sq = sigma_phi_sq + sigma_amp_sq
    floor = rms_sidelobe_floor_db(sigma_total_sq, n_elements, taper_efficiency)

    pointing = (
        beam_pointing_rms_deg(math.sqrt(sigma_phi_sq), n_elements, beamwidth_deg)
        if beamwidth_deg is not None
        else 0.0
    )

    return {
        "error_gain_loss_db": total_loss,
        "phase_quantization_loss_db": quant_loss,
        "rms_sidelobe_floor_db": floor,
        "pointing_error_rms_deg": pointing,
    }
