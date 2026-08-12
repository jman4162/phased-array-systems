"""Tests for RF cascade model functions."""

import math

import pytest

from phased_array_systems.models.rf.cascade import (
    RFStage,
    cascade_analysis,
    cascade_gain,
    cascade_gain_db,
    cascade_iip3,
    cascade_oip3,
    friis_noise_figure,
    mds_from_noise_figure,
    noise_figure_to_temp,
    noise_temp_to_figure,
    sfdr_from_iip3,
    sfdr_from_oip3,
    system_noise_temperature,
)


class TestNoiseFigureConversion:
    """Tests for NF <-> noise temperature conversions."""

    def test_nf_0db_gives_0K(self):
        """0 dB NF = 0 K noise temperature."""
        assert noise_figure_to_temp(0.0) == pytest.approx(0.0, abs=0.01)

    def test_nf_3db_gives_290K(self):
        """3 dB NF ~ 290 K (doubles noise power)."""
        te = noise_figure_to_temp(3.0)
        assert te == pytest.approx(290.0, rel=0.02)

    def test_roundtrip_nf_to_temp_to_nf(self):
        """NF -> temp -> NF should be identity."""
        original_nf = 5.0
        te = noise_figure_to_temp(original_nf)
        recovered_nf = noise_temp_to_figure(te)
        assert recovered_nf == pytest.approx(original_nf, rel=1e-6)


class TestFriisNoiseFigure:
    """Tests for Friis cascaded noise figure."""

    def test_single_stage(self):
        """Single stage should return its own NF."""
        result = friis_noise_figure([(20.0, 3.0)])
        assert result["total_nf_db"] == pytest.approx(3.0, rel=1e-6)
        assert result["total_gain_db"] == pytest.approx(20.0, rel=1e-6)

    def test_lna_dominates(self):
        """High-gain LNA should dominate cascaded NF."""
        # LNA: 20 dB gain, 1 dB NF; Mixer: -6 dB gain, 8 dB NF
        stages = [(20.0, 1.0), (-6.0, 8.0)]
        result = friis_noise_figure(stages)
        # With 20 dB gain in front, second stage contribution is small
        assert result["total_nf_db"] < 2.0

    def test_empty_stages(self):
        """Empty stage list should return zeros."""
        result = friis_noise_figure([])
        assert result["total_nf_db"] == 0.0
        assert result["total_gain_db"] == 0.0

    def test_three_stage_receiver(self):
        """Typical 3-stage receiver chain."""
        # LNA (20dB, 1.5dB), Filter (-3dB, 3dB), IF Amp (30dB, 6dB)
        stages = [(20.0, 1.5), (-3.0, 3.0), (30.0, 6.0)]
        result = friis_noise_figure(stages)
        # Total gain = 20 - 3 + 30 = 47 dB
        assert result["total_gain_db"] == pytest.approx(47.0, rel=1e-6)
        # NF dominated by LNA, should be close to 1.5 dB
        assert result["total_nf_db"] < 3.0
        assert result["total_nf_db"] > 1.5


class TestCascadeGain:
    """Tests for cascade gain calculations."""

    def test_cascade_gain_sum(self):
        """Cascade gain is sum in dB."""
        assert cascade_gain([10.0, -3.0, 20.0]) == pytest.approx(27.0)

    def test_cascade_gain_db_from_tuples(self):
        """cascade_gain_db extracts and sums gains from tuples."""
        stages = [(10.0, 3.0), (-3.0, 6.0), (20.0, 4.0)]
        assert cascade_gain_db(stages) == pytest.approx(27.0)


class TestCascadeIIP3:
    """Tests for cascaded IIP3 calculations."""

    def test_single_stage_iip3(self):
        """Single stage IIP3 should pass through."""
        result = cascade_iip3([(10.0, 5.0)])
        assert result["iip3_dbm"] == pytest.approx(5.0, rel=1e-6)
        assert result["oip3_dbm"] == pytest.approx(15.0, rel=1e-6)

    def test_high_gain_degrades_iip3(self):
        """High gain before a nonlinear stage degrades system IIP3."""
        # High-gain LNA (30dB, IIP3=0dBm) before mixer (0dB, IIP3=10dBm)
        result_with_gain = cascade_iip3([(30.0, 0.0), (0.0, 10.0)])
        result_no_gain = cascade_iip3([(0.0, 0.0), (0.0, 10.0)])
        # More gain in front -> worse IIP3
        assert result_with_gain["iip3_dbm"] < result_no_gain["iip3_dbm"]

    def test_empty_stages(self):
        """Empty stages should return inf."""
        result = cascade_iip3([])
        assert result["iip3_dbm"] == float("inf")


class TestCascadeOIP3:
    """Tests for cascaded OIP3."""

    def test_single_stage_oip3(self):
        """Single stage OIP3 should give correct IIP3."""
        # gain=10, OIP3=25 -> IIP3=15
        result = cascade_oip3([(10.0, 25.0)])
        assert result["iip3_dbm"] == pytest.approx(15.0, rel=1e-6)


class TestSFDR:
    """Tests for SFDR calculations."""

    def test_sfdr_positive(self):
        """SFDR should be positive for reasonable parameters."""
        result = sfdr_from_iip3(
            iip3_dbm=0.0,
            noise_floor_dbm_hz=-174.0,
            bandwidth_hz=1e6,
        )
        assert result["sfdr_db"] > 0

    def test_sfdr_from_oip3_matches_iip3(self):
        """sfdr_from_oip3 should give same result as sfdr_from_iip3."""
        gain_db = 20.0
        iip3 = 5.0
        oip3 = iip3 + gain_db
        nf_hz = -170.0
        bw = 1e6

        result_iip3 = sfdr_from_iip3(iip3, nf_hz, bw)
        result_oip3 = sfdr_from_oip3(oip3, nf_hz, bw, gain_db)
        assert result_iip3["sfdr_db"] == pytest.approx(result_oip3["sfdr_db"], rel=1e-6)


class TestMDS:
    """Tests for minimum detectable signal."""

    def test_mds_increases_with_nf(self):
        """Higher NF -> higher (worse) MDS."""
        mds_low = mds_from_noise_figure(3.0, 1e6)
        mds_high = mds_from_noise_figure(10.0, 1e6)
        assert mds_high["mds_dbm"] > mds_low["mds_dbm"]

    def test_mds_increases_with_bandwidth(self):
        """Wider bandwidth -> higher (worse) MDS."""
        mds_narrow = mds_from_noise_figure(3.0, 1e6)
        mds_wide = mds_from_noise_figure(3.0, 100e6)
        assert mds_wide["mds_dbm"] > mds_narrow["mds_dbm"]


class TestSystemNoiseTemperature:
    """Tests for system noise temperature."""

    def test_no_line_loss(self):
        """Without line loss, system temp = antenna + receiver."""
        result = system_noise_temperature(
            antenna_temp_k=50.0,
            receiver_nf_db=3.0,
            line_loss_db=0.0,
        )
        assert result["line_contribution_k"] == pytest.approx(0.0, abs=0.01)
        assert result["system_temp_k"] > 50.0  # Antenna + receiver

    def test_line_loss_increases_noise(self):
        """Line loss should increase system temperature."""
        result_no_loss = system_noise_temperature(50.0, 3.0, 0.0)
        result_with_loss = system_noise_temperature(50.0, 3.0, 3.0)
        assert result_with_loss["system_temp_k"] > result_no_loss["system_temp_k"]


class TestRFStage:
    """Tests for RFStage dataclass."""

    def test_oip3_property(self):
        """OIP3 = IIP3 + gain."""
        stage = RFStage(name="LNA", gain_db=20.0, noise_figure_db=1.5, iip3_dbm=-5.0)
        assert stage.oip3_dbm == pytest.approx(15.0)

    def test_op1db_property(self):
        """OP1dB = IP1dB + gain."""
        stage = RFStage(name="PA", gain_db=30.0, noise_figure_db=5.0, p1db_dbm=10.0)
        assert stage.op1db_dbm == pytest.approx(40.0)


class TestCascadeAnalysis:
    """Tests for complete cascade_analysis."""

    def test_typical_receiver(self):
        """Full analysis of a typical receiver chain."""
        stages = [
            RFStage(name="LNA", gain_db=20.0, noise_figure_db=1.5, iip3_dbm=-5.0),
            RFStage(name="Filter", gain_db=-3.0, noise_figure_db=3.0, iip3_dbm=50.0),
            RFStage(name="IF Amp", gain_db=30.0, noise_figure_db=6.0, iip3_dbm=10.0),
        ]

        result = cascade_analysis(stages, bandwidth_hz=10e6)

        assert result["total_gain_db"] == pytest.approx(47.0)
        assert result["total_nf_db"] < 3.0
        assert "sfdr_db" in result
        assert "mds_dbm" in result
        assert result["sfdr_db"] > 0
        assert len(result["stage_names"]) == 4  # Input + 3 stages
        assert result["n_stages"] == 3

    def test_empty_stages_returns_empty(self):
        """Empty stages list should return empty dict."""
        result = cascade_analysis([])
        assert result == {}


class TestCascadeP1dB:
    """Tests for cascaded 1 dB compression point."""

    def test_single_stage(self):
        from phased_array_systems.models.rf.cascade import cascade_p1db

        result = cascade_p1db([(20.0, -10.0)])
        assert result["ip1db_dbm"] == pytest.approx(-10.0, abs=1e-9)
        assert result["op1db_dbm"] == pytest.approx(-10.0 + 20.0 - 1.0, abs=1e-9)

    def test_two_stage_hand_computed(self):
        """Hand computation, reciprocal-sum form.

        Stage 1: G = 20 dB (x100), IP1dB = -10 dBm (0.1 mW)
        Stage 2: G = 10 dB (x10),  IP1dB = +10 dBm (10 mW)
        1/P = 1/0.1 + 100/10 = 20  ->  P = 0.05 mW = -13.0103 dBm
        """
        from phased_array_systems.models.rf.cascade import cascade_p1db

        result = cascade_p1db([(20.0, -10.0), (10.0, 10.0)])
        assert result["ip1db_dbm"] == pytest.approx(10 * math.log10(0.05), abs=1e-9)
        assert result["total_gain_db"] == pytest.approx(30.0)
        assert result["op1db_dbm"] == pytest.approx(10 * math.log10(0.05) + 29.0, abs=1e-9)

    def test_late_stage_dominates_with_gain_in_front(self):
        """High gain ahead of a weak stage drags the cascade P1dB down."""
        from phased_array_systems.models.rf.cascade import cascade_p1db

        weak_last = cascade_p1db([(30.0, 20.0), (0.0, 0.0)])
        # Input-referred: the last stage's 0 dBm P1dB seen through 30 dB of
        # gain caps the cascade near -30 dBm
        assert weak_last["ip1db_dbm"] < -29.0

    def test_empty_is_ideal(self):
        from phased_array_systems.models.rf.cascade import cascade_p1db

        result = cascade_p1db([])
        assert math.isinf(result["ip1db_dbm"])


class TestRappCompression:
    """Tests for the Rapp soft-limiter compression model."""

    def test_exactly_1db_at_p1db(self):
        from phased_array_systems.models.rf.cascade import rapp_compression_db

        for p in (1.0, 2.0, 3.0, 6.0):
            comp = rapp_compression_db(-5.0, -5.0, smoothness=p)
            assert comp == pytest.approx(1.0, abs=1e-12)

    def test_negligible_at_large_backoff(self):
        from phased_array_systems.models.rf.cascade import rapp_compression_db

        comp = rapp_compression_db(-25.0, -5.0, smoothness=2.0)
        # Hand value: r^2 = 10^0.2 - 1 = 0.5848932; x = r^2 * 10^-4;
        # 5*log10(1 + x) = 1.27e-4 dB
        assert comp == pytest.approx(5 * math.log10(1 + 0.5848932 * 1e-4), rel=1e-4)
        assert comp < 0.001

    def test_monotonic_in_drive(self):
        from phased_array_systems.models.rf.cascade import rapp_compression_db

        drives = [-20.0, -10.0, -5.0, 0.0, 5.0]
        comps = [rapp_compression_db(d, -5.0) for d in drives]
        assert all(b > a for a, b in zip(comps, comps[1:], strict=False))

    def test_deep_saturation_output_clamps(self):
        """Far past P1dB the output power approaches Psat: every extra input
        dB is eaten by compression."""
        from phased_array_systems.models.rf.cascade import rapp_compression_db

        out_a = 40.0 - rapp_compression_db(40.0, -5.0)
        out_b = 50.0 - rapp_compression_db(50.0, -5.0)
        assert out_b - out_a == pytest.approx(0.0, abs=0.01)


class TestCompressionCheck:
    """Tests for per-stage compression headroom."""

    def test_binding_stage_and_headroom(self):
        """driver: G=20, IP1dB=0 (OP1dB=20); pa: G=10, IP1dB=15 (OP1dB=25).
        At -10 dBm input: level 10 after driver (headroom 10),
        level 20 after pa (headroom 5) -> pa binds."""
        from phased_array_systems.models.rf.cascade import RFStage, compression_check

        stages = [
            RFStage(name="driver", gain_db=20.0, noise_figure_db=5.0, p1db_dbm=0.0),
            RFStage(name="pa", gain_db=10.0, noise_figure_db=8.0, p1db_dbm=15.0),
        ]
        result = compression_check(stages, -10.0)
        assert result["stage_headroom_db"] == pytest.approx([10.0, 5.0])
        assert result["min_headroom_db"] == pytest.approx(5.0)
        assert result["binding_stage"] == "pa"
        assert result["compressed"] is False

    def test_overdrive_flags_compressed(self):
        from phased_array_systems.models.rf.cascade import RFStage, compression_check

        stages = [
            RFStage(name="driver", gain_db=20.0, noise_figure_db=5.0, p1db_dbm=0.0),
            RFStage(name="pa", gain_db=10.0, noise_figure_db=8.0, p1db_dbm=15.0),
        ]
        result = compression_check(stages, 7.0)
        # After driver: 27 dBm vs OP1dB 20 -> -7 dB headroom
        # After pa: 37 dBm vs OP1dB 25 -> -12 dB headroom (binds)
        assert result["stage_headroom_db"] == pytest.approx([-7.0, -12.0])
        assert result["min_headroom_db"] == pytest.approx(-12.0)
        assert result["binding_stage"] == "pa"
        assert result["compressed"] is True

    def test_empty_chain(self):
        from phased_array_systems.models.rf.cascade import compression_check

        result = compression_check([], 0.0)
        assert result["compressed"] is False
        assert math.isinf(result["min_headroom_db"])


class TestSndrWithImd3:
    """Tests for SNDR combining thermal noise with IM3."""

    def test_thermal_dominated(self):
        """IM3 60 dB down barely moves a 20 dB SNR."""
        from phased_array_systems.models.rf.cascade import sndr_with_imd3

        result = sndr_with_imd3(20.0, -40.0, -10.0)
        assert result["imd3_dbc"] == pytest.approx(60.0)
        # -10log10(10^-2 + 10^-6) = 19.99957 dB
        assert result["sndr_db"] == pytest.approx(-10 * math.log10(1e-2 + 1e-6), abs=1e-9)
        assert result["sndr_db"] < 20.0

    def test_equal_contributions_cost_3db(self):
        from phased_array_systems.models.rf.cascade import sndr_with_imd3

        # imd3_dbc = 2*(iip3 - carrier) = 20 dB, equal to SNR
        result = sndr_with_imd3(20.0, -20.0, -10.0)
        assert result["imd3_dbc"] == pytest.approx(20.0)
        assert result["sndr_db"] == pytest.approx(20.0 - 10 * math.log10(2), abs=1e-9)

    def test_evm_from_sndr(self):
        from phased_array_systems.models.rf.cascade import sndr_with_imd3

        result = sndr_with_imd3(20.0, -40.0, -10.0)
        assert result["evm_rms_pct"] == pytest.approx(
            100 * 10 ** (-result["sndr_db"] / 20), rel=1e-12
        )

    def test_ideal_iip3_reduces_to_snr(self):
        from phased_array_systems.models.rf.cascade import sndr_with_imd3

        result = sndr_with_imd3(20.0, -60.0, 100.0)
        assert result["sndr_db"] == pytest.approx(20.0, abs=1e-9)


class TestCascadeAnalysisP1dBKeys:
    """cascade_analysis emits the new P1dB / compression keys."""

    def test_keys_present_and_consistent(self):
        stages = [
            RFStage(name="lna", gain_db=20.0, noise_figure_db=1.5, iip3_dbm=-5.0, p1db_dbm=-15.0),
            RFStage(name="mixer", gain_db=-7.0, noise_figure_db=7.0, iip3_dbm=15.0, p1db_dbm=5.0),
        ]
        result = cascade_analysis(stages, bandwidth_hz=1e6, input_power_dbm=-60.0)
        for key in (
            "ip1db_dbm",
            "op1db_dbm",
            "min_p1db_headroom_db",
            "p1db_binding_stage",
            "compressed",
        ):
            assert key in result
        # At -60 dBm drive nothing compresses
        assert result["compressed"] is False
        # Cascade P1dB is input-referred below the first stage's own P1dB
        assert result["ip1db_dbm"] < -15.0
