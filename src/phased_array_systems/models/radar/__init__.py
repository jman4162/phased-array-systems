"""Radar detection models."""

from phased_array_systems.models.radar.cfar import (
    ca_cfar_threshold_factor,
    cfar_loss_db,
    cfar_threshold_factor,
    compute_pd_with_cfar,
    go_cfar_threshold_factor,
    optimal_reference_cells,
    os_cfar_threshold_factor,
    so_cfar_threshold_factor,
)
from phased_array_systems.models.radar.clutter import (
    compute_resolution_cell_area,
    compute_resolution_volume,
    compute_scnr,
    compute_scr,
    ground_clutter_rcs,
    ground_clutter_sigma0,
    rain_clutter_rcs,
    rain_reflectivity,
    sea_clutter_rcs,
    sea_clutter_sigma0,
)
from phased_array_systems.models.radar.detection import (
    albersheim_snr,
    compute_detection_threshold,
    compute_pd_from_snr,
    compute_snr_for_pd,
)
from phased_array_systems.models.radar.equation import RadarModel
from phased_array_systems.models.radar.integration import (
    coherent_integration_gain,
    integration_loss,
    noncoherent_integration_gain,
)
from phased_array_systems.models.radar.mti import (
    blind_speed_ms,
    canceller_weights,
    clutter_autocorrelation,
    clutter_spectral_std_hz,
    doppler_shift_hz,
    mti_clutter_attenuation,
    mti_improvement_factor,
    mti_signal_gain,
    normalized_clutter_spread_rad,
    required_clutter_attenuation_db,
    unambiguous_range_m,
)
from phased_array_systems.models.radar.propagation import (
    atmospheric_attenuation_db_per_km,
    atmospheric_loss_db,
    grazing_angle_deg,
    multipath_fading_factor,
    radar_horizon_km,
    rain_attenuation_db,
    rain_attenuation_rate,
)
from phased_array_systems.models.radar.tracking import (
    alpha_beta_gains,
    angle_sigma_deg,
    combine_angle_errors_deg,
    crossrange_sigma_m,
    deterministic_tracking_index,
    maneuver_lag_m,
    process_noise_from_maneuver,
    range_resolution_m,
    range_sigma_m,
    scan_broadened_beamwidth_deg,
    steady_state_sigmas,
    tracking_index,
    variance_reduction_position,
    velocity_sigma_ms,
)

__all__ = [
    # Main model
    "RadarModel",
    # MTI clutter suppression
    "clutter_spectral_std_hz",
    "normalized_clutter_spread_rad",
    "clutter_autocorrelation",
    "canceller_weights",
    "mti_signal_gain",
    "mti_improvement_factor",
    "mti_clutter_attenuation",
    "required_clutter_attenuation_db",
    "blind_speed_ms",
    "doppler_shift_hz",
    "unambiguous_range_m",
    # Track accuracy
    "range_resolution_m",
    "range_sigma_m",
    "angle_sigma_deg",
    "scan_broadened_beamwidth_deg",
    "crossrange_sigma_m",
    "velocity_sigma_ms",
    "combine_angle_errors_deg",
    "tracking_index",
    "deterministic_tracking_index",
    "process_noise_from_maneuver",
    "alpha_beta_gains",
    "steady_state_sigmas",
    "variance_reduction_position",
    "maneuver_lag_m",
    # Detection
    "compute_detection_threshold",
    "compute_pd_from_snr",
    "compute_snr_for_pd",
    "albersheim_snr",
    # Integration
    "coherent_integration_gain",
    "noncoherent_integration_gain",
    "integration_loss",
    # Clutter
    "sea_clutter_sigma0",
    "sea_clutter_rcs",
    "ground_clutter_sigma0",
    "ground_clutter_rcs",
    "rain_reflectivity",
    "rain_clutter_rcs",
    "compute_resolution_cell_area",
    "compute_resolution_volume",
    "compute_scr",
    "compute_scnr",
    # Propagation
    "atmospheric_attenuation_db_per_km",
    "atmospheric_loss_db",
    "rain_attenuation_rate",
    "rain_attenuation_db",
    "radar_horizon_km",
    "grazing_angle_deg",
    "multipath_fading_factor",
    # CFAR
    "ca_cfar_threshold_factor",
    "os_cfar_threshold_factor",
    "go_cfar_threshold_factor",
    "so_cfar_threshold_factor",
    "cfar_threshold_factor",
    "cfar_loss_db",
    "optimal_reference_cells",
    "compute_pd_with_cfar",
]
