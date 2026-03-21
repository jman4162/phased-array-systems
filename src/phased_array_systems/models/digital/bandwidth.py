"""Bandwidth and throughput models for digital beamforming.

This module provides functions for analyzing digital beamformer
bandwidth constraints, beam-bandwidth products, and data rates.

Key Concepts:
    - Beam-Bandwidth Product: Total processing BW = N_beams * BW_per_beam
    - Digital Beamformer Data Rate: Scales with elements * sample rate * bits
    - Processing Margin: Ratio of available to required throughput

References:
    - Brookner, E. "Phased Array Radars: Past, Present, and Future"
    - Skolnik, M. "Radar Handbook", 3rd Edition, Chapter 13
"""

from __future__ import annotations

import math


def beam_bandwidth_product(
    n_beams: int,
    bandwidth_per_beam_hz: float,
) -> float:
    """Calculate total beam-bandwidth product.

    The beam-bandwidth product represents the total instantaneous
    processing bandwidth required for simultaneous beams.

    Args:
        n_beams: Number of simultaneous beams
        bandwidth_per_beam_hz: Bandwidth per beam in Hz

    Returns:
        Total beam-bandwidth product in Hz
    """
    return n_beams * bandwidth_per_beam_hz


def max_simultaneous_beams(
    processing_bandwidth_hz: float,
    bandwidth_per_beam_hz: float,
    overhead_factor: float = 1.1,
) -> int:
    """Calculate maximum number of simultaneous beams.

    Given a fixed processing bandwidth, determine how many beams
    can be formed simultaneously.

    Args:
        processing_bandwidth_hz: Total available processing bandwidth
        bandwidth_per_beam_hz: Required bandwidth per beam
        overhead_factor: Processing overhead (default 10%)

    Returns:
        Maximum number of simultaneous beams (integer)
    """
    effective_bw = processing_bandwidth_hz / overhead_factor
    return int(effective_bw / bandwidth_per_beam_hz)


def digital_beamformer_data_rate(
    n_elements: int,
    sample_rate_hz: float,
    bits_per_sample: int,
    n_channels: int = 2,  # I and Q
    overhead_factor: float = 1.25,
) -> dict[str, float]:
    """Calculate digital beamformer input data rate.

    Computes the raw data rate from ADCs into the digital beamformer.

    Args:
        n_elements: Number of array elements (each with ADC)
        sample_rate_hz: ADC sample rate in Hz
        bits_per_sample: Bits per sample (typically 12-16)
        n_channels: Number of channels per element (2 for I/Q)
        overhead_factor: Protocol overhead (framing, sync, etc.)

    Returns:
        Dictionary with:
            - raw_rate_bps: Raw data rate in bits/second
            - raw_rate_gbps: Raw data rate in Gbps
            - with_overhead_gbps: Rate including overhead
            - per_element_gbps: Rate per element
    """
    raw_rate_bps = n_elements * sample_rate_hz * bits_per_sample * n_channels
    raw_rate_gbps = raw_rate_bps / 1e9
    with_overhead_gbps = raw_rate_gbps * overhead_factor
    per_element_gbps = with_overhead_gbps / n_elements

    return {
        "raw_rate_bps": raw_rate_bps,
        "raw_rate_gbps": raw_rate_gbps,
        "with_overhead_gbps": with_overhead_gbps,
        "per_element_gbps": per_element_gbps,
        "n_elements": n_elements,
        "sample_rate_hz": sample_rate_hz,
        "bits_per_sample": bits_per_sample,
    }


def channelizer_output_rate(
    input_bandwidth_hz: float,
    n_channels: int,
    overlap_factor: float = 1.0,
    bits_per_output: int = 32,  # Complex float
) -> dict[str, float]:
    """Calculate polyphase channelizer output data rate.

    A channelizer divides a wideband input into narrowband channels.
    Output rate depends on channel count and overlap.

    Args:
        input_bandwidth_hz: Total input bandwidth
        n_channels: Number of output channels
        overlap_factor: Channel overlap (1.0 = no overlap, 2.0 = 50% overlap)
        bits_per_output: Bits per output sample (32 for complex float)

    Returns:
        Dictionary with:
            - channel_bandwidth_hz: Bandwidth per channel
            - channel_sample_rate_hz: Sample rate per channel
            - output_rate_gbps: Total output data rate
            - samples_per_channel_per_sec: Output samples per channel
    """
    channel_bandwidth_hz = input_bandwidth_hz / n_channels
    channel_sample_rate_hz = channel_bandwidth_hz * overlap_factor

    total_output_samples = n_channels * channel_sample_rate_hz
    output_rate_bps = total_output_samples * bits_per_output * 2  # Complex
    output_rate_gbps = output_rate_bps / 1e9

    return {
        "channel_bandwidth_hz": channel_bandwidth_hz,
        "channel_sample_rate_hz": channel_sample_rate_hz,
        "output_rate_gbps": output_rate_gbps,
        "samples_per_channel_per_sec": channel_sample_rate_hz,
        "n_channels": n_channels,
        "input_bandwidth_hz": input_bandwidth_hz,
    }


def processing_margin(
    available_throughput_gops: float,
    required_throughput_gops: float,
) -> dict[str, float]:
    """Calculate processing margin for digital beamformer.

    Compares available FPGA/GPU throughput against requirements.

    Args:
        available_throughput_gops: Available processing (Giga-ops/sec)
        required_throughput_gops: Required processing (Giga-ops/sec)

    Returns:
        Dictionary with:
            - margin_ratio: Available / Required (>1 is good)
            - margin_db: Margin in dB
            - utilization_percent: Percentage of capacity used
            - headroom_percent: Remaining capacity
    """
    margin_ratio = available_throughput_gops / required_throughput_gops
    margin_db = 10 * math.log10(margin_ratio) if margin_ratio > 0 else float("-inf")
    utilization_percent = (required_throughput_gops / available_throughput_gops) * 100
    headroom_percent = 100 - utilization_percent

    return {
        "margin_ratio": margin_ratio,
        "margin_db": margin_db,
        "utilization_percent": utilization_percent,
        "headroom_percent": headroom_percent,
        "available_gops": available_throughput_gops,
        "required_gops": required_throughput_gops,
    }


def beamformer_operations(
    n_elements: int,
    n_beams: int,
    sample_rate_hz: float,
    fft_size: int = 0,
) -> dict[str, float]:
    """Estimate digital beamformer computational requirements.

    Calculates operations per second for time-domain or frequency-domain
    beamforming.

    Args:
        n_elements: Number of array elements
        n_beams: Number of simultaneous beams
        sample_rate_hz: Sample rate in Hz
        fft_size: FFT size (0 for time-domain beamforming)

    Returns:
        Dictionary with:
            - complex_mults_per_sec: Complex multiplications/sec
            - complex_adds_per_sec: Complex additions/sec
            - total_gops: Total Giga-operations/sec
            - method: 'time_domain' or 'frequency_domain'
    """
    if fft_size > 0:
        # Frequency-domain: FFT + multiply + IFFT
        # FFT ops ≈ 5 * N * log2(N) per transform
        fft_ops = 5 * fft_size * math.log2(fft_size)
        transforms_per_sec = sample_rate_hz / fft_size

        # Per beam: FFT(input) + N_elem multiplies + IFFT(output)
        fft_total_ops = transforms_per_sec * fft_ops * n_elements  # Input FFTs
        mult_ops = transforms_per_sec * fft_size * n_elements * n_beams
        ifft_ops = transforms_per_sec * fft_ops * n_beams  # Output IFFTs

        total_ops = fft_total_ops + mult_ops + ifft_ops
        method = "frequency_domain"
    else:
        # Time-domain: weight and sum per sample
        # Each beam: N_elements complex multiplies + (N_elements-1) adds
        mults_per_sample = n_elements * n_beams
        adds_per_sample = (n_elements - 1) * n_beams

        complex_mults_per_sec = mults_per_sample * sample_rate_hz
        complex_adds_per_sec = adds_per_sample * sample_rate_hz

        # Complex mult ≈ 6 real ops, complex add ≈ 2 real ops
        total_ops = complex_mults_per_sec * 6 + complex_adds_per_sec * 2
        method = "time_domain"

    total_gops = total_ops / 1e9

    return {
        "total_gops": total_gops,
        "total_ops_per_sec": total_ops,
        "method": method,
        "n_elements": n_elements,
        "n_beams": n_beams,
        "sample_rate_hz": sample_rate_hz,
    }
