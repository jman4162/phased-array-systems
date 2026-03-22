"""Tests for digital beamformer model functions."""

import math

import pytest

from phased_array_systems.models.digital.bandwidth import (
    beam_bandwidth_product,
    beamformer_operations,
    channelizer_output_rate,
    digital_beamformer_data_rate,
    max_simultaneous_beams,
    processing_margin,
)
from phased_array_systems.models.digital.converters import (
    adc_dynamic_range,
    dac_output_power,
    enob_to_sfdr,
    enob_to_snr,
    max_signal_bandwidth,
    quantization_noise_floor,
    sample_rate_for_bandwidth,
    sfdr_to_enob,
    snr_to_enob,
)
from phased_array_systems.models.digital.scheduling import (
    Dwell,
    Function,
    Timeline,
    interleaved_timeline,
    max_update_rate,
    search_timeline,
    timeline_utilization,
)

# ======================== Converter Tests ========================


class TestENOBConversions:
    """Tests for ENOB <-> SNR/SFDR conversions."""

    def test_12bit_snr(self):
        """12-bit ENOB -> ~74 dB SNR."""
        snr = enob_to_snr(12.0)
        assert snr == pytest.approx(74.0, abs=0.1)

    def test_snr_to_enob_roundtrip(self):
        """SNR -> ENOB -> SNR should roundtrip."""
        original = 10.0
        recovered = enob_to_snr(snr_to_enob(enob_to_snr(original)))
        assert recovered == pytest.approx(enob_to_snr(original), rel=1e-6)

    def test_enob_to_sfdr_no_margin(self):
        """SFDR with no margin equals SNR."""
        snr = enob_to_snr(12.0)
        sfdr = enob_to_sfdr(12.0, margin_db=0.0)
        assert sfdr == pytest.approx(snr)

    def test_enob_to_sfdr_with_margin(self):
        """SFDR with margin is lower than SNR."""
        sfdr = enob_to_sfdr(12.0, margin_db=6.0)
        snr = enob_to_snr(12.0)
        assert sfdr == pytest.approx(snr - 6.0)

    def test_sfdr_to_enob(self):
        """sfdr_to_enob is inverse of enob_to_snr (approx)."""
        enob = sfdr_to_enob(enob_to_snr(10.0))
        assert enob == pytest.approx(10.0, rel=1e-6)


class TestSampleRate:
    """Tests for sample rate calculations."""

    def test_default_oversampling(self):
        """Default 2.5x oversampling."""
        fs = sample_rate_for_bandwidth(10e6)
        assert fs == pytest.approx(25e6)

    def test_max_bandwidth_inverse(self):
        """max_signal_bandwidth is inverse of sample_rate_for_bandwidth."""
        bw = max_signal_bandwidth(25e6, 2.5)
        assert bw == pytest.approx(10e6)

    def test_custom_oversampling(self):
        """Custom oversampling ratio."""
        fs = sample_rate_for_bandwidth(10e6, oversampling_ratio=4.0)
        assert fs == pytest.approx(40e6)


class TestQuantizationNoiseFloor:
    """Tests for quantization noise floor."""

    def test_noise_floor_decreases_with_enob(self):
        """Higher ENOB -> lower noise floor."""
        nf_10 = quantization_noise_floor(10.0, 0.0, 1e6, 25e6)
        nf_14 = quantization_noise_floor(14.0, 0.0, 1e6, 25e6)
        assert nf_14 < nf_10


class TestADCDynamicRange:
    """Tests for ADC dynamic range."""

    def test_dynamic_range_positive(self):
        """Dynamic range should be positive."""
        result = adc_dynamic_range(12.0, bandwidth_hz=10e6)
        assert result["dynamic_range_db"] > 0

    def test_higher_enob_more_range(self):
        """Higher ENOB -> more dynamic range."""
        dr_10 = adc_dynamic_range(10.0, bandwidth_hz=10e6)
        dr_14 = adc_dynamic_range(14.0, bandwidth_hz=10e6)
        assert dr_14["dynamic_range_db"] > dr_10["dynamic_range_db"]


class TestDACOutputPower:
    """Tests for DAC output power."""

    def test_backoff_reduces_power(self):
        """Operating power should be below full scale by backoff amount."""
        result = dac_output_power(12.0, full_scale_dbm=10.0, backoff_db=6.0)
        assert result["operating_power_dbm"] == pytest.approx(4.0)

    def test_snr_matches_enob(self):
        """SNR should match ENOB formula."""
        result = dac_output_power(12.0, full_scale_dbm=0.0)
        assert result["snr_db"] == pytest.approx(enob_to_snr(12.0))


# ======================== Bandwidth Tests ========================


class TestBeamBandwidthProduct:
    """Tests for beam-bandwidth product."""

    def test_single_beam(self):
        """Single beam: product equals bandwidth."""
        assert beam_bandwidth_product(1, 10e6) == pytest.approx(10e6)

    def test_multiple_beams(self):
        """Multiple beams scale linearly."""
        assert beam_bandwidth_product(4, 10e6) == pytest.approx(40e6)


class TestMaxSimultaneousBeams:
    """Tests for max beam count calculation."""

    def test_no_overhead(self):
        """Without overhead, max beams = processing_bw / beam_bw."""
        n = max_simultaneous_beams(100e6, 10e6, overhead_factor=1.0)
        assert n == 10

    def test_with_overhead(self):
        """Overhead reduces max beam count."""
        n = max_simultaneous_beams(100e6, 10e6, overhead_factor=1.1)
        assert n == 9  # 100/1.1 = 90.9, divided by 10 = 9


class TestDigitalBeamformerDataRate:
    """Tests for data rate calculations."""

    def test_data_rate_scales_with_elements(self):
        """More elements -> higher data rate."""
        rate_64 = digital_beamformer_data_rate(64, 25e6, 24)
        rate_256 = digital_beamformer_data_rate(256, 25e6, 24)
        assert rate_256["with_overhead_gbps"] > rate_64["with_overhead_gbps"]

    def test_per_element_rate(self):
        """Per-element rate should be independent of array size."""
        rate_64 = digital_beamformer_data_rate(64, 25e6, 24)
        rate_256 = digital_beamformer_data_rate(256, 25e6, 24)
        assert rate_64["per_element_gbps"] == pytest.approx(rate_256["per_element_gbps"], rel=1e-6)


class TestChannelizerOutputRate:
    """Tests for channelizer output rate."""

    def test_channel_bandwidth(self):
        """Channel BW = input BW / N channels."""
        result = channelizer_output_rate(100e6, 10)
        assert result["channel_bandwidth_hz"] == pytest.approx(10e6)

    def test_more_channels_same_total_rate(self):
        """Total output rate is roughly constant regardless of channelization."""
        result_10 = channelizer_output_rate(100e6, 10)
        result_100 = channelizer_output_rate(100e6, 100)
        # Both should have similar total output rate (same input BW)
        assert result_10["output_rate_gbps"] == pytest.approx(
            result_100["output_rate_gbps"], rel=0.01
        )


class TestProcessingMargin:
    """Tests for processing margin."""

    def test_sufficient_throughput(self):
        """Available > required -> positive margin."""
        result = processing_margin(100.0, 50.0)
        assert result["margin_ratio"] == pytest.approx(2.0)
        assert result["margin_db"] == pytest.approx(10 * math.log10(2.0))
        assert result["utilization_percent"] == pytest.approx(50.0)

    def test_exact_match(self):
        """Available == required -> 0 dB margin."""
        result = processing_margin(100.0, 100.0)
        assert result["margin_db"] == pytest.approx(0.0)
        assert result["utilization_percent"] == pytest.approx(100.0)


class TestBeamformerOperations:
    """Tests for beamformer compute estimation."""

    def test_time_domain(self):
        """Time-domain beamforming (fft_size=0)."""
        result = beamformer_operations(64, 1, 25e6, fft_size=0)
        assert result["method"] == "time_domain"
        assert result["total_gops"] > 0

    def test_frequency_domain(self):
        """Frequency-domain beamforming (fft_size>0)."""
        result = beamformer_operations(64, 1, 25e6, fft_size=256)
        assert result["method"] == "frequency_domain"
        assert result["total_gops"] > 0

    def test_more_beams_more_ops(self):
        """More beams -> more operations."""
        ops_1 = beamformer_operations(64, 1, 25e6)
        ops_4 = beamformer_operations(64, 4, 25e6)
        assert ops_4["total_gops"] > ops_1["total_gops"]


# ======================== Scheduling Tests ========================


class TestDwell:
    """Tests for Dwell dataclass."""

    def test_duration_conversions(self):
        """Duration unit conversions."""
        dwell = Dwell(function=Function.RADAR_SEARCH, duration_us=1000.0)
        assert dwell.duration_ms == pytest.approx(1.0)
        assert dwell.duration_s == pytest.approx(0.001)


class TestTimeline:
    """Tests for Timeline class."""

    def test_total_dwell_time(self):
        """Total dwell time is sum of durations."""
        dwells = [
            Dwell(function=Function.RADAR_SEARCH, duration_us=500.0),
            Dwell(function=Function.RADAR_TRACK, duration_us=300.0),
        ]
        tl = Timeline(dwells=dwells, frame_time_ms=1.0)
        assert tl.total_dwell_time_ms == pytest.approx(0.8)

    def test_dwells_by_function(self):
        """Filter dwells by function type."""
        dwells = [
            Dwell(function=Function.RADAR_SEARCH, duration_us=500.0),
            Dwell(function=Function.RADAR_TRACK, duration_us=300.0),
            Dwell(function=Function.RADAR_SEARCH, duration_us=500.0),
        ]
        tl = Timeline(dwells=dwells, frame_time_ms=2.0)
        search = tl.dwells_by_function(Function.RADAR_SEARCH)
        assert len(search) == 2

    def test_time_for_function(self):
        """Total time for a specific function."""
        dwells = [
            Dwell(function=Function.RADAR_SEARCH, duration_us=500.0),
            Dwell(function=Function.COMMS, duration_us=200.0),
            Dwell(function=Function.RADAR_SEARCH, duration_us=300.0),
        ]
        tl = Timeline(dwells=dwells, frame_time_ms=2.0)
        assert tl.time_for_function(Function.RADAR_SEARCH) == pytest.approx(0.8)


class TestTimelineUtilization:
    """Tests for timeline utilization analysis."""

    def test_full_utilization(self):
        """All time used -> 100% utilization."""
        dwells = [Dwell(function=Function.RADAR_SEARCH, duration_us=1000.0)]
        tl = Timeline(dwells=dwells, frame_time_ms=1.0)
        result = timeline_utilization(tl)
        assert result["total_utilization"] == pytest.approx(1.0)
        assert result["idle_time_ms"] == pytest.approx(0.0)

    def test_partial_utilization(self):
        """Half time used -> 50% utilization."""
        dwells = [Dwell(function=Function.RADAR_SEARCH, duration_us=500.0)]
        tl = Timeline(dwells=dwells, frame_time_ms=1.0)
        result = timeline_utilization(tl)
        assert result["total_utilization"] == pytest.approx(0.5)


class TestMaxUpdateRate:
    """Tests for volume update rate."""

    def test_update_rate_inversely_proportional(self):
        """Larger volume -> slower update rate."""
        rate_small = max_update_rate(0.1, 0.01, 100.0)
        rate_large = max_update_rate(1.0, 0.01, 100.0)
        assert rate_large["update_rate_hz"] < rate_small["update_rate_hz"]

    def test_beam_positions(self):
        """Number of beam positions = volume / beam angle."""
        result = max_update_rate(1.0, 0.01, 100.0)
        assert result["n_beam_positions"] == 100


class TestSearchTimeline:
    """Tests for search timeline generation."""

    def test_search_covers_volume(self):
        """Search should create dwells covering the scan volume."""
        tl = search_timeline(
            azimuth_range_deg=(-30.0, 30.0),
            elevation_range_deg=(0.0, 30.0),
            azimuth_step_deg=10.0,
            elevation_step_deg=10.0,
            dwell_time_us=100.0,
        )
        assert tl.n_dwells > 0
        # 7 az steps * 4 el steps = 28
        assert tl.n_dwells == 28


class TestInterleavedTimeline:
    """Tests for interleaved timeline generation."""

    def test_interleaved_creates_dwells(self):
        """Interleaved timeline should create dwells for each function."""
        functions = [
            {
                "function": Function.RADAR_SEARCH,
                "time_percent": 60,
                "dwell_time_us": 100.0,
                "priority": 2,
            },
            {
                "function": Function.COMMS,
                "time_percent": 30,
                "dwell_time_us": 200.0,
                "priority": 1,
            },
        ]
        tl = interleaved_timeline(functions, frame_time_ms=10.0)
        assert tl.n_dwells > 0
        search_dwells = tl.dwells_by_function(Function.RADAR_SEARCH)
        comms_dwells = tl.dwells_by_function(Function.COMMS)
        assert len(search_dwells) > 0
        assert len(comms_dwells) > 0
