"""Tests for I/O config loading and validation of new fields."""

import pandas as pd
import pytest

from phased_array_systems.io.config_loader import load_config_from_string


class TestConfigLoading:
    """Tests for loading configs with new fields."""

    def test_load_config_with_all_new_fields(self):
        """Load a config with all new array/RF/scenario fields."""
        config_yaml = """
name: "Full Feature Test"
architecture:
  array:
    nx: 8
    ny: 8
    dx_lambda: 0.5
    taper_type: taylor
    taper_sll_db: -25.0
    element_cos_exp: 2.0
    phase_bits: 6
  rf:
    tx_power_w_per_elem: 1.0
    noise_figure_db: 3.0
    rx_stages:
      - name: LNA
        gain_db: 20.0
        nf_db: 1.5
        iip3_dbm: -10.0
      - name: Mixer
        gain_db: 10.0
        nf_db: 8.0
  cost:
    cost_per_elem_usd: 150.0
  reliability:
    operating_temp_c: 95.0
    mttr_hours: 4.0
    mission_hours: 10000.0
scenario:
  type: comms
  freq_hz: 10.0e9
  bandwidth_hz: 10.0e6
  range_m: 50.0e3
  required_snr_db: 10.0
  path_loss_model: fspl
  rain_rate_mmh: 15.0
  elevation_deg: 45.0
"""
        config = load_config_from_string(config_yaml)
        arch = config.get_architecture()

        # Array fields
        assert arch.array.taper_type == "taylor"
        assert arch.array.taper_sll_db == -25.0
        assert arch.array.element_cos_exp == 2.0
        assert arch.array.phase_bits == 6

        # RF cascade stages
        assert arch.rf.rx_stages is not None
        assert len(arch.rf.rx_stages) == 2
        assert arch.rf.rx_stages[0]["name"] == "LNA"
        assert arch.rf.rx_stages[0]["gain_db"] == 20.0

        # Reliability
        assert arch.reliability is not None
        assert arch.reliability.operating_temp_c == 95.0
        assert arch.reliability.mttr_hours == 4.0
        assert arch.reliability.mission_hours == 10000.0

        # Scenario
        scenario = config.get_scenario()
        assert scenario.path_loss_model == "fspl"
        assert scenario.rain_rate_mmh == 15.0
        assert scenario.elevation_deg == 45.0

    def test_load_config_with_only_old_fields(self):
        """Config with only original fields should work with defaults."""
        config_yaml = """
name: "Legacy Config"
architecture:
  array:
    nx: 4
    ny: 4
  rf:
    tx_power_w_per_elem: 0.5
scenario:
  type: comms
  freq_hz: 5.0e9
  bandwidth_hz: 1.0e6
  range_m: 10.0e3
  required_snr_db: 8.0
"""
        config = load_config_from_string(config_yaml)
        arch = config.get_architecture()

        # Defaults should apply
        assert arch.array.taper_type == "uniform"
        assert arch.array.phase_bits is None
        assert arch.array.element_cos_exp == 1.5
        assert arch.rf.rx_stages is None
        assert arch.reliability is None

    def test_invalid_taper_type_raises(self):
        """Invalid taper_type should raise a validation error."""
        config_yaml = """
name: "Bad Taper"
architecture:
  array:
    nx: 8
    ny: 8
    taper_type: invalid_taper
  rf:
    tx_power_w_per_elem: 1.0
"""
        with pytest.raises((ValueError, KeyError)):
            config = load_config_from_string(config_yaml)
            config.get_architecture()

    def test_round_trip_yaml(self, tmp_path):
        """Config -> YAML -> load should preserve values."""
        from phased_array_systems.io.config_loader import save_config

        config_yaml = """
name: "Round Trip Test"
architecture:
  array:
    nx: 16
    ny: 16
    dx_lambda: 0.5
    taper_type: chebyshev
    taper_sll_db: -30.0
    element_cos_exp: 1.0
  rf:
    tx_power_w_per_elem: 2.0
    noise_figure_db: 2.5
    rx_stages:
      - name: LNA
        gain_db: 25.0
        nf_db: 1.0
scenario:
  type: comms
  freq_hz: 28.0e9
  bandwidth_hz: 100.0e6
  range_m: 1.0e3
  required_snr_db: 15.0
  path_loss_model: log_distance
  path_loss_exponent: 3.5
  rain_rate_mmh: 25.0
"""
        config = load_config_from_string(config_yaml)

        # Save to file
        out_path = tmp_path / "roundtrip.yaml"
        save_config(config, out_path)

        # Reload
        from phased_array_systems.io.config_loader import load_config

        config2 = load_config(out_path)
        arch2 = config2.get_architecture()

        assert arch2.array.taper_type == "chebyshev"
        assert arch2.array.taper_sll_db == -30.0
        assert arch2.rf.rx_stages is not None
        assert len(arch2.rf.rx_stages) == 1

        scenario2 = config2.get_scenario()
        assert scenario2.path_loss_model == "log_distance"
        assert scenario2.path_loss_exponent == 3.5
        assert scenario2.rain_rate_mmh == 25.0

    def test_reliability_defaults(self):
        """ReliabilityConfig with defaults should have standard MTBFs."""
        from phased_array_systems.architecture import ReliabilityConfig

        rc = ReliabilityConfig()
        assert "lna" in rc.component_mtbfs
        assert "pa" in rc.component_mtbfs
        assert rc.operating_temp_c == 85.0
        assert rc.mttr_hours == 8.0
        assert rc.mission_hours == 8760.0


class TestExportRoundTrip:
    """Tests for export/import round-trips."""

    @pytest.fixture
    def sample_df(self):
        """Create a sample results DataFrame."""
        return pd.DataFrame(
            {
                "g_peak_db": [30.0, 32.0, 28.0],
                "eirp_dbw": [45.0, 48.0, 42.0],
                "cost_usd": [50000.0, 75000.0, 30000.0],
                "link_margin_db": [5.0, 8.0, 2.0],
                "case_id": ["case_0", "case_1", "case_2"],
            }
        )

    def test_parquet_round_trip(self, tmp_path, sample_df):
        """DataFrame -> export -> load should preserve values."""
        from phased_array_systems.io.exporters import export_results, load_results

        path = tmp_path / "results.parquet"
        export_results(sample_df, path)
        loaded = load_results(path)

        pd.testing.assert_frame_equal(sample_df, loaded)

    def test_csv_round_trip(self, tmp_path, sample_df):
        """CSV round-trip should preserve values."""
        from phased_array_systems.io.exporters import export_results, load_results

        path = tmp_path / "results.csv"
        export_results(sample_df, path)
        loaded = load_results(path)

        pd.testing.assert_frame_equal(sample_df, loaded)

    def test_json_round_trip(self, tmp_path, sample_df):
        """JSON round-trip should preserve values."""
        from phased_array_systems.io.exporters import export_results, load_results

        path = tmp_path / "results.json"
        export_results(sample_df, path)
        loaded = load_results(path)

        pd.testing.assert_frame_equal(sample_df, loaded)

    def test_parquet_metadata(self, tmp_path, sample_df):
        """Parquet export should include metadata in schema."""
        import pyarrow.parquet as pq

        from phased_array_systems.io.exporters import export_results

        path = tmp_path / "results.parquet"
        export_results(sample_df, path, include_metadata=True)

        # Read metadata directly from the parquet file schema
        table = pq.read_table(path)
        meta = table.schema.metadata
        assert meta is not None
        assert b"package_version" in meta
        assert b"export_timestamp" in meta
        assert meta[b"n_cases"] == b"3"

    def test_evaluate_export_report_pipeline(self, tmp_path):
        """Full pipeline: evaluate -> export -> load -> report."""
        from phased_array_systems.architecture import Architecture, ArrayConfig, RFChainConfig
        from phased_array_systems.evaluate import evaluate_case
        from phased_array_systems.io.exporters import export_results, load_results
        from phased_array_systems.reports import HTMLReport, ReportConfig
        from phased_array_systems.scenarios import CommsLinkScenario

        arch = Architecture(
            array=ArrayConfig(nx=8, ny=8),
            rf=RFChainConfig(tx_power_w_per_elem=1.0),
        )
        scenario = CommsLinkScenario(
            freq_hz=10e9, bandwidth_hz=10e6, range_m=100e3, required_snr_db=10.0
        )
        metrics = evaluate_case(arch, scenario)

        df = pd.DataFrame([metrics])
        parquet_path = tmp_path / "results.parquet"
        export_results(df, parquet_path)

        loaded = load_results(parquet_path)
        assert len(loaded) == 1

        report = HTMLReport(ReportConfig(title="Pipeline Test"))
        html = report.generate(loaded)
        assert "<html" in html

    def test_export_nan_values(self, tmp_path):
        """NaN/inf values should not crash export."""
        from phased_array_systems.io.exporters import export_results, load_results

        df = pd.DataFrame(
            {
                "metric_a": [1.0, float("nan"), 3.0],
                "metric_b": [float("inf"), 2.0, float("-inf")],
            }
        )

        for fmt in ["parquet", "csv", "json"]:
            path = tmp_path / f"results.{fmt}"
            export_results(df, path)
            loaded = load_results(path)
            assert len(loaded) == 3

    def test_export_empty_dataframe(self, tmp_path):
        """Empty DataFrame should be handled gracefully."""
        from phased_array_systems.io.exporters import export_results, load_results

        df = pd.DataFrame()

        # Parquet and JSON handle empty DataFrames
        for fmt in ["parquet", "json"]:
            path = tmp_path / f"empty.{fmt}"
            export_results(df, path)
            loaded = load_results(path)
            assert len(loaded) == 0
