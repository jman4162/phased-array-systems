"""Tests for the T/R module abstraction."""

import pytest

from phased_array_systems.architecture import (
    Architecture,
    ArrayConfig,
    CostConfig,
    ReliabilityConfig,
    RFChainConfig,
    TRComponent,
    TRModuleConfig,
)
from phased_array_systems.evaluate import evaluate_case
from phased_array_systems.models.rf.trm import (
    KNOWN_COMPONENT_NAMES,
    chain_dc_power_w,
    chain_noise_figure_db,
    chain_op1db_dbm,
    chain_to_stages,
)
from phased_array_systems.scenarios import CommsLinkScenario

RX_CHAIN = [
    TRComponent(name="lna", gain_db=20.0, noise_figure_db=1.5, iip3_dbm=-5.0, dc_power_w=0.15),
    TRComponent(name="phase_shifter", gain_db=-3.0, noise_figure_db=3.0, dc_power_w=0.02),
    TRComponent(name="attenuator", gain_db=-1.0, noise_figure_db=1.0, dc_power_w=0.03),
]

TX_CHAIN = [
    TRComponent(name="phase_shifter", gain_db=-3.0, noise_figure_db=3.0, dc_power_w=0.02),
    TRComponent(name="driver", gain_db=20.0, noise_figure_db=5.0, p1db_dbm=5.0, dc_power_w=0.5),
    TRComponent(name="pa", gain_db=13.0, noise_figure_db=8.0, p1db_dbm=20.0, dc_power_w=8.0),
]


class TestChainHelpers:
    def test_stages_shape(self):
        stages = chain_to_stages(RX_CHAIN)
        assert stages[0] == {
            "name": "lna",
            "gain_db": 20.0,
            "nf_db": 1.5,
            "iip3_dbm": -5.0,
            "p1db_dbm": 100.0,
        }

    def test_composite_nf_matches_friis(self):
        """Hand check: LNA dominates; NF between LNA's 1.5 and 2.5 dB."""
        nf = chain_noise_figure_db(RX_CHAIN)
        assert 1.5 < nf < 2.5

    def test_dc_power_sum(self):
        assert chain_dc_power_w(RX_CHAIN) == pytest.approx(0.20)

    def test_tx_op1db(self):
        """Cascaded OP1dB is bounded by the PA's own OP1dB (33 dBm)."""
        op1db = chain_op1db_dbm(TX_CHAIN)
        assert op1db < 33.0
        assert op1db > 25.0


class TestTRMDerivation:
    def _arch(self, **rf_kwargs):
        return Architecture(
            array=ArrayConfig(nx=8, ny=8, dx_lambda=0.5, dy_lambda=0.5),
            rf=RFChainConfig(tx_power_w_per_elem=1.0, **rf_kwargs),
            cost=CostConfig(cost_per_elem_usd=100.0),
            trm=TRModuleConfig(tx_chain=TX_CHAIN, rx_chain=RX_CHAIN),
        )

    def test_derives_stages_and_aggregates(self):
        arch = self._arch()
        assert arch.rf.rx_stages is not None
        assert [s["name"] for s in arch.rf.rx_stages] == ["lna", "phase_shifter", "attenuator"]
        assert arch.rf.tx_stages is not None
        assert arch.rf.noise_figure_db == pytest.approx(chain_noise_figure_db(RX_CHAIN))
        assert arch.rf.rx_power_w_per_elem == pytest.approx(0.20)
        assert arch.rf.pa_op1db_dbm_per_elem == pytest.approx(chain_op1db_dbm(TX_CHAIN))

    def test_explicit_rf_fields_override(self):
        arch = self._arch(noise_figure_db=9.0, rx_power_w_per_elem=0.7)
        assert arch.rf.noise_figure_db == 9.0
        assert arch.rf.rx_power_w_per_elem == 0.7
        # Non-explicit fields still derived
        assert arch.rf.rx_stages is not None

    def test_no_trm_no_change(self):
        arch = Architecture(
            array=ArrayConfig(nx=8, ny=8, dx_lambda=0.5, dy_lambda=0.5),
            rf=RFChainConfig(tx_power_w_per_elem=1.0),
        )
        assert arch.rf.rx_stages is None
        assert arch.rf.noise_figure_db == 3.0


class TestTRMEquivalence:
    """A TRM whose chains reproduce explicit aggregates gives identical metrics."""

    SCENARIO = CommsLinkScenario(
        freq_hz=10e9,
        bandwidth_hz=10e6,
        range_m=100e3,
        required_snr_db=10.0,
    )

    def test_metrics_identical(self):
        explicit = Architecture(
            array=ArrayConfig(nx=8, ny=8, dx_lambda=0.5, dy_lambda=0.5),
            rf=RFChainConfig(
                tx_power_w_per_elem=1.0,
                noise_figure_db=chain_noise_figure_db(RX_CHAIN),
                rx_power_w_per_elem=chain_dc_power_w(RX_CHAIN),
                rx_stages=chain_to_stages(RX_CHAIN),
                tx_stages=chain_to_stages(TX_CHAIN),
                pa_op1db_dbm_per_elem=chain_op1db_dbm(TX_CHAIN),
            ),
            cost=CostConfig(cost_per_elem_usd=100.0),
        )
        via_trm = Architecture(
            array=ArrayConfig(nx=8, ny=8, dx_lambda=0.5, dy_lambda=0.5),
            rf=RFChainConfig(tx_power_w_per_elem=1.0),
            cost=CostConfig(cost_per_elem_usd=100.0),
            trm=TRModuleConfig(tx_chain=TX_CHAIN, rx_chain=RX_CHAIN),
        )
        m_explicit = evaluate_case(explicit, self.SCENARIO)
        m_trm = evaluate_case(via_trm, self.SCENARIO)
        for key, value in m_explicit.items():
            if key.startswith("meta."):
                continue
            assert m_trm[key] == value, f"metric {key} differs"


class TestReliabilityVocabulary:
    def test_default_mtbf_names_are_known(self):
        assert set(ReliabilityConfig().component_mtbfs) == set(KNOWN_COMPONENT_NAMES)

    def test_trm_names_feed_reliability(self):
        """The TRM component names map onto the MTBF vocabulary (driver is
        the one deliberate extra: it prices as a second amplifier stage in
        RF terms but has no dedicated MTBF entry)."""
        trm = TRModuleConfig(tx_chain=TX_CHAIN, rx_chain=RX_CHAIN)
        unknown = trm.component_names - KNOWN_COMPONENT_NAMES
        assert unknown == {"driver"}


class TestFlatRoundTrip:
    def test_flat_dump_includes_trm(self):
        arch = Architecture(
            array=ArrayConfig(nx=8, ny=8, dx_lambda=0.5, dy_lambda=0.5),
            rf=RFChainConfig(tx_power_w_per_elem=1.0),
            trm=TRModuleConfig(tx_chain=TX_CHAIN, rx_chain=RX_CHAIN),
        )
        flat = arch.model_dump_flat()
        assert "trm.tx_chain" in flat
        rebuilt = Architecture.from_flat(flat)
        assert rebuilt.trm is not None
        assert rebuilt.trm.component_names == arch.trm.component_names
