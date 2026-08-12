"""T/R module description and derivation of RF chain aggregates.

A :class:`~phased_array_systems.architecture.TRModuleConfig` describes one
transmit/receive module as two component chains (TX and RX) in signal-flow
order. The same component list feeds three places:

- RF: the chains become ``tx_stages`` / ``rx_stages`` and the composite
  receive noise figure via the existing cascade math
- Power: per-element DC power is the sum of component ``dc_power_w``
- Reliability: component names match the vocabulary of
  ``ReliabilityConfig.component_mtbfs`` (lna, pa, phase_shifter, attenuator,
  switch, control_asic), so one module description drives ``trm_mtbf``

Derivation only fills RF-chain fields the user did not set explicitly; an
explicit value always overrides the derived one.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from phased_array_systems.models.rf.cascade import RFStage, cascade_p1db, friis_noise_figure

if TYPE_CHECKING:
    from phased_array_systems.architecture.config import (
        RFChainConfig,
        TRComponent,
        TRModuleConfig,
    )

# Component names understood by ReliabilityConfig.component_mtbfs
KNOWN_COMPONENT_NAMES = frozenset(
    {"lna", "pa", "phase_shifter", "attenuator", "switch", "control_asic"}
)


def chain_to_stages(chain: list[TRComponent]) -> list[dict[str, float | str]]:
    """Convert TRComponent list to the rx_stages/tx_stages dict shape."""
    return [
        {
            "name": c.name,
            "gain_db": c.gain_db,
            "nf_db": c.noise_figure_db,
            "iip3_dbm": c.iip3_dbm,
            "p1db_dbm": c.p1db_dbm,
        }
        for c in chain
    ]


def chain_noise_figure_db(chain: list[TRComponent]) -> float:
    """Composite noise figure of a component chain (Friis)."""
    if not chain:
        return 0.0
    pairs = [(c.gain_db, c.noise_figure_db) for c in chain]
    return float(friis_noise_figure(pairs)["total_nf_db"])


def chain_dc_power_w(chain: list[TRComponent]) -> float:
    """Total DC power of a component chain (W)."""
    return float(sum(c.dc_power_w for c in chain))


def chain_op1db_dbm(chain: list[TRComponent]) -> float:
    """Cascaded output-referred P1dB of a component chain (dBm)."""
    pairs = [(c.gain_db, c.p1db_dbm) for c in chain]
    return float(cascade_p1db(pairs)["op1db_dbm"])


def chain_rf_stages(chain: list[TRComponent]) -> list[RFStage]:
    """Convert TRComponent list to RFStage objects."""
    return [
        RFStage(
            name=c.name,
            gain_db=c.gain_db,
            noise_figure_db=c.noise_figure_db,
            iip3_dbm=c.iip3_dbm,
            p1db_dbm=c.p1db_dbm,
        )
        for c in chain
    ]


def apply_technology_defaults(trm: TRModuleConfig) -> TRModuleConfig:
    """Fill component parameters a technology choice implies.

    For a TRM with ``technology`` set, components still carrying their
    field defaults get catalog midpoints: an ``lna``'s noise figure and
    IIP3, and a ``pa``'s P1dB (from the catalog's saturated power class —
    an optimistic upper bound, documented in the catalog). A value the
    user set explicitly (pydantic ``model_fields_set``) is never touched.
    Returns a new TRModuleConfig; the input is not mutated.
    """
    if trm.technology is None:
        return trm
    from phased_array_systems.models.rf.technology import technology_defaults

    defaults = technology_defaults(trm.technology)

    def fill(component):  # type: ignore[no-untyped-def]
        explicit = component.model_fields_set
        updates = {}
        if component.name == "lna":
            if "noise_figure_db" not in explicit and "lna_nf_db" in defaults:
                updates["noise_figure_db"] = defaults["lna_nf_db"]
            if "iip3_dbm" not in explicit and "lna_iip3_dbm" in defaults:
                updates["iip3_dbm"] = defaults["lna_iip3_dbm"]
        if (
            component.name == "pa"
            and "p1db_dbm" not in explicit
            and "pa_p1db_dbm" in defaults
        ):
            updates["p1db_dbm"] = defaults["pa_p1db_dbm"]
        return component.model_copy(update=updates) if updates else component

    return trm.model_copy(
        update={
            "tx_chain": [fill(c) for c in trm.tx_chain],
            "rx_chain": [fill(c) for c in trm.rx_chain],
        }
    )


def derive_rf_chain_fields(trm: TRModuleConfig, rf: RFChainConfig) -> dict[str, object]:
    """Fields of RFChainConfig that a T/R module description implies.

    Returns only the fields to *fill in*: a field the user set explicitly on
    the RF chain (tracked by pydantic's ``model_fields_set``) is left alone.

    Derived fields:
        - ``rx_stages`` / ``tx_stages`` from the component chains
        - ``noise_figure_db``: composite RX noise figure (Friis)
        - ``rx_power_w_per_elem``: RX-chain DC power sum
        - ``pa_op1db_dbm_per_elem``: cascaded TX output P1dB, which arms the
          Rapp compression model in the link budget
    """
    explicit = rf.model_fields_set
    derived: dict[str, object] = {}

    if trm.rx_chain:
        if "rx_stages" not in explicit:
            derived["rx_stages"] = chain_to_stages(trm.rx_chain)
        if "noise_figure_db" not in explicit:
            derived["noise_figure_db"] = chain_noise_figure_db(trm.rx_chain)
        if "rx_power_w_per_elem" not in explicit:
            derived["rx_power_w_per_elem"] = chain_dc_power_w(trm.rx_chain)

    if trm.tx_chain:
        if "tx_stages" not in explicit:
            derived["tx_stages"] = chain_to_stages(trm.tx_chain)
        if "pa_op1db_dbm_per_elem" not in explicit:
            derived["pa_op1db_dbm_per_elem"] = chain_op1db_dbm(trm.tx_chain)

    return derived
