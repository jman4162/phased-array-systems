"""Shared propagation reference models (ITU-R P.676, P.838, path helpers).

Backend for the comms and radar propagation wrappers. Coefficient data is
vendored verbatim from the cited Recommendations; no network access or
external dependency is required.
"""

from phased_array_systems.models.propagation.itu_p676 import (
    gaseous_attenuation_components_db_per_km,
    gaseous_attenuation_db_per_km,
    gaseous_attenuation_from_humidity,
    saturation_vapor_pressure_hpa,
    water_vapor_density_g_m3,
)
from phased_array_systems.models.propagation.itu_p838 import (
    rain_k_alpha,
    rain_specific_attenuation_db_per_km,
)
from phased_array_systems.models.propagation.path import (
    H2O_EQUIVALENT_HEIGHT_KM,
    O2_EQUIVALENT_HEIGHT_KM,
    effective_rain_path_km,
    gaseous_slant_path_km,
)

__all__ = [
    "H2O_EQUIVALENT_HEIGHT_KM",
    "O2_EQUIVALENT_HEIGHT_KM",
    "effective_rain_path_km",
    "gaseous_attenuation_components_db_per_km",
    "gaseous_attenuation_db_per_km",
    "gaseous_attenuation_from_humidity",
    "gaseous_slant_path_km",
    "rain_k_alpha",
    "rain_specific_attenuation_db_per_km",
    "saturation_vapor_pressure_hpa",
    "water_vapor_density_g_m3",
]
