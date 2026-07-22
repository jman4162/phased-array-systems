"""DAC/ADC converter models for digital phased arrays.

This module provides functions for analyzing data converter performance
including ENOB, SFDR, SNR, quantization noise, and sample rate constraints.

Key Relationships:
    - SNR (ideal) = 6.02 * ENOB + 1.76 dB
    - SFDR ≈ SNR for ideal converters (harmonics dominate)
    - Nyquist: fs >= 2 * BW (practical: fs >= 2.5 * BW)

References:
    - Kester, W. "Data Conversion Handbook", Analog Devices, 2005
    - IEEE Std 1241-2010: ADC Testing
"""

from __future__ import annotations

import math


def enob_to_snr(enob: float) -> float:
    """Convert Effective Number of Bits to SNR.

    The ideal SNR for a converter with ENOB effective bits is:
        SNR = 6.02 * ENOB + 1.76 dB

    This assumes full-scale sinusoidal input and ideal quantization.

    Args:
        enob: Effective number of bits

    Returns:
        SNR in dB
    """
    return 6.02 * enob + 1.76


def snr_to_enob(snr_db: float) -> float:
    """Convert SNR to Effective Number of Bits.

    Inverse of enob_to_snr:
        ENOB = (SNR - 1.76) / 6.02

    Useful for determining effective resolution from measured SNR.

    Args:
        snr_db: Signal-to-noise ratio in dB

    Returns:
        Effective number of bits
    """
    return (snr_db - 1.76) / 6.02


def enob_to_sfdr(enob: float, margin_db: float = 0.0) -> float:
    """Estimate SFDR from ENOB.

    For an ideal converter, SFDR is approximately equal to SNR.
    Real converters may have SFDR limited by harmonic distortion.

    Args:
        enob: Effective number of bits
        margin_db: Derate factor for non-ideal behavior (default 0)

    Returns:
        Estimated SFDR in dB
    """
    return enob_to_snr(enob) - margin_db


def sfdr_to_enob(sfdr_db: float) -> float:
    """Convert SFDR to equivalent ENOB.

    Useful for determining effective dynamic range in bits.

    Args:
        sfdr_db: Spurious-free dynamic range in dB

    Returns:
        Equivalent ENOB
    """
    return snr_to_enob(sfdr_db)


def adc_effective_snr(
    enob: float,
    sample_rate_hz: float,
    input_freq_hz: float | None = None,
    jitter_s_rms: float | None = None,
) -> dict[str, float]:
    """ADC SNR combining quantization and aperture-jitter noise.

    Quantization: SNR_q = 6.02*ENOB + 1.76 dB.
    Aperture jitter: SNR_j = -20*log10(2*pi*f_in*t_j), which dominates at
    high input frequency and wide bandwidth. Contributions add as noise
    powers.

    Args:
        enob: Effective number of bits (quantization-limited)
        sample_rate_hz: ADC sample rate in Hz
        input_freq_hz: Input frequency for jitter SNR; None uses fs/2
        jitter_s_rms: Aperture jitter in seconds RMS; None ignores jitter

    Returns:
        Dictionary with:
            - snr_quant_db: Quantization-limited SNR
            - snr_jitter_db: Jitter-limited SNR (inf if no jitter given)
            - snr_total_db: Combined SNR
            - enob_effective: ENOB implied by the combined SNR
    """
    snr_quant_db = enob_to_snr(enob)

    if jitter_s_rms is None or jitter_s_rms <= 0:
        snr_jitter_db = float("inf")
        snr_total_db = snr_quant_db
    else:
        f_in = input_freq_hz if input_freq_hz is not None else sample_rate_hz / 2
        snr_jitter_db = -20 * math.log10(2 * math.pi * f_in * jitter_s_rms)
        noise_linear = 10 ** (-snr_quant_db / 10) + 10 ** (-snr_jitter_db / 10)
        snr_total_db = -10 * math.log10(noise_linear)

    return {
        "snr_quant_db": snr_quant_db,
        "snr_jitter_db": snr_jitter_db,
        "snr_total_db": snr_total_db,
        "enob_effective": snr_to_enob(snr_total_db),
    }


def adc_power_w(
    enob: float,
    sample_rate_hz: float,
    fom_fj: float = 100.0,
) -> float:
    """ADC power from the Walden figure of merit.

    P = FOM * 2^ENOB * fs, with FOM in J per conversion step. Survey values
    range from ~10 fJ (state of the art) to a few hundred fJ.

    Args:
        enob: Effective number of bits
        sample_rate_hz: Sample rate in Hz
        fom_fj: Figure of merit in femtojoules per conversion step

    Returns:
        ADC power in Watts
    """
    return fom_fj * 1e-15 * 2**enob * sample_rate_hz


def quantization_noise_floor(
    enob: float,
    full_scale_dbm: float,
    bandwidth_hz: float,
    sample_rate_hz: float,
) -> float:
    """Calculate quantization noise floor in dBm/Hz.

    The quantization noise power is spread across the Nyquist bandwidth.
    Noise floor density = Full scale - SNR - 10*log10(fs/2)

    Args:
        enob: Effective number of bits
        full_scale_dbm: Full-scale input power in dBm
        bandwidth_hz: Signal bandwidth in Hz
        sample_rate_hz: Sample rate in Hz

    Returns:
        Noise floor spectral density in dBm/Hz
    """
    snr_db = enob_to_snr(enob)
    nyquist_bw = sample_rate_hz / 2
    noise_floor_dbm_hz = full_scale_dbm - snr_db - 10 * math.log10(nyquist_bw)
    return noise_floor_dbm_hz


def sample_rate_for_bandwidth(
    signal_bandwidth_hz: float,
    oversampling_ratio: float = 2.5,
) -> float:
    """Calculate minimum sample rate for a given signal bandwidth.

    Nyquist requires fs >= 2*BW, but practical systems use oversampling
    to ease anti-aliasing filter requirements.

    Args:
        signal_bandwidth_hz: Signal bandwidth in Hz
        oversampling_ratio: Ratio of sample rate to Nyquist rate
            - 2.0: Minimum (steep filter required)
            - 2.5: Typical (recommended)
            - 4.0: Relaxed filtering

    Returns:
        Required sample rate in Hz
    """
    return signal_bandwidth_hz * oversampling_ratio


def max_signal_bandwidth(
    sample_rate_hz: float,
    oversampling_ratio: float = 2.5,
) -> float:
    """Calculate maximum signal bandwidth for a given sample rate.

    Inverse of sample_rate_for_bandwidth.

    Args:
        sample_rate_hz: ADC/DAC sample rate in Hz
        oversampling_ratio: Ratio of sample rate to Nyquist rate

    Returns:
        Maximum signal bandwidth in Hz
    """
    return sample_rate_hz / oversampling_ratio


def adc_dynamic_range(
    enob: float,
    noise_figure_db: float = 0.0,
    input_noise_dbm_hz: float = -174.0,
    bandwidth_hz: float = 1.0,
) -> dict[str, float]:
    """Calculate ADC dynamic range metrics.

    Computes the usable dynamic range considering both quantization
    noise and thermal noise contributions.

    Args:
        enob: Effective number of bits
        noise_figure_db: Front-end noise figure in dB
        input_noise_dbm_hz: Input noise density (default: thermal at 290K)
        bandwidth_hz: Signal bandwidth for integrated noise

    Returns:
        Dictionary with:
            - snr_db: Quantization-limited SNR
            - noise_floor_dbm: Integrated noise floor
            - max_input_dbm: Maximum input before clipping
            - dynamic_range_db: Usable dynamic range
    """
    snr_db = enob_to_snr(enob)

    # Thermal noise floor
    thermal_noise_dbm = input_noise_dbm_hz + noise_figure_db + 10 * math.log10(bandwidth_hz)

    # Full scale (assume 0 dBm reference, adjust as needed)
    full_scale_dbm = 0.0

    # Quantization noise
    quant_noise_dbm = full_scale_dbm - snr_db

    # Total noise (power sum)
    total_noise_linear = 10 ** (thermal_noise_dbm / 10) + 10 ** (quant_noise_dbm / 10)
    total_noise_dbm = 10 * math.log10(total_noise_linear)

    dynamic_range_db = full_scale_dbm - total_noise_dbm

    return {
        "snr_db": snr_db,
        "noise_floor_dbm": total_noise_dbm,
        "max_input_dbm": full_scale_dbm,
        "dynamic_range_db": dynamic_range_db,
        "thermal_noise_dbm": thermal_noise_dbm,
        "quant_noise_dbm": quant_noise_dbm,
    }


def dac_output_power(
    enob: float,
    full_scale_dbm: float,
    backoff_db: float = 6.0,
) -> dict[str, float]:
    """Calculate DAC output power metrics.

    DACs typically operate with backoff from full scale to maintain
    linearity and avoid clipping on signal peaks.

    Args:
        enob: Effective number of bits
        full_scale_dbm: Full-scale output power in dBm
        backoff_db: Operating backoff from full scale

    Returns:
        Dictionary with:
            - full_scale_dbm: Maximum output power
            - operating_power_dbm: Power with backoff
            - snr_db: Signal-to-quantization-noise ratio
            - sfdr_db: Estimated spurious-free dynamic range
            - noise_floor_dbm: Quantization noise floor
    """
    snr_db = enob_to_snr(enob)
    sfdr_db = enob_to_sfdr(enob)
    operating_power_dbm = full_scale_dbm - backoff_db
    noise_floor_dbm = full_scale_dbm - snr_db

    return {
        "full_scale_dbm": full_scale_dbm,
        "operating_power_dbm": operating_power_dbm,
        "backoff_db": backoff_db,
        "snr_db": snr_db,
        "sfdr_db": sfdr_db,
        "noise_floor_dbm": noise_floor_dbm,
    }
