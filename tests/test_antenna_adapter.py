"""Tests for the antenna adapter and metrics."""

import math

import numpy as np
import pytest

from phased_array_systems.architecture import Architecture, ArrayConfig, RFChainConfig
from phased_array_systems.models.antenna import (
    PhasedArrayAdapter,
    check_grating_lobes,
    compute_beamwidth,
    compute_scan_loss,
    compute_sidelobe_level,
)
from phased_array_systems.models.antenna.adapter import HAS_PAM
from phased_array_systems.models.antenna.metrics import (
    compute_array_gain,
    compute_directivity_rectangular,
)
from phased_array_systems.scenarios import CommsLinkScenario


class TestMetricFunctions:
    """Tests for metric extraction functions."""

    def test_compute_beamwidth_sinc(self):
        """Test beamwidth computation with a sinc-like pattern."""
        angles = np.linspace(-30, 30, 601)
        # Create a sinc-like pattern with normalized sinc
        # For sinc(x), the -3dB points are at x ≈ ±0.443
        # With angles in degrees and x = angles/scale, bw ≈ 0.886*scale degrees
        scale = 2.0  # degrees per unit x
        x = angles / scale
        pattern = np.sinc(x)  # sinc(x) = sin(pi*x)/(pi*x)
        pattern_db = 20 * np.log10(np.abs(pattern) + 1e-12)

        bw = compute_beamwidth(pattern_db, angles, -3.0)
        # Actual -3dB width of sinc is approximately 0.886 * 2 * scale = 1.77 degrees
        assert 1.0 < bw < 3.0

    def test_compute_sidelobe_level(self):
        """Test sidelobe level computation."""
        angles = np.linspace(-60, 60, 1201)
        x = np.radians(angles) * 10
        pattern = np.sinc(x / np.pi)
        pattern_db = 20 * np.log10(np.abs(pattern) + 1e-12)

        sll = compute_sidelobe_level(pattern_db, angles)
        # Sinc first sidelobe is about -13.2 dB
        assert -15.0 < sll < -12.0

    def test_compute_scan_loss_boresight(self):
        """Test scan loss at boresight (should be 0)."""
        loss = compute_scan_loss(0.0)
        assert loss == pytest.approx(0.0)

    def test_compute_scan_loss_45deg(self):
        """Test scan loss at 45 degrees."""
        loss = compute_scan_loss(45.0)
        # cos(45) = 0.707, 10*log10(0.707) ≈ -1.5 dB
        expected = -10 * math.log10(math.cos(math.radians(45)))
        assert loss == pytest.approx(expected, rel=0.01)

    def test_compute_scan_loss_60deg(self):
        """Test scan loss at 60 degrees."""
        loss = compute_scan_loss(60.0)
        # cos(60) = 0.5, 10*log10(0.5) ≈ -3 dB
        expected = -10 * math.log10(0.5)
        assert loss == pytest.approx(expected, rel=0.01)

    def test_compute_array_gain(self):
        """Test array gain computation."""
        # 64 elements with 0 dB element gain
        gain = compute_array_gain(64, 0.0)
        expected = 10 * math.log10(64)  # ~18.06 dB
        assert gain == pytest.approx(expected)

        # With element gain
        gain_with_elem = compute_array_gain(64, 5.0)
        assert gain_with_elem == pytest.approx(expected + 5.0)

    def test_compute_directivity_rectangular(self):
        """Test directivity computation for rectangular array."""
        # 8x8 array with half-wavelength spacing
        directivity = compute_directivity_rectangular(8, 8, 0.5, 0.5)
        # D ≈ 4*pi * (8*0.5) * (8*0.5) = 4*pi*16 = 201 ≈ 23 dB
        expected = 10 * math.log10(4 * math.pi * 16)
        assert directivity == pytest.approx(expected, rel=0.01)


class TestPhasedArrayAdapter:
    """Tests for the PhasedArrayAdapter class (analytical fallback)."""

    @pytest.fixture
    def sample_architecture(self):
        return Architecture(
            array=ArrayConfig(
                nx=8,
                ny=8,
                dx_lambda=0.5,
                dy_lambda=0.5,
                enforce_subarray_constraint=False,
            ),
            rf=RFChainConfig(tx_power_w_per_elem=1.0),
        )

    @pytest.fixture
    def sample_scenario(self):
        return CommsLinkScenario(
            freq_hz=10e9,  # 10 GHz
            bandwidth_hz=10e6,
            range_m=100e3,
            required_snr_db=10.0,
            scan_angle_deg=0.0,
        )

    def test_adapter_creation(self):
        """Test adapter can be created."""
        adapter = PhasedArrayAdapter(use_analytical_fallback=True)
        assert adapter.name == "antenna"

    def test_evaluate_boresight(self, sample_architecture, sample_scenario):
        """Test evaluation at boresight."""
        adapter = PhasedArrayAdapter(use_analytical_fallback=True)
        metrics = adapter.evaluate(sample_architecture, sample_scenario, {})

        assert "g_peak_db" in metrics
        assert "beamwidth_az_deg" in metrics
        assert "beamwidth_el_deg" in metrics
        assert "sll_db" in metrics
        assert "scan_loss_db" in metrics
        assert "n_elements" in metrics

        # Sanity checks
        assert metrics["g_peak_db"] > 15  # Should be significant gain
        assert metrics["scan_loss_db"] == pytest.approx(0.0)  # No scan loss at boresight
        assert metrics["n_elements"] == 64
        assert 0 < metrics["beamwidth_az_deg"] < 30
        assert 0 < metrics["beamwidth_el_deg"] < 30

    def test_evaluate_with_scan(self, sample_architecture):
        """Test evaluation with scan angle."""
        adapter = PhasedArrayAdapter(use_analytical_fallback=True)

        scenario = CommsLinkScenario(
            freq_hz=10e9,
            bandwidth_hz=10e6,
            range_m=100e3,
            required_snr_db=10.0,
            scan_angle_deg=45.0,
        )

        metrics = adapter.evaluate(sample_architecture, scenario, {})

        # Should have scan loss at 45 degrees
        assert metrics["scan_loss_db"] > 1.0
        # Peak gain should be reduced by scan loss
        assert metrics["g_peak_db"] < metrics["directivity_db"]

    def test_evaluate_different_array_sizes(self):
        """Test that larger arrays have higher gain."""
        adapter = PhasedArrayAdapter(use_analytical_fallback=True)

        scenario = CommsLinkScenario(
            freq_hz=10e9,
            bandwidth_hz=10e6,
            range_m=100e3,
            required_snr_db=10.0,
        )

        arch_small = Architecture(
            array=ArrayConfig(nx=4, ny=4, enforce_subarray_constraint=False),
            rf=RFChainConfig(tx_power_w_per_elem=1.0),
        )
        arch_large = Architecture(
            array=ArrayConfig(nx=16, ny=16, enforce_subarray_constraint=False),
            rf=RFChainConfig(tx_power_w_per_elem=1.0),
        )

        metrics_small = adapter.evaluate(arch_small, scenario, {})
        metrics_large = adapter.evaluate(arch_large, scenario, {})

        # Larger array should have higher gain
        assert metrics_large["g_peak_db"] > metrics_small["g_peak_db"]
        # Larger array should have narrower beamwidth
        assert metrics_large["beamwidth_az_deg"] < metrics_small["beamwidth_az_deg"]


@pytest.mark.skipif(not HAS_PAM, reason="phased_array library not installed")
class TestPhasedArrayAdapterWithLibrary:
    """Tests for the adapter using the actual phased_array library."""

    @pytest.fixture
    def adapter(self):
        return PhasedArrayAdapter(use_analytical_fallback=False)

    @pytest.fixture
    def scenario_10ghz(self):
        return CommsLinkScenario(
            freq_hz=10e9,
            bandwidth_hz=10e6,
            range_m=100e3,
            required_snr_db=10.0,
            scan_angle_deg=0.0,
        )

    def test_has_pam_is_true(self):
        """Verify the library is actually imported."""
        assert HAS_PAM is True

    def test_uniform_taper_sll_near_analytical(self, adapter, scenario_10ghz):
        """Uniform taper SLL should be near -13 dB (analytical baseline)."""
        arch = Architecture(
            array=ArrayConfig(
                nx=16,
                ny=16,
                dx_lambda=0.5,
                dy_lambda=0.5,
                taper_type="uniform",
                enforce_subarray_constraint=False,
            ),
            rf=RFChainConfig(tx_power_w_per_elem=1.0),
        )
        metrics = adapter.evaluate(arch, scenario_10ghz, {})

        # Uniform rectangular array SLL ~-13 dB (element pattern may shift slightly)
        assert -16.0 < metrics["sll_db"] < -11.0

    def test_taylor_taper_reduces_sll(self, adapter, scenario_10ghz):
        """Taylor taper should achieve lower SLL than uniform."""
        arch_uniform = Architecture(
            array=ArrayConfig(
                nx=16,
                ny=16,
                dx_lambda=0.5,
                dy_lambda=0.5,
                taper_type="uniform",
                enforce_subarray_constraint=False,
            ),
            rf=RFChainConfig(tx_power_w_per_elem=1.0),
        )
        arch_taylor = Architecture(
            array=ArrayConfig(
                nx=16,
                ny=16,
                dx_lambda=0.5,
                dy_lambda=0.5,
                taper_type="taylor",
                taper_sll_db=-30.0,
                enforce_subarray_constraint=False,
            ),
            rf=RFChainConfig(tx_power_w_per_elem=1.0),
        )

        m_uniform = adapter.evaluate(arch_uniform, scenario_10ghz, {})
        m_taylor = adapter.evaluate(arch_taylor, scenario_10ghz, {})

        # Taylor SLL should be lower (more negative) than uniform
        assert m_taylor["sll_db"] < m_uniform["sll_db"]

    def test_taper_efficiency_reported(self, adapter, scenario_10ghz):
        """Taper metrics should be included in output."""
        arch = Architecture(
            array=ArrayConfig(
                nx=8,
                ny=8,
                dx_lambda=0.5,
                dy_lambda=0.5,
                taper_type="hamming",
                enforce_subarray_constraint=False,
            ),
            rf=RFChainConfig(tx_power_w_per_elem=1.0),
        )
        metrics = adapter.evaluate(arch, scenario_10ghz, {})

        assert "taper_efficiency" in metrics
        assert "taper_loss_db" in metrics
        assert 0 < metrics["taper_efficiency"] <= 1.0
        assert metrics["taper_loss_db"] >= 0.0
        # Hamming has non-trivial taper loss
        assert metrics["taper_loss_db"] > 0.1

    def test_scan_angle_shifts_beam(self, adapter):
        """Verify that scanning changes the pattern."""
        arch = Architecture(
            array=ArrayConfig(
                nx=16,
                ny=16,
                dx_lambda=0.5,
                dy_lambda=0.5,
                enforce_subarray_constraint=False,
            ),
            rf=RFChainConfig(tx_power_w_per_elem=1.0),
        )

        scenario_boresight = CommsLinkScenario(
            freq_hz=10e9,
            bandwidth_hz=10e6,
            range_m=100e3,
            required_snr_db=10.0,
            scan_angle_deg=0.0,
        )
        scenario_scanned = CommsLinkScenario(
            freq_hz=10e9,
            bandwidth_hz=10e6,
            range_m=100e3,
            required_snr_db=10.0,
            scan_angle_deg=30.0,
        )

        m_bore = adapter.evaluate(arch, scenario_boresight, {})
        m_scan = adapter.evaluate(arch, scenario_scanned, {})

        # Scanned beam should have reduced gain due to scan loss
        assert m_scan["g_peak_db"] < m_bore["g_peak_db"]
        assert m_scan["scan_loss_db"] > 0

    def test_default_taper_type_is_uniform(self, adapter, scenario_10ghz):
        """Config without taper_type should default to uniform."""
        arch = Architecture(
            array=ArrayConfig(
                nx=8,
                ny=8,
                dx_lambda=0.5,
                dy_lambda=0.5,
                enforce_subarray_constraint=False,
            ),
            rf=RFChainConfig(tx_power_w_per_elem=1.0),
        )
        metrics = adapter.evaluate(arch, scenario_10ghz, {})
        assert metrics["taper_type"] == "uniform"
        assert metrics["taper_efficiency"] == pytest.approx(1.0)

    def test_element_pattern_applied(self, adapter, scenario_10ghz):
        """Element pattern should be applied and flagged."""
        arch = Architecture(
            array=ArrayConfig(
                nx=8,
                ny=8,
                dx_lambda=0.5,
                dy_lambda=0.5,
                enforce_subarray_constraint=False,
            ),
            rf=RFChainConfig(tx_power_w_per_elem=1.0),
        )
        metrics = adapter.evaluate(arch, scenario_10ghz, {})
        assert metrics["element_pattern_applied"] is True
        assert metrics["element_cos_exp"] == 1.5

    def test_grating_lobe_safe_spacing(self, adapter, scenario_10ghz):
        """dx=0.5 at scan_limit=60 deg should be grating-safe."""
        arch = Architecture(
            array=ArrayConfig(
                nx=8,
                ny=8,
                dx_lambda=0.5,
                dy_lambda=0.5,
                scan_limit_deg=60.0,
                enforce_subarray_constraint=False,
            ),
            rf=RFChainConfig(tx_power_w_per_elem=1.0),
        )
        metrics = adapter.evaluate(arch, scenario_10ghz, {})
        assert metrics["grating_lobe_risk"] is False

    def test_grating_lobe_risky_spacing(self, adapter, scenario_10ghz):
        """dx=0.8 at scan_limit=60 deg should flag grating risk."""
        arch = Architecture(
            array=ArrayConfig(
                nx=8,
                ny=8,
                dx_lambda=0.8,
                dy_lambda=0.8,
                scan_limit_deg=60.0,
                enforce_subarray_constraint=False,
            ),
            rf=RFChainConfig(tx_power_w_per_elem=1.0),
        )
        metrics = adapter.evaluate(arch, scenario_10ghz, {})
        assert metrics["grating_lobe_risk"] is True


@pytest.mark.skipif(not HAS_PAM, reason="phased_array library not installed")
class TestImpairments:
    """Tests for the impairments pipeline (phase quantization + element failures)."""

    @pytest.fixture
    def adapter(self):
        return PhasedArrayAdapter(use_analytical_fallback=False)

    @pytest.fixture
    def scenario(self):
        return CommsLinkScenario(
            freq_hz=10e9,
            bandwidth_hz=10e6,
            range_m=100e3,
            required_snr_db=10.0,
            scan_angle_deg=0.0,
        )

    def test_phase_quantization_degrades_sll(self, adapter):
        """2-bit quantization at non-trivial scan should degrade SLL vs. ideal."""
        # Use scan_angle=15 deg to avoid phase-grid alignment at common angles
        scenario_scan = CommsLinkScenario(
            freq_hz=10e9,
            bandwidth_hz=10e6,
            range_m=100e3,
            required_snr_db=10.0,
            scan_angle_deg=15.0,
        )
        arch_ideal = Architecture(
            array=ArrayConfig(
                nx=16,
                ny=16,
                dx_lambda=0.5,
                dy_lambda=0.5,
                taper_type="taylor",
                taper_sll_db=-30.0,
                phase_bits=None,
                enforce_subarray_constraint=False,
            ),
            rf=RFChainConfig(tx_power_w_per_elem=1.0),
        )
        arch_2bit = Architecture(
            array=ArrayConfig(
                nx=16,
                ny=16,
                dx_lambda=0.5,
                dy_lambda=0.5,
                taper_type="taylor",
                taper_sll_db=-30.0,
                phase_bits=2,
                enforce_subarray_constraint=False,
            ),
            rf=RFChainConfig(tx_power_w_per_elem=1.0),
        )

        m_ideal = adapter.evaluate(arch_ideal, scenario_scan, {})
        m_2bit = adapter.evaluate(arch_2bit, scenario_scan, {})

        # 2-bit quantization should raise SLL (less negative = worse)
        assert m_2bit["sll_db"] > m_ideal["sll_db"]
        assert "phase_quantization_bits" in m_2bit
        assert m_2bit["phase_quantization_bits"] == 2

    def test_element_failures_reduce_gain(self, adapter, scenario):
        """5% failure rate should reduce gain."""
        arch = Architecture(
            array=ArrayConfig(
                nx=16,
                ny=16,
                dx_lambda=0.5,
                dy_lambda=0.5,
                enforce_subarray_constraint=False,
            ),
            rf=RFChainConfig(tx_power_w_per_elem=1.0),
        )

        m_healthy = adapter.evaluate(arch, scenario, {})
        m_failed = adapter.evaluate(arch, scenario, {"failure_rate": 0.05, "meta.seed": 42})

        # Failed array should have lower gain
        assert m_failed["g_peak_db"] <= m_healthy["g_peak_db"]
        assert m_failed["n_failed_elements"] > 0

    def test_no_impairments_by_default(self, adapter, scenario):
        """Default config should have no impairments applied."""
        arch = Architecture(
            array=ArrayConfig(
                nx=8,
                ny=8,
                dx_lambda=0.5,
                dy_lambda=0.5,
                enforce_subarray_constraint=False,
            ),
            rf=RFChainConfig(tx_power_w_per_elem=1.0),
        )
        metrics = adapter.evaluate(arch, scenario, {})

        assert "phase_quantization_bits" not in metrics
        assert "n_failed_elements" not in metrics


class TestGratingLobes:
    """Tests for grating lobe detection."""

    def test_half_wavelength_60deg_safe(self):
        """dx=0.5 lambda at 60 deg scan limit is safe."""
        result = check_grating_lobes(0.5, 0.5, 60.0)
        assert result["grating_lobe_risk"] is False

    def test_wide_spacing_risky(self):
        """dx=0.8 lambda at 60 deg scan limit is risky."""
        result = check_grating_lobes(0.8, 0.8, 60.0)
        assert result["grating_lobe_risk"] is True

    def test_max_safe_spacing_value(self):
        """Verify max safe spacing calculation."""
        # At 0 deg scan, max safe = 1/(1+0) = 1.0
        result = check_grating_lobes(0.5, 0.5, 0.0)
        assert result["max_safe_spacing_lambda"] == pytest.approx(1.0)

        # At 30 deg scan, max safe = 1/(1+0.5) = 0.667
        result = check_grating_lobes(0.5, 0.5, 30.0)
        assert result["max_safe_spacing_lambda"] == pytest.approx(2.0 / 3.0, rel=0.01)

    def test_asymmetric_spacing(self):
        """Only one axis needs to exceed limit for risk."""
        result = check_grating_lobes(0.5, 0.9, 60.0)
        assert result["grating_lobe_risk"] is True
