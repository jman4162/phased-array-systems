"""RF chain and cascaded performance models."""

from phased_array_systems.models.rf.cascade import (
    RFStage,
    cascade_analysis,
    cascade_gain,
    cascade_gain_db,
    cascade_iip3,
    cascade_oip3,
    friis_noise_figure,
    mds_from_noise_figure,
    noise_figure_to_temp,
    noise_temp_to_figure,
    sfdr_from_iip3,
    sfdr_from_oip3,
    system_noise_temperature,
)
from phased_array_systems.models.rf.reliability import (
    ArrayReliabilityResult,
    TRMReliabilitySpec,
    analyze_array_reliability,
    array_mtbf,
    availability,
    degraded_gain,
    degraded_sidelobe,
    expected_failures,
    max_failures_for_spec,
    plot_availability_vs_mtbf,
    plot_degradation_curves,
    prob_failed_elements,
    trm_mtbf,
)

__all__ = [
    # Noise figure
    "friis_noise_figure",
    "noise_figure_to_temp",
    "noise_temp_to_figure",
    "system_noise_temperature",
    # Gain
    "cascade_gain",
    "cascade_gain_db",
    # Dynamic range
    "cascade_iip3",
    "cascade_oip3",
    "sfdr_from_iip3",
    "sfdr_from_oip3",
    "mds_from_noise_figure",
    # Complete cascade
    "RFStage",
    "cascade_analysis",
    # TRM Reliability
    "trm_mtbf",
    "array_mtbf",
    "prob_failed_elements",
    "expected_failures",
    "availability",
    "degraded_gain",
    "degraded_sidelobe",
    "max_failures_for_spec",
    "TRMReliabilitySpec",
    "ArrayReliabilityResult",
    "analyze_array_reliability",
    "plot_degradation_curves",
    "plot_availability_vs_mtbf",
]
