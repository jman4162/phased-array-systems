"""Tests for I/O config loading and validation of new fields."""

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
