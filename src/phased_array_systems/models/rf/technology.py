"""Semiconductor technology catalog for T/R module trades.

The catalog (``data/technologies.yaml``) stores survey and review *ranges*
per technology — SiGe, GaAs, GaN, CMOS, LDMOS — with every number carrying
a citation that was fetched and read when the row was written. The loader
follows spacedc-mdao's provenance pattern: numeric fields are mappings
``{value, units, source, url, accessed, kind, confidence, quote}``;
``resolve`` returns the usable value.

Range policy: where a field stores ``[lo, hi]``, ``technology_defaults``
returns the midpoint. That is a documented convention, not a claim about
any device; explicit values on a component always override.

``docs/technology-catalog.md`` is generated from the YAML by
``render_provenance_table`` (``python -m phased_array_systems.models.rf.technology``).
"""

from __future__ import annotations

from functools import cache
from importlib.resources import files
from typing import Any, cast

import yaml

CATALOG_FILE = "technologies.yaml"


def resolve(raw: Any) -> Any:
    """Return the usable value: the `value` of a provenance mapping, or the scalar."""
    if isinstance(raw, dict) and "value" in raw:
        return raw["value"]
    return raw


def midpoint(value: Any) -> float:
    """Collapse a [lo, hi] range to its midpoint; pass scalars through."""
    if isinstance(value, list):
        if len(value) != 2:
            raise ValueError(f"expected [lo, hi], got {value}")
        return (float(value[0]) + float(value[1])) / 2.0
    return float(value)


@cache
def load_catalog() -> dict[str, Any]:
    """Load and cache the technology catalog."""
    text = (files("phased_array_systems.data") / CATALOG_FILE).read_text()
    return cast(dict[str, Any], yaml.safe_load(text) or {})


def technologies() -> list[str]:
    """Available technology keys."""
    return sorted(load_catalog())


def entry(technology: str) -> dict[str, Any]:
    """One catalog entry with every field resolved to its value."""
    catalog = load_catalog()
    key = technology.lower()
    if key not in catalog:
        raise KeyError(f"unknown technology {key!r}; available: {sorted(catalog)}")
    return {k: resolve(v) for k, v in catalog[key].items()}


def technology_defaults(technology: str) -> dict[str, float]:
    """Component parameter defaults a technology choice implies.

    Returns midpoints of the catalog ranges for the fields the TRM hook
    fills: ``lna_nf_db``, ``lna_iip3_dbm`` where present, and
    ``pa_p1db_dbm`` taken from the catalog's ``pa_class_dbm``. The PA class
    is a saturated/optimization power class, so using it as P1dB is an
    optimistic upper bound — stated here once and in the generated docs.
    """
    e = entry(technology)
    defaults: dict[str, float] = {}
    if "lna_nf_db" in e:
        defaults["lna_nf_db"] = midpoint(e["lna_nf_db"])
    if "lna_iip3_dbm" in e:
        defaults["lna_iip3_dbm"] = midpoint(e["lna_iip3_dbm"])
    if "pa_class_dbm" in e:
        defaults["pa_p1db_dbm"] = midpoint(e["pa_class_dbm"])
    return defaults


def render_provenance_table() -> str:
    """Render the catalog with full provenance as a Markdown document."""
    catalog = load_catalog()
    lines = [
        "# Technology catalog provenance",
        "",
        "Generated from `src/phased_array_systems/data/technologies.yaml` by",
        "`python -m phased_array_systems.models.rf.technology`. Do not edit by hand.",
        "",
        "Values are survey/review ranges or single published data points, each",
        "with the citation that was fetched when the row was written. Ranges",
        "collapse to midpoints in `technology_defaults`. The `pa_class_dbm`",
        "field is a saturated/optimization power class; the TRM hook uses it",
        "as a P1dB default, which is an optimistic upper bound.",
        "",
        "For the full published-design landscape rather than class ranges, see",
        "the [ETH IDEAS PA Survey](https://ideas.ethz.ch/Surveys/pa-survey.html)",
        "(v10: 5073 designs, 500 MHz-1.5 THz, CMOS/SiGe/GaN/GaAs/InP/LDMOS) and",
        "the [ETH IDEAS LNA Survey](https://ideas.ethz.ch/Surveys/lna-survey.html)",
        "(v3.0, silicon/SiGe, 500 MHz-300 GHz), both accessed 2026-08-11.",
        "",
    ]
    for tech in sorted(catalog):
        fields = catalog[tech]
        name = fields.get("name", tech)
        lines.append(f"## {tech} — {name}")
        lines.append("")
        lines.append("| field | value | units | source | confidence |")
        lines.append("|---|---|---|---|---|")
        for field, raw in fields.items():
            if field == "name":
                continue
            if isinstance(raw, dict) and "value" in raw:
                src = raw.get("source", "")
                url = raw.get("url", "")
                cite = f"[{src}]({url})" if url else src
                lines.append(
                    f"| {field} | {raw['value']} | {raw.get('units', '')} "
                    f"| {cite} (accessed {raw.get('accessed', '?')}) "
                    f"| {raw.get('confidence', '?')} |"
                )
            else:
                lines.append(f"| {field} | {raw} | | | |")
        lines.append("")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    import pathlib
    import sys

    out = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path("docs")
    out.mkdir(parents=True, exist_ok=True)
    target = out / "technology-catalog.md"
    target.write_text(render_provenance_table())
    print(f"wrote {target}")
