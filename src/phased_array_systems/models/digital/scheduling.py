"""Timeline and scheduling models for multi-function arrays.

This module provides functions for analyzing time-interleaved operations
in digital phased arrays supporting multiple functions (radar, ESM, comms).

Key Concepts:
    - Dwell: A single beam position with specific duration and function
    - Timeline: Sequence of dwells over a frame period
    - Utilization: Fraction of time actively used
    - Multi-function: Radar search, track, ESM, communications sharing aperture

References:
    - Brookner, E. "Phased Array Radars: Past, Present, and Future"
    - Richards, M. "Fundamentals of Radar Signal Processing", Chapter 1
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum


class Function(str, Enum):
    """Array function types for multi-function scheduling."""

    RADAR_SEARCH = "radar_search"
    RADAR_TRACK = "radar_track"
    RADAR_CONFIRM = "radar_confirm"
    ESM = "esm"  # Electronic Support Measures
    ECM = "ecm"  # Electronic Countermeasures
    COMMS = "comms"
    CALIBRATION = "calibration"
    IDLE = "idle"


@dataclass
class Dwell:
    """A single dwell (beam position) in the timeline.

    Attributes:
        function: Type of function being performed
        duration_us: Dwell duration in microseconds
        azimuth_deg: Beam azimuth angle in degrees
        elevation_deg: Beam elevation angle in degrees
        bandwidth_hz: Instantaneous bandwidth for this dwell
        priority: Scheduling priority (higher = more important)
        metadata: Additional function-specific parameters
    """

    function: Function
    duration_us: float
    azimuth_deg: float = 0.0
    elevation_deg: float = 0.0
    bandwidth_hz: float = 0.0
    priority: int = 1
    metadata: dict = field(default_factory=dict)

    @property
    def duration_ms(self) -> float:
        """Duration in milliseconds."""
        return self.duration_us / 1000

    @property
    def duration_s(self) -> float:
        """Duration in seconds."""
        return self.duration_us / 1e6


@dataclass
class Timeline:
    """A complete timeline of dwells over a frame period.

    Attributes:
        dwells: List of dwells in chronological order
        frame_time_ms: Total frame duration in milliseconds
        name: Optional timeline identifier
    """

    dwells: list[Dwell]
    frame_time_ms: float
    name: str = ""

    @property
    def total_dwell_time_ms(self) -> float:
        """Sum of all dwell durations."""
        return sum(d.duration_ms for d in self.dwells)

    @property
    def n_dwells(self) -> int:
        """Number of dwells in timeline."""
        return len(self.dwells)

    def dwells_by_function(self, function: Function) -> list[Dwell]:
        """Get all dwells for a specific function."""
        return [d for d in self.dwells if d.function == function]

    def time_for_function(self, function: Function) -> float:
        """Total time allocated to a function in ms."""
        return sum(d.duration_ms for d in self.dwells_by_function(function))


def timeline_utilization(timeline: Timeline) -> dict[str, float]:
    """Calculate timeline utilization metrics.

    Analyzes how efficiently the timeline uses available time
    and breaks down allocation by function.

    Args:
        timeline: Timeline object to analyze

    Returns:
        Dictionary with:
            - total_utilization: Fraction of frame time used (0-1)
            - idle_time_ms: Unused time in milliseconds
            - by_function: Dict of function -> time allocation
            - by_function_percent: Dict of function -> percentage

    Example:
        >>> tl = Timeline(dwells=[...], frame_time_ms=100)
        >>> util = timeline_utilization(tl)
        >>> print(f"Utilization: {util['total_utilization']*100:.1f}%")
    """
    total_dwell_ms = timeline.total_dwell_time_ms
    idle_time_ms = max(0, timeline.frame_time_ms - total_dwell_ms)
    utilization = total_dwell_ms / timeline.frame_time_ms if timeline.frame_time_ms > 0 else 0

    # Breakdown by function
    by_function = {}
    by_function_percent = {}

    for func in Function:
        time_ms = timeline.time_for_function(func)
        by_function[func.value] = time_ms
        by_function_percent[func.value] = (time_ms / timeline.frame_time_ms * 100) if timeline.frame_time_ms > 0 else 0

    return {
        "total_utilization": utilization,
        "total_dwell_time_ms": total_dwell_ms,
        "idle_time_ms": idle_time_ms,
        "frame_time_ms": timeline.frame_time_ms,
        "n_dwells": timeline.n_dwells,
        "by_function": by_function,
        "by_function_percent": by_function_percent,
    }


def max_update_rate(
    scan_volume_sr: float,
    beam_solid_angle_sr: float,
    dwell_time_us: float,
    overhead_us: float = 10.0,
) -> dict[str, float]:
    """Calculate maximum volume update rate for search.

    Determines how quickly a phased array can search a given volume.

    Args:
        scan_volume_sr: Search volume in steradians
        beam_solid_angle_sr: Beam solid angle in steradians (≈ θ_az * θ_el)
        dwell_time_us: Time per beam position in microseconds
        overhead_us: Beam switching overhead in microseconds

    Returns:
        Dictionary with:
            - n_beam_positions: Number of beams to cover volume
            - frame_time_ms: Time to complete one scan
            - update_rate_hz: Volume scans per second
            - scan_time_s: Time for one complete scan

    Example:
        >>> # Search ±60° az, ±30° el with 3° beam
        >>> result = max_update_rate(
        ...     scan_volume_sr=2.0,  # ~hemisphere
        ...     beam_solid_angle_sr=0.003,  # ~3° beam
        ...     dwell_time_us=100
        ... )
        >>> print(f"Update rate: {result['update_rate_hz']:.2f} Hz")
    """
    n_beam_positions = math.ceil(scan_volume_sr / beam_solid_angle_sr)
    time_per_position_us = dwell_time_us + overhead_us
    frame_time_us = n_beam_positions * time_per_position_us
    frame_time_ms = frame_time_us / 1000
    scan_time_s = frame_time_us / 1e6
    update_rate_hz = 1 / scan_time_s if scan_time_s > 0 else float('inf')

    return {
        "n_beam_positions": n_beam_positions,
        "frame_time_ms": frame_time_ms,
        "scan_time_s": scan_time_s,
        "update_rate_hz": update_rate_hz,
        "time_per_position_us": time_per_position_us,
    }


def search_timeline(
    azimuth_range_deg: tuple[float, float],
    elevation_range_deg: tuple[float, float],
    azimuth_step_deg: float,
    elevation_step_deg: float,
    dwell_time_us: float,
    function: Function = Function.RADAR_SEARCH,
) -> Timeline:
    """Generate a raster search timeline.

    Creates a timeline of dwells covering a rectangular search volume
    using a raster scan pattern.

    Args:
        azimuth_range_deg: (min, max) azimuth in degrees
        elevation_range_deg: (min, max) elevation in degrees
        azimuth_step_deg: Azimuth step between beams
        elevation_step_deg: Elevation step between beams
        dwell_time_us: Dwell time per position
        function: Function type for dwells

    Returns:
        Timeline with search dwells

    Example:
        >>> tl = search_timeline(
        ...     azimuth_range_deg=(-60, 60),
        ...     elevation_range_deg=(0, 30),
        ...     azimuth_step_deg=3.0,
        ...     elevation_step_deg=3.0,
        ...     dwell_time_us=100
        ... )
        >>> print(f"Generated {tl.n_dwells} dwells")
    """
    dwells = []

    az_min, az_max = azimuth_range_deg
    el_min, el_max = elevation_range_deg

    el = el_min
    row = 0
    while el <= el_max:
        # Alternate scan direction for efficiency
        if row % 2 == 0:
            az_range = _frange(az_min, az_max, azimuth_step_deg)
        else:
            az_range = _frange(az_max, az_min, -azimuth_step_deg)

        for az in az_range:
            dwell = Dwell(
                function=function,
                duration_us=dwell_time_us,
                azimuth_deg=az,
                elevation_deg=el,
            )
            dwells.append(dwell)

        el += elevation_step_deg
        row += 1

    total_time_ms = sum(d.duration_ms for d in dwells)

    return Timeline(
        dwells=dwells,
        frame_time_ms=total_time_ms,
        name=f"Search {az_min:.0f}:{az_max:.0f} az, {el_min:.0f}:{el_max:.0f} el",
    )


def interleaved_timeline(
    functions: list[dict],
    frame_time_ms: float,
) -> Timeline:
    """Generate an interleaved multi-function timeline.

    Creates a timeline that allocates time to multiple functions
    based on specified priorities and time allocations.

    Args:
        functions: List of dicts with:
            - function: Function enum value
            - time_percent: Percentage of frame time
            - dwell_time_us: Duration of each dwell
            - dwells_per_burst: Number of consecutive dwells
        frame_time_ms: Total frame duration

    Returns:
        Timeline with interleaved function dwells

    Example:
        >>> tl = interleaved_timeline(
        ...     functions=[
        ...         {"function": Function.RADAR_SEARCH, "time_percent": 60,
        ...          "dwell_time_us": 100, "dwells_per_burst": 10},
        ...         {"function": Function.RADAR_TRACK, "time_percent": 30,
        ...          "dwell_time_us": 50, "dwells_per_burst": 5},
        ...         {"function": Function.ESM, "time_percent": 10,
        ...          "dwell_time_us": 200, "dwells_per_burst": 2},
        ...     ],
        ...     frame_time_ms=100
        ... )
    """
    dwells = []

    # Calculate time budget for each function
    for func_spec in functions:
        func = func_spec["function"]
        time_budget_ms = frame_time_ms * func_spec["time_percent"] / 100
        dwell_time_us = func_spec["dwell_time_us"]

        # How many dwells fit in budget?
        dwell_time_ms = dwell_time_us / 1000
        n_dwells = int(time_budget_ms / dwell_time_ms)

        # Create dwells (simple placeholder positions)
        for _ in range(n_dwells):
            dwell = Dwell(
                function=func,
                duration_us=dwell_time_us,
                azimuth_deg=0.0,  # Would be populated by scheduler
                elevation_deg=0.0,
                priority=func_spec.get("priority", 1),
            )
            dwells.append(dwell)

    # Sort by priority (higher priority dwells interleaved more frequently)
    # This is a simplified scheduling - real systems use more sophisticated algorithms
    dwells.sort(key=lambda d: -d.priority)

    return Timeline(
        dwells=dwells,
        frame_time_ms=frame_time_ms,
        name="Interleaved multi-function",
    )


def _frange(start: float, stop: float, step: float):
    """Float range generator."""
    if step > 0:
        while start <= stop:
            yield start
            start += step
    else:
        while start >= stop:
            yield start
            start += step
