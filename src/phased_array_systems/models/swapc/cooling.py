"""Cooling-technology feasibility for aperture heat flux.

A junction-to-ambient thermal resistance is an *assertion* about a cooling
solution. This module checks the assertion: given the design's aperture heat
flux, can the declared cooling approach actually remove it?

The thresholds are order-of-magnitude regime gates from ``data/cooling.yaml``,
where every number records whether it was quoted from a primary source or is
an engineering-judgment gate consistent with one.
"""

from __future__ import annotations

from functools import cache
from importlib.resources import files
from typing import Any, cast

import yaml

CATALOG_FILE = "cooling.yaml"

#: Entries in the catalog that describe context rather than a cooling class.
_NON_CLASS_KEYS = frozenset({"notes"})


def resolve(raw: Any) -> Any:
    """Return the usable value of a provenance mapping, or the scalar."""
    if isinstance(raw, dict) and "value" in raw:
        return raw["value"]
    return raw


@cache
def load_catalog() -> dict[str, Any]:
    """Load and cache the cooling catalog."""
    text = (files("phased_array_systems.data") / CATALOG_FILE).read_text()
    return cast(dict[str, Any], yaml.safe_load(text) or {})


def cooling_classes() -> list[str]:
    """Available cooling-class keys, weakest capability first."""
    catalog = load_catalog()
    classes = [k for k in catalog if k not in _NON_CLASS_KEYS]
    return sorted(classes, key=lambda k: float(resolve(catalog[k]["max_heat_flux_w_per_cm2"])))


def max_heat_flux(cooling_class: str) -> float:
    """Aperture heat flux (W/cm^2) the named class is gated at."""
    catalog = load_catalog()
    key = cooling_class.lower()
    if key in _NON_CLASS_KEYS or key not in catalog:
        raise KeyError(f"unknown cooling class {cooling_class!r}; available: {cooling_classes()}")
    return float(resolve(catalog[key]["max_heat_flux_w_per_cm2"]))


def assess(heat_flux_w_per_cm2: float, cooling_class: str) -> dict[str, Any]:
    """Compare a design's heat flux against its declared cooling class.

    Returns ``cooling_class``, ``max_heat_flux_w_per_cm2``,
    ``cooling_margin_w_per_cm2`` (positive means headroom) and
    ``cooling_feasible``.
    """
    ceiling = max_heat_flux(cooling_class)
    margin = ceiling - heat_flux_w_per_cm2
    return {
        "cooling_class": cooling_class.lower(),
        "max_heat_flux_w_per_cm2": ceiling,
        "cooling_margin_w_per_cm2": margin,
        "cooling_feasible": bool(margin >= 0.0),
    }


def minimum_class_for(heat_flux_w_per_cm2: float) -> str | None:
    """The weakest cooling class that supports this flux, or None if past all."""
    for name in cooling_classes():
        if max_heat_flux(name) >= heat_flux_w_per_cm2:
            return name
    return None
