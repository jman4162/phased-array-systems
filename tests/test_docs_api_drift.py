"""Guards against documentation drifting away from the API it documents.

Every stale name this catches was real: the radar user guide, the scenario
reference table, three API pages and a tutorial all described a constructor
that had not existed for several releases (`target_rcs_m2`, `required_pd`,
`pulse_width_s`, `swerling_model`), named a class that was never exported
(`RadarEquationModel`), and called a function under the wrong name
(`compute_required_snr`). Three shipped configs set `system_loss_db` inside
their scenario block, where it belongs to `RFChainConfig` and was silently
discarded.

These tests read the documentation and the example configs as data and check
every keyword they use against the live models, so the next rename fails CI
rather than shipping.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest
import yaml

from phased_array_systems.scenarios import CommsLinkScenario, RadarDetectionScenario

REPO = Path(__file__).resolve().parent.parent
DOCS = REPO / "docs"
CONFIGS = REPO / "examples" / "configs"

SCENARIOS = {
    "RadarDetectionScenario": RadarDetectionScenario,
    "CommsLinkScenario": CommsLinkScenario,
}


def _allowed(model) -> set[str]:
    """Constructor keywords a model accepts."""
    return set(model.model_fields)


def _python_blocks(path: Path) -> list[str]:
    return re.findall(r"```python\n(.*?)```", path.read_text(), re.S)


def _iter_doc_files():
    return sorted(DOCS.rglob("*.md"))


def _constructor_kwargs(source: str, class_name: str) -> list[tuple[str, int]]:
    """Keyword names passed to `class_name(...)` in a code block.

    Parsed with `ast` rather than by regex so nested calls and multi-line
    argument lists are handled correctly. Blocks that do not parse (they use
    `...` as an illustrative placeholder) are skipped by the caller.
    """
    tree = ast.parse(source)
    found: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = getattr(func, "id", None) or getattr(func, "attr", None)
        if name != class_name:
            continue
        for kw in node.keywords:
            if kw.arg is not None:
                found.append((kw.arg, node.lineno))
    return found


@pytest.mark.parametrize("doc", _iter_doc_files(), ids=lambda p: str(p.relative_to(DOCS)))
def test_documented_scenario_kwargs_exist(doc):
    """Every scenario keyword shown in the docs must be a real model field."""
    bad: list[str] = []
    for block in _python_blocks(doc):
        try:
            ast.parse(block)
        except SyntaxError:
            continue  # illustrative fragment, not runnable code
        for class_name, model in SCENARIOS.items():
            allowed = _allowed(model)
            for kwarg, lineno in _constructor_kwargs(block, class_name):
                if kwarg not in allowed:
                    bad.append(f"{class_name}(..., {kwarg}=...) at block line {lineno}")
    assert not bad, f"{doc.relative_to(REPO)} documents fields that do not exist: {bad}"


@pytest.mark.parametrize("doc", _iter_doc_files(), ids=lambda p: str(p.relative_to(DOCS)))
def test_documented_python_blocks_parse(doc):
    """Runnable-looking blocks must at least be syntactically valid Python.

    Blocks using `...` as a placeholder are exempt, since they are prose.
    """
    for i, block in enumerate(_python_blocks(doc), 1):
        if "..." in block:
            continue
        try:
            ast.parse(block)
        except SyntaxError as exc:
            pytest.fail(f"{doc.relative_to(REPO)} block {i} is not valid Python: {exc}")


@pytest.mark.parametrize("cfg", sorted(CONFIGS.glob("*.yaml")), ids=lambda p: p.name)
def test_config_scenario_keys_are_real_fields(cfg):
    """A scenario key that no model accepts is silently dropped, so forbid it.

    `system_loss_db` sat in three radar configs asserting two decibels of loss
    that never reached the radar equation; it belongs to `RFChainConfig`.
    """
    data = yaml.safe_load(cfg.read_text()) or {}
    scenario = data.get("scenario")
    if not scenario:
        pytest.skip("no scenario block")
    kind = scenario.get("type")
    model = {"radar": RadarDetectionScenario, "comms": CommsLinkScenario}.get(kind)
    if model is None:
        pytest.skip(f"unknown scenario type {kind!r}")
    unknown = set(scenario) - _allowed(model) - {"type"}
    assert not unknown, (
        f"{cfg.name} sets scenario keys that are not model fields: {sorted(unknown)}"
    )


def test_unknown_scenario_fields_are_rejected():
    """The models forbid extras, so a typo fails loudly instead of vanishing."""
    with pytest.raises(Exception) as exc:
        RadarDetectionScenario(
            freq_hz=10e9,
            bandwidth_hz=1e6,
            range_m=100e3,
            target_rcs_dbsm=0.0,
            system_loss_db=2.0,  # belongs on RFChainConfig
        )
    assert "system_loss_db" in str(exc.value)


def test_renamed_fields_stay_renamed():
    """Names that appeared in old documentation must not silently come back."""
    retired = {"target_rcs_m2", "required_pd", "pulse_width_s", "swerling_model"}
    live = _allowed(RadarDetectionScenario)
    assert not (retired & live), f"a retired name is a constructor field again: {retired & live}"
    # target_rcs_m2 remains valid as a derived read-only property.
    assert "target_rcs_m2" in RadarDetectionScenario.model_computed_fields
