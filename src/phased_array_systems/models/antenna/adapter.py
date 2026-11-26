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

    Beamwidth convention
    --------------------
    ``beamwidth_az_deg`` and ``beamwidth_el_deg`` are the half-power widths in
    each principal plane **at the scenario's scan angle**. The scan is in the
    azimuth plane (``scan_phi_deg = 0``), so azimuth carries the 1/cos(phi)
    broadening of Curry Eq. (8.9) and elevation does not. Both paths emit them
    on this convention, and no consumer should broaden them again -- doing so
    squared the factor for every track metric until v0.15.0, and did it only
    when the pattern backend happened to be installed.

    ``beamwidth_{az,el}_broadside_deg`` are the same widths at broadside. Use
    these wherever a *scan-invariant* footprint is wanted -- tiling a search
    volume, for instance, where the beam sweeps the whole sector and pinning
    the footprint to one scan angle biases the beam count badly (44% low at 60
    degrees). Use the scanned widths for anything that looks in one direction:
    measurement accuracy, and the clutter resolution cell.

    The two paths are not interchangeable to better than about 25% on a tapered
    array: the analytical branch uses the uniform-illumination 0.886/(N d) form
    and does not model taper broadening, which the pattern path measures.

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

        # Elevation cut, taken through the steered beam rather than through
        # broadside. Holding u = sin(theta_s) fixed and sweeping
        # v = sin(psi) traces the elevation principal plane of the *steered*
        # beam; at broadside it reduces exactly to the phi = 90 cut.
        #
        # The phi = 90 cut it replaces was measuring the wrong thing at every
        # nonzero scan angle, because it passes through broadside while the
        # beam is elsewhere: at a 30 degree scan its peak amplitude is 5.8e-13,
        # under the 1e-12 floor added below, so compute_beamwidth saw a flat
        # pattern and returned NaN; at 60 degrees it landed on a sidelobe and
        # returned that sidelobe's skirt as an elevation beamwidth.
        u_s = np.sin(np.radians(scan_angle_deg))
        psi_max_deg = np.degrees(np.arcsin(np.sqrt(max(0.0, 1.0 - u_s**2))))
        psi_deg = np.linspace(-psi_max_deg, psi_max_deg, 721)
        v_el = np.sin(np.radians(psi_deg))
        sin_theta_el = np.clip(np.hypot(u_s, v_el), 0.0, 1.0)
        theta_el = np.arcsin(sin_theta_el)
        phi_el = np.arctan2(v_el, u_s)
        tp_el = total_pattern(
            theta_el,
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

        # 6. Extract metrics from computed patterns.
        #
        # These are measured on the *steered* pattern, so beamwidth_az_deg
        # already carries the 1/cos(scan) broadening -- that is the convention
        # (see the class docstring), and evaluate.py must not apply it a second
        # time. The elevation cut does not broaden under an azimuth-plane scan:
        # phi = 90 gives u = sin(theta)cos(90) = 0 along the whole cut, so for a
        # separable taper the azimuth factor AFx(0 - u_s) is a constant on it and
        # only AFy(v) varies with theta. The element pattern is a function of
        # theta alone, so it too is a common factor. compute_beamwidth normalizes
        # to the cut's own peak, so what comes back is the broadside elevation
        # width at any azimuth scan.
        beamwidth_az = compute_beamwidth(tp_az_db, theta_deg)
        beamwidth_el = compute_beamwidth(tp_el_db, psi_deg)
        # Scan-invariant footprint, for consumers that tile a search volume
        # rather than look in one direction. Measured from the unsteered
        # taper rather than by dividing the scanned width back out by
        # cos(scan): the 1/cos law is only a model of what the steered cut
        # does, and backing it out is 31% off by a 75 degree scan. Impairments
        # are deliberately excluded -- this is the array's nominal tiling
        # footprint, not a performance metric.
        tp_az_bs = total_pattern(
            theta_rad,
            phi_az,
            geom.x,
            geom.y,
            taper_weights.astype(complex),
            k,
            element_pattern_func=element_pattern,
            cos_exp_theta=element_cos_exp,
        )
        tp_az_bs_db = 20 * np.log10(np.abs(tp_az_bs) + 1e-12)
        beamwidth_az_broadside = compute_beamwidth(tp_az_bs_db - np.max(tp_az_bs_db), theta_deg)
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
            "beamwidth_az_broadside_deg": beamwidth_az_broadside,
            # The elevation width does not broaden under an azimuth-plane
            # scan (see above), so the scanned and broadside values coincide.
            "beamwidth_el_broadside_deg": beamwidth_el,
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
        # broaden this slightly, not modeled here -- see the class docstring,
        # the two paths are not interchangeable to better than ~25% on a
        # tapered array)
        beamwidth_az_broadside_deg = np.degrees(0.886 / (nx * arch.array.dx_lambda))
        beamwidth_el_broadside_deg = np.degrees(0.886 / (ny * arch.array.dy_lambda))

        # Reported at the scan angle, as the pattern path reports them. The
        # scan is in azimuth only, so only the azimuth width broadens
        # (Curry Eq. 8.9); the elevation width is unchanged. Mirrors
        # compute_scan_loss at endfire, where the projected aperture vanishes.
        if scan_angle_deg >= 90.0:
            beamwidth_az_deg = float("inf")
        else:
            beamwidth_az_deg = beamwidth_az_broadside_deg / np.cos(np.radians(scan_angle_deg))
        beamwidth_el_deg = beamwidth_el_broadside_deg

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
            "beamwidth_az_broadside_deg": beamwidth_az_broadside_deg,
            "beamwidth_el_broadside_deg": beamwidth_el_broadside_deg,
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
