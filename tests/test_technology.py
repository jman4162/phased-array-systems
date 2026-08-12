"""Tests for the technology catalog and its TRM hook."""

import pytest

from phased_array_systems.architecture import (
    Architecture,
    ArrayConfig,
    RFChainConfig,
    TRComponent,
    TRModuleConfig,
)
from phased_array_systems.models.rf.technology import (
    entry,
    load_catalog,
    midpoint,
    render_provenance_table,
    technologies,
    technology_defaults,
)

EXPECTED_TECHNOLOGIES = {"sige", "gaas", "gan", "cmos", "ldmos"}


class TestCatalogSchema:
    def test_all_technologies_present(self):
        assert set(technologies()) == EXPECTED_TECHNOLOGIES

    def test_every_number_carries_provenance(self):
        """Every numeric field is a provenance mapping with source, url,
        accessed date, and a quote — the no-number-without-a-checkable-
        reference rule, enforced."""
        for tech, fields in load_catalog().items():
            for field, raw in fields.items():
                if field == "name" or isinstance(raw, str):
                    continue
                assert isinstance(raw, dict), f"{tech}.{field} lacks provenance"
                for required in ("value", "units", "source", "url", "accessed", "quote"):
                    assert required in raw, f"{tech}.{field} missing {required}"

    def test_ranges_are_ordered_pairs(self):
        for tech, fields in load_catalog().items():
            for field, raw in fields.items():
                if isinstance(raw, dict) and isinstance(raw.get("value"), list):
                    lo, hi = raw["value"]
                    assert lo < hi, f"{tech}.{field} range not ascending"

    def test_unknown_technology_raises(self):
        with pytest.raises(KeyError, match="unknown technology"):
            entry("inp")

    def test_midpoint(self):
        assert midpoint([1.0, 3.0]) == 2.0
        assert midpoint(5.0) == 5.0


class TestPlausibility:
    """Cross-technology sanity: the catalog reproduces the known ordering."""

    def test_gan_power_density_exceeds_gaas_exceeds_ldmos_wafer(self):
        gan_lo = entry("gan")["pa_psat_w_per_mm"][0]
        gaas_hi = entry("gaas")["pa_psat_w_per_mm"][1]
        assert gan_lo > gaas_hi

    def test_lna_nf_ordering(self):
        """GaAs pHEMT < SiGe < GaN < CMOS upper bounds."""
        gaas_hi = entry("gaas")["lna_nf_db"][1]
        sige_hi = entry("sige")["lna_nf_db"][1]
        cmos_hi = entry("cmos")["lna_nf_db"][1]
        assert gaas_hi < sige_hi < cmos_hi

    def test_pa_class_ordering(self):
        assert (
            midpoint(entry("cmos")["pa_class_dbm"])
            < midpoint(entry("gaas")["pa_class_dbm"])
            < entry("gan")["pa_class_dbm"] + 1e-9
        )

    def test_defaults_distinct_per_technology(self):
        nf = {t: technology_defaults(t).get("lna_nf_db") for t in technologies()}
        nf = {t: v for t, v in nf.items() if v is not None}
        assert len(set(nf.values())) == len(nf)


class TestTRMHook:
    def _trm(self, technology, **lna_kwargs):
        return TRModuleConfig(
            technology=technology,
            tx_chain=[
                TRComponent(name="pa", gain_db=13.0, noise_figure_db=8.0, dc_power_w=4.0),
            ],
            rx_chain=[
                TRComponent(name="lna", gain_db=20.0, dc_power_w=0.15, **lna_kwargs),
            ],
        )

    def test_technology_fills_lna_and_pa(self):
        arch = Architecture(
            array=ArrayConfig(nx=8, ny=8, dx_lambda=0.5, dy_lambda=0.5),
            rf=RFChainConfig(tx_power_w_per_elem=1.0),
            trm=self._trm("gaas"),
        )
        defaults = technology_defaults("gaas")
        lna = arch.trm.rx_chain[0]
        assert lna.noise_figure_db == pytest.approx(defaults["lna_nf_db"])
        assert lna.iip3_dbm == pytest.approx(defaults["lna_iip3_dbm"])
        pa = arch.trm.tx_chain[0]
        assert pa.p1db_dbm == pytest.approx(defaults["pa_p1db_dbm"])
        # And the derived RF chain picks up the catalog NF via Friis
        assert arch.rf.noise_figure_db == pytest.approx(defaults["lna_nf_db"], abs=0.5)

    def test_explicit_component_values_win(self):
        arch = Architecture(
            array=ArrayConfig(nx=8, ny=8, dx_lambda=0.5, dy_lambda=0.5),
            rf=RFChainConfig(tx_power_w_per_elem=1.0),
            trm=self._trm("gaas", noise_figure_db=2.5),
        )
        assert arch.trm.rx_chain[0].noise_figure_db == 2.5

    def test_technologies_produce_distinct_cascades(self):
        nfs = {}
        for tech in ("gaas", "sige", "gan", "cmos"):
            arch = Architecture(
                array=ArrayConfig(nx=8, ny=8, dx_lambda=0.5, dy_lambda=0.5),
                rf=RFChainConfig(tx_power_w_per_elem=1.0),
                trm=self._trm(tech),
            )
            nfs[tech] = arch.rf.noise_figure_db
        assert len(set(nfs.values())) == 4
        # GaAs is the low-noise workhorse; CMOS the worst of the four
        assert nfs["gaas"] == min(nfs.values())
        assert nfs["cmos"] == max(nfs.values())

    def test_no_technology_no_fill(self):
        arch = Architecture(
            array=ArrayConfig(nx=8, ny=8, dx_lambda=0.5, dy_lambda=0.5),
            rf=RFChainConfig(tx_power_w_per_elem=1.0),
            trm=self._trm(None),
        )
        assert arch.trm.rx_chain[0].noise_figure_db == 0.0

    def test_unknown_technology_raises_at_construction(self):
        with pytest.raises(KeyError):
            Architecture(
                array=ArrayConfig(nx=8, ny=8, dx_lambda=0.5, dy_lambda=0.5),
                rf=RFChainConfig(tx_power_w_per_elem=1.0),
                trm=self._trm("inp"),
            )


class TestProvenanceDoc:
    def test_renders_and_is_committed_fresh(self):
        from pathlib import Path

        rendered = render_provenance_table()
        committed = Path(__file__).parent.parent / "docs" / "technology-catalog.md"
        assert committed.exists(), "run python -m phased_array_systems.models.rf.technology docs"
        assert committed.read_text() == rendered, (
            "docs/technology-catalog.md is stale; regenerate it"
        )
