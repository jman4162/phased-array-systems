"""Adapter wrapping phased-array-modeling for consistent metric extraction."""

import logging
from typing import Any, cast

import numpy as np

from phased_array_systems.architecture import Architecture
from phased_array_systems.models.antenna.errors import (
    phase_quantization_loss_db,
    phase_quantization_rms_rad,
    rms_sidelobe_floor_db,
)
from phased_array_systems.models.antenna.metrics import (
    compute_beamwidth,
    compute_directivity_rectangular,
    compute_scan_loss,
    compute_sidelobe_level,
)
from phased_array_systems.models.antenna.taper import (
    TaperType,
    generate_taper_weights,
)
from phased_array_systems.models.antenna.taper import (
    compute_taper_efficiency as _local_taper_efficiency,
)
from phased_array_systems.types import MetricsDict, Scenario

logger = logging.getLogger(__name__)

# Try to import phased-array-modeling (actual package name: phased_array)
try:
    from phased_array import (
        chebyshev_taper_2d,
        compute_taper_efficiency,
        cosine_taper_2d,
        create_rectangular_array,
        element_pattern,
        gaussian_taper_2d,
        hamming_taper_2d,
        quantize_phase,
        simulate_element_failures,
        steering_vector,
        taylor_taper_2d,
        total_pattern,
    )

    HAS_PAM = True
except ImportError:
    HAS_PAM = False


def _build_taper_weights(taper_type: str, nx: int, ny: int, sll_db: float) -> np.ndarray:
    """Build 2D taper weights array.

    Args:
        taper_type: Taper type name
        nx: Number of elements in x
        ny: Number of elements in y
        sll_db: Target sidelobe level (dB, negative) for taylor/chebyshev

    Returns:
        1D array of taper weights (length nx*ny)
    """
    if taper_type == "uniform":
        return np.ones(nx * ny)
    elif taper_type == "taylor":
        return np.asarray(taylor_taper_2d(nx, ny, sidelobe_dB=sll_db)).ravel()
    elif taper_type == "chebyshev":
        return np.asarray(chebyshev_taper_2d(nx, ny, sidelobe_dB=sll_db)).ravel()
    elif taper_type == "hamming":
        return np.asarray(hamming_taper_2d(nx, ny)).ravel()
    elif taper_type == "cosine":
        return np.asarray(cosine_taper_2d(nx, ny)).ravel()
    elif taper_type == "gaussian":
        return np.asarray(gaussian_taper_2d(nx, ny)).ravel()
    else:
        logger.warning("Unknown taper type '%s', using uniform", taper_type)
        return np.ones(nx * ny)


class PhasedArrayAdapter:
    """Adapter for phased-array-modeling library.

    Provides a consistent interface for computing antenna pattern metrics
    using the phased-array-modeling library, with fallback to analytical
    approximations when the library is not available.

    Attributes:
        name: Model block name for identification
        use_analytical_fallback: If True, use analytical approximations
            when phased-array-modeling is not available
    """

    name: str = "antenna"

    def __init__(self, use_analytical_fallback: bool = True):
        """Initialize the adapter.

        Args:
            use_analytical_fallback: Use analytical methods if PAM unavailable
        """
        self.use_analytical_fallback = use_analytical_fallback

        if not HAS_PAM and not use_analytical_fallback:
            raise ImportError(
                "phased-array-modeling not installed. Install with: "
                "pip install phased-array-modeling"
            )

    def evaluate(
        self, arch: Architecture, scenario: Scenario, context: dict[str, Any]
    ) -> MetricsDict:
        """Evaluate antenna performance metrics.

        Args:
            arch: Architecture configuration
            scenario: Scenario with frequency and scan angle info
            context: Additional context (may contain failure_rate for degradation)

        Returns:
            Dictionary with antenna metrics
        """
        scan_angle_deg = getattr(scenario, "scan_angle_deg", 0.0)

        if HAS_PAM:
            return self._evaluate_with_pam(arch, scenario, scan_angle_deg, context)
        else:
            return self._evaluate_analytical(arch, scenario, scan_angle_deg)

    def _evaluate_with_pam(
        self,
        arch: Architecture,
        scenario: Scenario,
        scan_angle_deg: float,
        context: dict[str, Any],
    ) -> MetricsDict:
        """Evaluate using phased-array-modeling library."""
        wavelength_m = scenario.wavelength_m if hasattr(scenario, "wavelength_m") else None

        if wavelength_m is None:
            from phased_array_systems.constants import C

            wavelength_m = C / scenario.freq_hz

        nx = arch.array.nx
        ny = arch.array.ny

        # 1. Create array geometry (dx/dy are in wavelengths, library converts to meters)
        geom = create_rectangular_array(
            nx, ny, arch.array.dx_lambda, arch.array.dy_lambda, wavelength=wavelength_m
        )
        k = 2 * np.pi / wavelength_m

        # 2. Build taper weights
        taper_type = getattr(arch.array, "taper_type", "uniform")
        taper_sll_db = getattr(arch.array, "taper_sll_db", -30.0)
        taper_weights = _build_taper_weights(taper_type, nx, ny, taper_sll_db)

        # Compute taper efficiency
        taper_eff = compute_taper_efficiency(taper_weights)
        taper_loss_db = -10 * np.log10(taper_eff) if taper_eff > 0 else 0.0

        # 3. Apply steering vector
        scan_phi_deg = 0.0  # Azimuth plane scan
        sv = steering_vector(k, geom.x, geom.y, scan_angle_deg, scan_phi_deg)
        weights = taper_weights * sv

        # 4. Apply impairments pipeline
        phase_bits = getattr(arch.array, "phase_bits", None)
        quantization_applied = False
        if phase_bits is not None:
            weights = quantize_phase(weights, n_bits=phase_bits)
            quantization_applied = True

        failure_rate = context.get("failure_rate", 0.0)
        n_failed = 0
        if failure_rate > 0:
            seed = context.get("meta.seed")
            weights, fail_mask = simulate_element_failures(weights, failure_rate, seed=seed)
            # The library's mask is True for FAILED elements; counting the
            # zeros counted the survivors (251 "failures" out of 256 at a 2%
            # rate).
            n_failed = int(np.sum(fail_mask))

        # 5. Compute patterns using total_pattern (includes element pattern)
        theta_deg = np.linspace(-90, 90, 721)
        theta_rad = np.radians(theta_deg)

        element_cos_exp = getattr(arch.array, "element_cos_exp", 1.5)

        # Azimuth cut (phi=0)
        phi_az = np.zeros_like(theta_rad)
        tp_az = total_pattern(
            theta_rad,
            phi_az,
            geom.x,
            geom.y,
            weights,
            k,
            element_pattern_func=element_pattern,
            cos_exp_theta=element_cos_exp,
        )
        tp_az_db = 20 * np.log10(np.abs(tp_az) + 1e-12)
        tp_az_db = tp_az_db - np.max(tp_az_db)  # Normalize to peak

        # Elevation cut (phi=90)
        phi_el = np.full_like(theta_rad, np.pi / 2)
        tp_el = total_pattern(
            theta_rad,
            phi_el,
            geom.x,
            geom.y,
            weights,
            k,
            element_pattern_func=element_pattern,
            cos_exp_theta=element_cos_exp,
        )
        tp_el_db = 20 * np.log10(np.abs(tp_el) + 1e-12)
        tp_el_db = tp_el_db - np.max(tp_el_db)

        # 6. Extract metrics from computed patterns
        beamwidth_az = compute_beamwidth(tp_az_db, theta_deg)
        beamwidth_el = compute_beamwidth(tp_el_db, theta_deg)
        sll = compute_sidelobe_level(tp_az_db, theta_deg)
        scan_loss = compute_scan_loss(scan_angle_deg)
        directivity = compute_directivity_rectangular(
            nx, ny, arch.array.dx_lambda, arch.array.dy_lambda
        )
        # Quantization is simulated in the pattern, but g_peak is assembled
        # analytically, so the quantization gain loss must be subtracted here
        quant_loss_db = phase_quantization_loss_db(phase_bits) if phase_bits else 0.0
        g_peak = directivity - scan_loss - taper_loss_db - quant_loss_db

        # 7. Grating lobe check
        from phased_array_systems.models.antenna.grating import check_grating_lobes

        grating_info = check_grating_lobes(
            arch.array.dx_lambda, arch.array.dy_lambda, arch.array.scan_limit_deg
        )
        if grating_info["grating_lobe_risk"]:
            logger.warning(
                "Grating lobe risk detected: dx=%.2f, dy=%.2f lambda, "
                "max safe spacing=%.3f lambda at scan_limit=%.1f deg",
                arch.array.dx_lambda,
                arch.array.dy_lambda,
                grating_info["max_safe_spacing_lambda"],
                arch.array.scan_limit_deg,
            )

        metrics: MetricsDict = {
            "g_peak_db": g_peak,
            "beamwidth_az_deg": beamwidth_az,
            "beamwidth_el_deg": beamwidth_el,
            "sll_db": sll,
            "scan_loss_db": scan_loss,
            "directivity_db": directivity,
            "n_elements": arch.array.n_elements,
            "taper_type": taper_type,
            "taper_efficiency": taper_eff,
            "taper_loss_db": taper_loss_db,
            "element_pattern_applied": True,
            "element_cos_exp": element_cos_exp,
            "grating_lobe_risk": grating_info["grating_lobe_risk"],
            "max_safe_spacing_lambda": grating_info["max_safe_spacing_lambda"],
        }

        if quantization_applied and phase_bits is not None:
            metrics["phase_quantization_bits"] = phase_bits
            metrics["phase_quantization_loss_db"] = quant_loss_db
            metrics["rms_sidelobe_floor_db"] = rms_sidelobe_floor_db(
                phase_quantization_rms_rad(phase_bits) ** 2,
                arch.array.n_elements,
                taper_eff,
            )

        if failure_rate > 0:
            metrics["n_failed_elements"] = n_failed
            metrics["failure_rate"] = failure_rate

        return metrics

    # Approximate first-sidelobe design levels for fixed-shape windows
    # (uniform: sinc theory; hamming/cosine/gaussian: window first SLL)
    _DESIGN_SLL_DB = {
        "uniform": -13.2,
        "hamming": -42.7,
        "cosine": -23.0,
        "gaussian": -55.0,
    }

    def _evaluate_analytical(
        self, arch: Architecture, scenario: Scenario, scan_angle_deg: float
    ) -> MetricsDict:
        """Evaluate using analytical approximations.

        Uses standard phased array formulas when the full simulation
        library is not available. Emits the same metric key set as the
        pattern-based path so downstream models and requirements behave
        identically in both modes.
        """
        nx, ny = arch.array.nx, arch.array.ny

        # Taper from real window functions (separable 2-D outer product)
        taper_type = cast(TaperType, getattr(arch.array, "taper_type", "uniform"))
        taper_sll_db = getattr(arch.array, "taper_sll_db", -30.0)
        wx = generate_taper_weights(taper_type, nx, taper_sll_db)
        wy = generate_taper_weights(taper_type, ny, taper_sll_db)
        weights_2d = np.outer(wx, wy).ravel()
        taper_eff = _local_taper_efficiency(weights_2d)
        taper_loss_db = -10 * np.log10(taper_eff) if taper_eff > 0 else 0.0

        # Directivity from aperture size
        directivity_db = compute_directivity_rectangular(
            nx, ny, arch.array.dx_lambda, arch.array.dy_lambda
        )

        # Scan loss
        scan_loss = compute_scan_loss(scan_angle_deg)

        # Phase-shifter quantization loss (analytic Ruze form)
        phase_bits = getattr(arch.array, "phase_bits", None)
        quant_loss_db = phase_quantization_loss_db(phase_bits) if phase_bits else 0.0

        # Peak gain
        g_peak = directivity_db - scan_loss - taper_loss_db - quant_loss_db

        # Beamwidth approximations for a rectangular array
        # BW ≈ 0.886 / (N * d_lambda) radians (uniform-taper form; tapers
        # broaden this slightly, not modeled here)
        beamwidth_az_deg = np.degrees(0.886 / (nx * arch.array.dx_lambda))
        beamwidth_el_deg = np.degrees(0.886 / (ny * arch.array.dy_lambda))

        # Sidelobe level: taper design SLL, floored by the RMS error
        # sidelobe floor when quantization is present
        if taper_type in ("taylor", "chebyshev"):
            design_sll = taper_sll_db
        else:
            design_sll = self._DESIGN_SLL_DB.get(taper_type, -13.2)
        if phase_bits:
            error_floor = rms_sidelobe_floor_db(
                phase_quantization_rms_rad(phase_bits) ** 2,
                arch.array.n_elements,
                taper_eff,
            )
            sll_db = max(design_sll, error_floor)
        else:
            sll_db = design_sll

        # Grating lobe check (same as the pattern-based path)
        from phased_array_systems.models.antenna.grating import check_grating_lobes

        grating_info = check_grating_lobes(
            arch.array.dx_lambda, arch.array.dy_lambda, arch.array.scan_limit_deg
        )

        metrics: MetricsDict = {
            "g_peak_db": g_peak,
            "beamwidth_az_deg": beamwidth_az_deg,
            "beamwidth_el_deg": beamwidth_el_deg,
            "sll_db": sll_db,
            "scan_loss_db": scan_loss,
            "directivity_db": directivity_db,
            "n_elements": arch.array.n_elements,
            "taper_type": taper_type,
            "taper_efficiency": taper_eff,
            "taper_loss_db": taper_loss_db,
            "element_pattern_applied": False,
            "element_cos_exp": getattr(arch.array, "element_cos_exp", 1.5),
            "grating_lobe_risk": grating_info["grating_lobe_risk"],
            "max_safe_spacing_lambda": grating_info["max_safe_spacing_lambda"],
        }

        if phase_bits:
            metrics["phase_quantization_bits"] = phase_bits
            metrics["phase_quantization_loss_db"] = quant_loss_db
            metrics["rms_sidelobe_floor_db"] = rms_sidelobe_floor_db(
                phase_quantization_rms_rad(phase_bits) ** 2,
                arch.array.n_elements,
                taper_eff,
            )

        return metrics
