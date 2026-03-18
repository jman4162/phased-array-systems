"""TRM reliability and graceful degradation models.

This module implements reliability analysis for phased array T/R modules (TRMs):
- MTBF calculations based on MIL-HDBK-217 approximations
- Array-level reliability for various redundancy schemes
- Failure probability distributions
- Graceful degradation of gain and sidelobe levels

These models are essential for system availability analysis and determining
maintenance intervals for fielded phased array systems.

Key Concepts:
    - MTBF (Mean Time Between Failures): Average time until a component fails
    - Availability: Fraction of time the system meets requirements
    - Graceful degradation: Performance reduction as elements fail

References:
    - MIL-HDBK-217F: Reliability Prediction of Electronic Equipment
    - Brookner, E. "Practical Phased Array Antenna Systems"
    - Your PowerPoint: Section on AESA reliability considerations
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

# ============== MTBF Calculations ==============

def trm_mtbf(
    component_mtbfs: dict[str, float],
    operating_temp_c: float = 85.0,
    temp_reference_c: float = 55.0,
    activation_energy_ev: float = 0.7,
) -> float:
    """Calculate TRM MTBF from component-level MTBFs.

    Uses series reliability model: 1/MTBF_total = sum(1/MTBF_i)
    Includes Arrhenius temperature derating.

    Args:
        component_mtbfs: Dictionary of component name -> MTBF in hours
            Typical components: 'lna', 'pa', 'phase_shifter', 'switch', etc.
        operating_temp_c: Operating junction temperature in Celsius
        temp_reference_c: Reference temperature for MTBF data (default 55C)
        activation_energy_ev: Arrhenius activation energy (default 0.7 eV)

    Returns:
        TRM MTBF in hours

    Examples:
        >>> components = {
        ...     'lna': 500_000,
        ...     'pa': 250_000,
        ...     'phase_shifter': 2_000_000,
        ...     'switch': 1_000_000,
        ... }
        >>> mtbf = trm_mtbf(components, operating_temp_c=85)
        >>> mtbf > 100_000  # Reasonable TRM MTBF
        True

    Notes:
        Temperature acceleration factor:
            AF = exp((Ea/k) * (1/T_ref - 1/T_op))
        where Ea is activation energy, k is Boltzmann constant.
    """
    if not component_mtbfs:
        return float('inf')

    # Boltzmann constant in eV/K
    k_boltzmann = 8.617e-5

    # Convert temperatures to Kelvin
    t_op_k = operating_temp_c + 273.15
    t_ref_k = temp_reference_c + 273.15

    # Arrhenius acceleration factor
    exponent = (activation_energy_ev / k_boltzmann) * (1/t_ref_k - 1/t_op_k)
    acceleration_factor = math.exp(exponent)

    # Apply temperature derating to all components
    derated_mtbfs = {name: mtbf / acceleration_factor
                     for name, mtbf in component_mtbfs.items()}

    # Series reliability: 1/MTBF_total = sum(1/MTBF_i)
    failure_rate_sum = sum(1/mtbf for mtbf in derated_mtbfs.values())

    return 1 / failure_rate_sum


def array_mtbf(
    trm_mtbf_hours: float,
    n_elements: int,
    redundancy: str = 'none',
    spare_count: int = 0,
) -> float:
    """Calculate array-level MTBF for given redundancy scheme.

    Args:
        trm_mtbf_hours: MTBF of a single TRM in hours
        n_elements: Total number of TRM elements
        redundancy: Redundancy scheme:
            'none' - No redundancy, first failure is array failure
            'graceful' - Graceful degradation, array fails at threshold
            'k_of_n' - K-of-N redundancy (use spare_count)
        spare_count: For 'k_of_n', number of elements that can fail
            before array fails

    Returns:
        Array MTBF in hours

    Examples:
        >>> # 1000-element array with 10 spares
        >>> mtbf = array_mtbf(200_000, 1000, redundancy='k_of_n', spare_count=10)
        >>> mtbf < 200_000  # Array MTBF less than element MTBF
        True

    Notes:
        For 'none': MTBF_array = MTBF_trm / N
        For 'k_of_n' with k failures allowed:
            Uses sum of failure rates up to k failures
    """
    if n_elements <= 0:
        return float('inf')

    if redundancy == 'none':
        # First failure kills the array
        return trm_mtbf_hours / n_elements

    elif redundancy == 'graceful' or redundancy == 'k_of_n':
        # K-of-N redundancy: array works with up to k failures
        k = spare_count

        if k >= n_elements:
            return float('inf')  # More spares than elements

        # For exponential failures, time to (k+1)th failure
        # MTBF = MTBF_trm * sum(1/i, i=n-k to n)
        harmonic_sum = sum(1/i for i in range(n_elements - k, n_elements + 1))
        return trm_mtbf_hours * harmonic_sum

    else:
        raise ValueError(f"Unknown redundancy scheme: {redundancy}")


# ============== Failure Probability ==============

def prob_failed_elements(
    n_elements: int,
    trm_mtbf_hours: float,
    operating_hours: float,
) -> NDArray[np.floating]:
    """Compute probability distribution of number of failed elements.

    Assumes exponential failure distribution (constant failure rate).

    Args:
        n_elements: Total number of TRM elements
        trm_mtbf_hours: MTBF of a single TRM in hours
        operating_hours: Cumulative operating time

    Returns:
        Probability array of shape (n_elements + 1,)
        prob[k] = P(exactly k elements have failed)

    Examples:
        >>> probs = prob_failed_elements(100, 200_000, 10_000)
        >>> probs.shape
        (101,)
        >>> np.isclose(np.sum(probs), 1.0)  # Should sum to 1
        True
    """
    # Failure probability per element
    p_fail = 1 - math.exp(-operating_hours / trm_mtbf_hours)
    p_survive = 1 - p_fail

    # Binomial distribution
    k = np.arange(n_elements + 1)
    from scipy.special import comb
    probs = comb(n_elements, k, exact=False) * (p_fail ** k) * (p_survive ** (n_elements - k))

    return probs


def expected_failures(
    n_elements: int,
    trm_mtbf_hours: float,
    operating_hours: float,
) -> float:
    """Compute expected number of failed elements.

    Args:
        n_elements: Total number of TRM elements
        trm_mtbf_hours: MTBF of a single TRM in hours
        operating_hours: Cumulative operating time

    Returns:
        Expected number of failed elements

    Examples:
        >>> expected = expected_failures(1000, 200_000, 10_000)
        >>> 40 < expected < 60  # ~5% failure rate expected
        True
    """
    p_fail = 1 - math.exp(-operating_hours / trm_mtbf_hours)
    return n_elements * p_fail


def availability(
    trm_mtbf_hours: float,
    mttr_hours: float,
) -> float:
    """Compute steady-state availability.

    Availability = MTBF / (MTBF + MTTR)

    Args:
        trm_mtbf_hours: Mean time between failures
        mttr_hours: Mean time to repair

    Returns:
        Availability as fraction (0 to 1)

    Examples:
        >>> avail = availability(200_000, 8)  # 8-hour repair time
        >>> avail > 0.999  # Should be very high
        True
    """
    return trm_mtbf_hours / (trm_mtbf_hours + mttr_hours)


# ============== Graceful Degradation ==============

def degraded_gain(
    n_elements: int,
    n_failed: int,
    failure_pattern: str = 'random',
) -> float:
    """Estimate gain reduction due to failed elements.

    Args:
        n_elements: Total number of elements
        n_failed: Number of failed elements
        failure_pattern: Pattern of failures:
            'random' - Randomly distributed failures
            'clustered' - Failures in a cluster (worst case)
            'edge' - Failures at array edges (best case)

    Returns:
        Gain loss in dB (negative value)

    Examples:
        >>> loss = degraded_gain(1000, 50, 'random')  # 5% failed
        >>> -0.5 < loss < 0  # Small loss expected
        True

    Notes:
        For random failures: Loss ≈ 20*log10(1 - n_failed/N)
        This is approximate; actual loss depends on failed element positions.
    """
    if n_failed >= n_elements:
        return float('-inf')

    if n_failed == 0:
        return 0.0

    surviving_ratio = (n_elements - n_failed) / n_elements

    if failure_pattern == 'random':
        # Power is proportional to (sum of weights)^2
        # For random failures, expect ~(N-k)^2 / N^2 gain
        gain_ratio = surviving_ratio ** 2
    elif failure_pattern == 'clustered':
        # Worst case: larger gain loss due to pattern disruption
        # Add penalty factor
        penalty = 1.0 + 0.5 * (n_failed / n_elements)
        gain_ratio = (surviving_ratio ** 2) / penalty
    elif failure_pattern == 'edge':
        # Best case: edge elements contribute less
        # Slight improvement over random
        improvement = 1.0 + 0.2 * (n_failed / n_elements)
        gain_ratio = min(1.0, (surviving_ratio ** 2) * improvement)
    else:
        raise ValueError(f"Unknown failure pattern: {failure_pattern}")

    if gain_ratio <= 0:
        return float('-inf')

    return 10 * math.log10(gain_ratio)


def degraded_sidelobe(
    n_elements: int,
    n_failed: int,
    original_sll_db: float = -13.2,
    failure_pattern: str = 'random',
) -> float:
    """Estimate sidelobe level increase due to failed elements.

    Args:
        n_elements: Total number of elements
        n_failed: Number of failed elements
        original_sll_db: Original sidelobe level in dB (negative)
        failure_pattern: Pattern of failures ('random', 'clustered', 'edge')

    Returns:
        New sidelobe level in dB (less negative = worse)

    Examples:
        >>> sll = degraded_sidelobe(1000, 50, -30)  # 5% failed, -30 dB original
        >>> sll > -30  # Should be worse (less negative)
        True

    Notes:
        Random element failures create noise in the pattern that raises
        the average sidelobe level. The increase is approximately:
            ΔSL ≈ 10*log10(1 + N*p_fail/(N*(1-p_fail))^2 / (10^(SL/10)))
    """
    if n_failed >= n_elements:
        return 0.0  # Complete failure

    if n_failed == 0:
        return original_sll_db

    p_fail = n_failed / n_elements
    n_surviving = n_elements - n_failed

    # Original sidelobe power (linear)
    sl_power_original = 10 ** (original_sll_db / 10)

    # Failed elements contribute noise-like sidelobes
    # Noise power ~ n_failed / n_surviving^2 (relative to main beam)
    if failure_pattern == 'random':
        noise_power = n_failed / (n_surviving ** 2)
    elif failure_pattern == 'clustered':
        # Clustered failures cause higher sidelobe increase
        noise_power = 1.5 * n_failed / (n_surviving ** 2)
    elif failure_pattern == 'edge':
        # Edge failures have less impact on sidelobes
        noise_power = 0.7 * n_failed / (n_surviving ** 2)
    else:
        raise ValueError(f"Unknown failure pattern: {failure_pattern}")

    # New sidelobe level: max of original and noise floor
    new_sl_power = max(sl_power_original, noise_power)

    # Also consider degradation of taper effectiveness
    if original_sll_db < -20:  # Tapered array
        taper_degradation = 1 + 2 * p_fail  # Taper becomes less effective
        new_sl_power = new_sl_power * taper_degradation

    return 10 * math.log10(new_sl_power)


def max_failures_for_spec(
    n_elements: int,
    gain_margin_db: float,
    sll_margin_db: float,
    original_sll_db: float = -13.2,
) -> int:
    """Determine maximum allowable failures to meet specifications.

    Finds the maximum number of element failures before either
    gain loss or sidelobe degradation exceeds the specified margins.

    Args:
        n_elements: Total number of elements
        gain_margin_db: Allowable gain loss in dB (positive value)
        sll_margin_db: Allowable sidelobe increase in dB (positive value)
        original_sll_db: Original sidelobe level in dB

    Returns:
        Maximum number of failed elements while meeting spec

    Examples:
        >>> max_fail = max_failures_for_spec(1000, gain_margin_db=1.0, sll_margin_db=3.0)
        >>> 50 < max_fail < 200  # Reasonable range for 1000 elements
        True
    """
    max_failures = 0

    for n_failed in range(n_elements):
        gain_loss = -degraded_gain(n_elements, n_failed, 'random')  # Make positive
        new_sll = degraded_sidelobe(n_elements, n_failed, original_sll_db, 'random')
        sll_increase = new_sll - original_sll_db

        if gain_loss > gain_margin_db or sll_increase > sll_margin_db:
            break

        max_failures = n_failed

    return max_failures


# ============== Data Classes ==============

@dataclass
class TRMReliabilitySpec:
    """Specification for TRM reliability analysis.

    Attributes:
        component_mtbfs: MTBF for each component type (hours)
        operating_temp_c: Junction temperature during operation
        mttr_hours: Mean time to repair
        mission_hours: Expected mission/deployment duration
    """
    component_mtbfs: dict[str, float] = field(default_factory=lambda: {
        'lna': 500_000,
        'pa': 250_000,
        'phase_shifter': 2_000_000,
        'attenuator': 3_000_000,
        'switch': 1_000_000,
        'control_asic': 1_000_000,
    })
    operating_temp_c: float = 85.0
    mttr_hours: float = 8.0
    mission_hours: float = 50_000.0  # ~5.7 years


@dataclass
class ArrayReliabilityResult:
    """Results from array reliability analysis.

    Attributes:
        trm_mtbf_hours: Calculated TRM MTBF
        array_mtbf_hours: Array-level MTBF
        expected_failures: Expected failures over mission
        availability: System availability fraction
        max_failures_for_spec: Maximum failures meeting spec
        prob_meeting_spec: Probability of meeting spec at end of mission
    """
    trm_mtbf_hours: float
    array_mtbf_hours: float
    expected_failures: float
    availability: float
    max_failures_for_spec: int
    prob_meeting_spec: float


def analyze_array_reliability(
    n_elements: int,
    spec: TRMReliabilitySpec,
    gain_margin_db: float = 1.0,
    sll_margin_db: float = 3.0,
    original_sll_db: float = -30.0,
) -> ArrayReliabilityResult:
    """Perform comprehensive array reliability analysis.

    Args:
        n_elements: Number of TRM elements
        spec: TRM reliability specification
        gain_margin_db: Allowable gain loss
        sll_margin_db: Allowable sidelobe increase
        original_sll_db: Original sidelobe level

    Returns:
        ArrayReliabilityResult with all metrics

    Examples:
        >>> spec = TRMReliabilitySpec()
        >>> result = analyze_array_reliability(256, spec)
        >>> result.trm_mtbf_hours > 100_000
        True
    """
    # Calculate TRM MTBF
    calculated_trm_mtbf = trm_mtbf(spec.component_mtbfs, spec.operating_temp_c)

    # Calculate array MTBF (with graceful degradation)
    max_fail = max_failures_for_spec(n_elements, gain_margin_db, sll_margin_db, original_sll_db)
    arr_mtbf = array_mtbf(calculated_trm_mtbf, n_elements, 'k_of_n', spare_count=max_fail)

    # Expected failures at end of mission
    exp_fail = expected_failures(n_elements, calculated_trm_mtbf, spec.mission_hours)

    # Availability
    avail = availability(calculated_trm_mtbf, spec.mttr_hours)

    # Probability of meeting spec at end of mission
    probs = prob_failed_elements(n_elements, calculated_trm_mtbf, spec.mission_hours)
    prob_meet_spec = float(np.sum(probs[:max_fail + 1]))

    return ArrayReliabilityResult(
        trm_mtbf_hours=calculated_trm_mtbf,
        array_mtbf_hours=arr_mtbf,
        expected_failures=exp_fail,
        availability=avail,
        max_failures_for_spec=max_fail,
        prob_meeting_spec=prob_meet_spec,
    )


# ============== Visualization Helpers ==============

def plot_degradation_curves(
    n_elements: int,
    max_failures: int,
    original_sll_db: float = -30.0,
    ax=None,
):
    """Plot gain and sidelobe degradation vs number of failures.

    Args:
        n_elements: Total number of elements
        max_failures: Maximum failures to plot
        original_sll_db: Original sidelobe level
        ax: Matplotlib axes (creates new if None)

    Returns:
        Matplotlib axes object
    """
    import matplotlib.pyplot as plt

    if ax is None or not hasattr(ax, '__len__'):
        fig, ax = plt.subplots(1, 2, figsize=(12, 5))

    failures = np.arange(0, max_failures + 1)
    gain_losses = [degraded_gain(n_elements, n, 'random') for n in failures]
    sll_values = [degraded_sidelobe(n_elements, n, original_sll_db, 'random') for n in failures]

    # Gain plot
    ax[0].plot(failures, gain_losses, 'b-', linewidth=2)
    ax[0].set_xlabel('Number of Failed Elements')
    ax[0].set_ylabel('Gain Loss (dB)')
    ax[0].set_title(f'Gain Degradation ({n_elements} elements)')
    ax[0].grid(True, alpha=0.3)
    ax[0].axhline(y=-1, color='r', linestyle='--', label='-1 dB margin')
    ax[0].legend()

    # Sidelobe plot
    ax[1].plot(failures, sll_values, 'r-', linewidth=2)
    ax[1].set_xlabel('Number of Failed Elements')
    ax[1].set_ylabel('Sidelobe Level (dB)')
    ax[1].set_title(f'Sidelobe Degradation ({n_elements} elements)')
    ax[1].grid(True, alpha=0.3)
    ax[1].axhline(y=original_sll_db + 3, color='b', linestyle='--', label='+3 dB margin')
    ax[1].legend()

    plt.tight_layout()
    return ax


def plot_availability_vs_mtbf(
    n_elements: int,
    mission_hours: float,
    target_availability: float = 0.95,
    ax=None,
):
    """Plot array availability vs TRM MTBF.

    Args:
        n_elements: Number of elements
        mission_hours: Mission duration in hours
        target_availability: Target availability level
        ax: Matplotlib axes

    Returns:
        Matplotlib axes object
    """
    import matplotlib.pyplot as plt

    if ax is None:
        fig, ax = plt.subplots(figsize=(8, 6))

    mtbf_range = np.logspace(4, 7, 100)  # 10k to 10M hours

    # Simple availability approximation
    availabilities = []
    for mtbf in mtbf_range:
        exp_fail = expected_failures(n_elements, mtbf, mission_hours)
        # Availability approximation: fraction of expected survivors
        avail = 1 - (exp_fail / n_elements)
        availabilities.append(max(0, avail))

    ax.semilogx(mtbf_range, availabilities, 'b-', linewidth=2)
    ax.axhline(y=target_availability, color='r', linestyle='--',
               label=f'Target: {target_availability:.0%}')
    ax.set_xlabel('TRM MTBF (hours)')
    ax.set_ylabel('Array Availability')
    ax.set_title(f'Array Availability vs TRM MTBF\n({n_elements} elements, {mission_hours:,.0f} hour mission)')
    ax.grid(True, alpha=0.3)
    ax.legend()
    ax.set_ylim(0.8, 1.01)

    plt.tight_layout()
    return ax
