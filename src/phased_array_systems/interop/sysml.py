"""Bridge from sysml2kit requirement specs to a RequirementSet.

sysml2kit (the SysML v2 toolkit) extracts machine-checkable requirements
from a model as ``RequirementSpec`` objects carrying ``metric_key``, an
operator-form threshold (``op`` + ``value``), units, and severity — the same
shape as this package's ``Requirement``. This module maps a list of them
(or their ``model_dump()`` dicts, as returned by the sysml2kit MCP tool
``requirements_extract``) into a ``RequirementSet`` ready for
``verify(metrics)``.

sysml2kit is not a dependency: the input is duck-typed, so callers can pass
either the pydantic objects or plain dicts.
"""

from collections.abc import Iterable, Mapping
from typing import Any

from phased_array_systems.requirements.core import Requirement, RequirementSet
from phased_array_systems.types import ComparisonOp, Severity

_OPS: tuple[ComparisonOp, ...] = (">=", "<=", "==", ">", "<")
_SEVERITIES: tuple[Severity, ...] = ("must", "should", "nice")


def _get(spec: Any, key: str) -> Any:
    if isinstance(spec, Mapping):
        return spec.get(key)
    return getattr(spec, key, None)


def requirement_from_spec(spec: Any) -> Requirement:
    """Convert one sysml2kit RequirementSpec (object or dict) to a Requirement.

    Raises ValueError when the spec has no operator-form threshold (a
    requirement without a metricKey threshold cannot be checked here).
    """
    op = _get(spec, "op")
    value = _get(spec, "value")
    if op not in _OPS or value is None:
        raise ValueError(f"spec {_get(spec, 'id')!r} has no operator-form threshold (op={op!r})")
    severity = _get(spec, "severity")
    return Requirement(
        id=str(_get(spec, "id")),
        name=str(_get(spec, "name") or _get(spec, "id")),
        metric_key=str(_get(spec, "metric_key")),
        op=op,
        value=float(value),
        units=_get(spec, "units"),
        severity=severity if severity in _SEVERITIES else "must",
    )


def requirement_set_from_specs(
    specs: Iterable[Any], *, skip_unthresholded: bool = True
) -> RequirementSet:
    """Build a RequirementSet from sysml2kit requirement specs.

    Args:
        specs: RequirementSpec objects or their dict form.
        skip_unthresholded: When True (default), specs without an
            operator-form threshold are skipped; when False they raise.

    Returns:
        A RequirementSet ready for ``verify(metrics)``.
    """
    req_set = RequirementSet()
    for spec in specs:
        try:
            req_set.add(requirement_from_spec(spec))
        except ValueError:
            if not skip_unthresholded:
                raise
    return req_set
