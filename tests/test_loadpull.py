"""Tests for the load-pull model and EdgeFEM scan-CSV ingestion."""

from pathlib import Path

import numpy as np
import pytest

from phased_array_systems.models.rf.loadpull import (
    SCAN_CSV_COLUMNS,
    LoadPullModel,
    LoadPullTable,
    eirp_vs_scan,
    load_scan_csv,
)

FIXTURE = Path(__file__).parent / "fixtures" / "edgefem" / "golden_scan.csv"


class TestLoadPullModel:
    def test_no_degradation_at_optimum(self):
        model = LoadPullModel(gamma_opt=0.2 + 0.1j)
        r = model.evaluate(0.2 + 0.1j)
        assert r.pout_drop_db == 0.0
        assert r.pae_drop_pct == 0.0
        assert r.ampm_deg == 0.0

    def test_monotonic_in_mismatch(self):
        model = LoadPullModel(gamma_opt=0.0)
        drops = [model.evaluate(g).pout_drop_db for g in (0.1, 0.2, 0.3, 0.5)]
        assert all(b > a for a, b in zip(drops, drops[1:], strict=False))

    def test_hand_value_circular(self):
        """Circular contours, sensitivity 10 dB: drop at |dGamma|=0.3 is
        10 * 0.09 = 0.9 dB."""
        model = LoadPullModel(gamma_opt=0.0, pout_sensitivity_db=10.0)
        assert model.evaluate(0.3).pout_drop_db == pytest.approx(0.9)
        assert model.evaluate(0.3j).pout_drop_db == pytest.approx(0.9)

    def test_elliptical_contours(self):
        """Axial ratio 2, no rotation: an imaginary-axis mismatch counts
        double, so it degrades 4x in the quadratic."""
        model = LoadPullModel(gamma_opt=0.0, pout_sensitivity_db=10.0, contour_axial_ratio=2.0)
        real_drop = model.evaluate(0.2).pout_drop_db
        imag_drop = model.evaluate(0.2j).pout_drop_db
        assert imag_drop == pytest.approx(4.0 * real_drop)

    def test_rotation_moves_the_easy_axis(self):
        """Rotating the ellipse 90 deg swaps which axis is penalized."""
        model = LoadPullModel(
            gamma_opt=0.0,
            pout_sensitivity_db=10.0,
            contour_axial_ratio=2.0,
            contour_rotation_deg=90.0,
        )
        assert model.evaluate(0.2j).pout_drop_db == pytest.approx(
            LoadPullModel(gamma_opt=0.0, pout_sensitivity_db=10.0, contour_axial_ratio=2.0)
            .evaluate(0.2)
            .pout_drop_db
        )

    def test_gamma_opt_outside_unit_circle_rejected(self):
        with pytest.raises(ValueError):
            LoadPullModel(gamma_opt=1.2)


class TestLoadPullTable:
    def _table(self, tmp_path):
        csv_path = tmp_path / "lp.csv"
        csv_path.write_text(
            "Gamma_real,Gamma_imag,pout_drop_db,pae_drop_pct,ampm_deg\n"
            "0.0,0.0,0.0,0.0,0.0\n"
            "0.4,0.0,1.0,5.0,3.0\n"
            "-0.4,0.0,1.2,6.0,-3.0\n"
            "0.0,0.4,0.8,4.0,2.0\n"
            "0.0,-0.4,0.8,4.0,-2.0\n"
        )
        return LoadPullTable.from_csv(csv_path)

    def test_exact_point_returns_row(self, tmp_path):
        table = self._table(tmp_path)
        r = table.evaluate(0.4 + 0.0j)
        assert r.pout_drop_db == 1.0
        assert r.pae_drop_pct == 5.0
        assert r.ampm_deg == 3.0

    def test_interpolation_bounded_by_neighbors(self, tmp_path):
        table = self._table(tmp_path)
        r = table.evaluate(0.2 + 0.0j)
        assert 0.0 < r.pout_drop_db < 1.2

    def test_wrong_columns_rejected(self, tmp_path):
        bad = tmp_path / "bad.csv"
        bad.write_text("a,b\n1,2\n")
        with pytest.raises(ValueError, match="columns"):
            LoadPullTable.from_csv(bad)


class TestScanCsvContract:
    """Pins the EdgeFEM export_scan_csv format via the vendored golden
    fixture (contract revision 2). If these fail after a refresh, EdgeFEM
    changed the format; do not silently adapt."""

    def test_fixture_exists(self):
        assert FIXTURE.exists()

    def test_columns(self):
        header = FIXTURE.read_text().splitlines()[0]
        assert header.split(",") == SCAN_CSV_COLUMNS

    def test_scan_angles_and_shape(self):
        scan = load_scan_csv(FIXTURE)
        assert [(p.theta_deg, p.phi_deg) for p in scan] == [
            (0.0, 0.0),
            (30.0, 0.0),
            (60.0, 0.0),
        ]
        assert all(len(p.gamma) == 4 for p in scan)

    def test_hand_computed_vswr_row(self):
        """Element 0 at 60 deg: Gamma exactly 0.5 -> VSWR 3, Z 150 ohm."""
        scan = load_scan_csv(FIXTURE)
        p60 = scan[2]
        assert p60.gamma[0] == pytest.approx(0.5 + 0.0j, abs=1e-9)
        assert p60.vswr[0] == pytest.approx(3.0, abs=1e-9)
        assert p60.z_ohm[0] == pytest.approx(150.0 + 0.0j, abs=1e-6)

    def test_gamma_z_consistency(self):
        """Z = Z0 (1 + Gamma)/(1 - Gamma) at 50 ohms, every row."""
        for point in load_scan_csv(FIXTURE):
            expected = 50.0 * (1 + point.gamma) / (1 - point.gamma)
            np.testing.assert_allclose(point.z_ohm, expected, atol=1e-6)

    def test_vswr_consistency(self):
        for point in load_scan_csv(FIXTURE):
            mag = np.abs(point.gamma)
            np.testing.assert_allclose(point.vswr, (1 + mag) / (1 - mag), rtol=1e-9)


class TestEirpVsScan:
    def test_matched_pa_stays_flat(self):
        """A PA matched to each element's broadside load barely degrades at
        broadside and the sweep is monotone-worse off broadside for a
        mismatched one."""
        scan = load_scan_csv(FIXTURE)
        # Matched to the exact broadside Gamma of element 0
        matched = LoadPullModel(gamma_opt=0.1 + 0.0j, pout_sensitivity_db=10.0)
        rows = eirp_vs_scan(scan, matched)
        assert rows[0]["eirp_delta_db"] == pytest.approx(0.0, abs=0.01)
        # Off broadside the active impedance moves away: worse EIRP
        assert rows[2]["eirp_delta_db"] < rows[1]["eirp_delta_db"] < rows[0]["eirp_delta_db"]

    def test_mismatched_pa_worsens_off_broadside(self):
        scan = load_scan_csv(FIXTURE)
        model = LoadPullModel(gamma_opt=0.0, pout_sensitivity_db=10.0)
        rows = eirp_vs_scan(scan, model)
        deltas = [r["eirp_delta_db"] for r in rows]
        assert deltas[2] < deltas[1] < deltas[0] <= 0.0

    def test_worst_vswr_reported(self):
        scan = load_scan_csv(FIXTURE)
        rows = eirp_vs_scan(scan, LoadPullModel())
        assert rows[2]["worst_vswr"] == pytest.approx(3.0, abs=1e-9)

    def test_eirp_delta_hand_value(self):
        """Uniform drop d on every element gives eirp_delta = -d exactly."""
        scan = load_scan_csv(FIXTURE)
        p0 = scan[0]

        class UniformDrop:
            def evaluate(self, gamma):
                from phased_array_systems.models.rf.loadpull import LoadPullResult

                return LoadPullResult(pout_drop_db=2.0, pae_drop_pct=0.0, ampm_deg=0.0)

        rows = eirp_vs_scan([p0], UniformDrop())
        assert rows[0]["eirp_delta_db"] == pytest.approx(-2.0, abs=1e-12)
        assert rows[0]["mean_pout_drop_db"] == pytest.approx(2.0)
