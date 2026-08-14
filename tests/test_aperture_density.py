"""Aperture power density, cooling feasibility, and power-aperture product.

The physics pinned here:

- unit cell area is (dx_lambda * dy_lambda) * lambda^2, so at half-wave
  spacing it is (lambda/2)^2 and heat flux rises as f^2 at fixed per-element
  dissipation. That scaling is the whole reason the metric exists;
- heat flux uses AVERAGE power (cold-plate time constants are seconds, a PRI
  is microseconds), while radiated density is reported at both peak and
  average;
- the junction temperature keeps its per-DEVICE normalization. Aperture flux
  answers a different question and must not change it.
"""

import math

import pytest

from phased_array_systems.architecture import (
    Architecture,
    ArrayConfig,
    CoolingConfig,
    CostConfig,
    ReliabilityConfig,
    RFChainConfig,
)
from phased_array_systems.constants import C
from phased_array_systems.evaluate import evaluate_case
from phased_array_systems.models.swapc.cooling import (
    assess,
    cooling_classes,
    load_catalog,
    max_heat_flux,
    minimum_class_for,
)
from phased_array_systems.models.swapc.power import PowerModel, aperture_geometry
from phased_array_systems.scenarios import CommsLinkScenario, RadarDetectionScenario


def _arch(nx=16, ny=16, dx=0.5, dy=0.5, tx_w=1.0, **rf):
    return Architecture(
        array=ArrayConfig(nx=nx, ny=ny, dx_lambda=dx, dy_lambda=dy),
        rf=RFChainConfig(tx_power_w_per_elem=tx_w, pa_efficiency=0.3, **rf),
        cost=CostConfig(cost_per_elem_usd=100.0),
    )


def _scenario(freq_hz=10e9, duty=1.0):
    return RadarDetectionScenario(
        freq_hz=freq_hz,
        bandwidth_hz=10e6,
        range_m=20e3,
        target_rcs_dbsm=0.0,
        duty_cycle=duty,
    )


class TestApertureGeometry:
    def test_half_wave_cell_at_10ghz_hand_value(self):
        """lambda = c/10 GHz = 2.9979 cm; cell = (lambda/2)^2 = 2.2469 cm^2."""
        geom = aperture_geometry(_arch(), _scenario())
        lam = C / 10e9
        assert geom["wavelength_m"] == pytest.approx(lam)
        assert geom["cell_area_cm2"] == pytest.approx((lam / 2) ** 2 * 1e4, rel=1e-12)
        assert geom["cell_area_cm2"] == pytest.approx(2.2469, abs=1e-3)

    def test_aperture_is_n_times_d_not_n_minus_one(self):
        """Each element owns a full cell, so the radiating aperture is N*d."""
        geom = aperture_geometry(_arch(nx=16, ny=16), _scenario())
        assert geom["aperture_area_m2"] == pytest.approx(256 * geom["cell_area_m2"])

    def test_cell_area_scales_with_spacing(self):
        wide = aperture_geometry(_arch(dx=0.6, dy=0.6), _scenario())["cell_area_cm2"]
        half = aperture_geometry(_arch(dx=0.5, dy=0.5), _scenario())["cell_area_cm2"]
        assert wide / half == pytest.approx((0.6 / 0.5) ** 2)

    def test_missing_frequency_is_an_error(self):
        class NoFreq:
            freq_hz = 0.0

        with pytest.raises(ValueError, match="freq_hz"):
            aperture_geometry(_arch(), NoFreq())


class TestHeatFluxScaling:
    def test_f_squared_law(self):
        """The claim the metric exists for: at fixed per-element dissipation,
        tripling frequency (X to Ka) multiplies heat flux by nine."""
        arch = _arch()
        model = PowerModel()
        x = model.evaluate(arch, _scenario(10e9), {})
        ka = model.evaluate(arch, _scenario(30e9), {})
        assert ka["heat_dissipation_w"] == pytest.approx(x["heat_dissipation_w"])
        ratio = ka["heat_flux_w_per_cm2"] / x["heat_flux_w_per_cm2"]
        assert ratio == pytest.approx(9.0, rel=1e-9)

    def test_flux_is_heat_per_element_over_cell_area(self):
        """Equivalent normalizations: total/aperture == per-element/cell."""
        arch = _arch()
        m = PowerModel().evaluate(arch, _scenario(), {})
        per_elem = m["heat_dissipation_w"] / arch.array.n_elements
        assert m["heat_flux_w_per_cm2"] == pytest.approx(per_elem / m["cell_area_cm2"], rel=1e-9)

    def test_radiated_peak_and_average_differ_by_duty_cycle(self):
        m = PowerModel().evaluate(_arch(), _scenario(duty=0.1), {})
        assert m["radiated_power_density_avg_w_per_cm2"] == pytest.approx(
            0.1 * m["radiated_power_density_peak_w_per_cm2"], rel=1e-9
        )

    def test_energy_balance_closes(self):
        """heat = DC in minus average RF out, from the one shared balance."""
        m = PowerModel().evaluate(_arch(), _scenario(duty=0.2), {})
        assert m["heat_dissipation_w"] == pytest.approx(
            m["dc_power_w"] - m["rf_avg_power_w"], rel=1e-12
        )

    def test_tighter_lattice_raises_flux_at_fixed_element_power(self):
        """The coupling the per-element thermal model cannot see: packing
        elements tighter leaves junction dissipation unchanged and raises
        aperture heat flux."""
        loose = PowerModel().evaluate(_arch(dx=0.5, dy=0.5), _scenario(), {})
        tight = PowerModel().evaluate(_arch(dx=0.3, dy=0.3), _scenario(), {})
        per_elem_loose = loose["heat_dissipation_w"] / 256
        per_elem_tight = tight["heat_dissipation_w"] / 256
        assert per_elem_tight == pytest.approx(per_elem_loose)
        assert tight["heat_flux_w_per_cm2"] > loose["heat_flux_w_per_cm2"]
        assert tight["heat_flux_w_per_cm2"] / loose["heat_flux_w_per_cm2"] == pytest.approx(
            (0.5 / 0.3) ** 2
        )


class TestCoolingCatalog:
    def test_classes_ordered_by_capability(self):
        names = cooling_classes()
        fluxes = [max_heat_flux(n) for n in names]
        assert fluxes == sorted(fluxes)
        assert names[0] == "natural_convection"

    def test_every_number_carries_provenance(self):
        """No number without a checkable reference, and each states whether it
        was quoted from the source or is a judgment gate."""
        for key, entry in load_catalog().items():
            if key == "notes":
                continue
            field = entry["max_heat_flux_w_per_cm2"]
            for required in ("value", "units", "verified", "source", "url", "accessed", "quote"):
                assert required in field, f"{key} missing {required}"
            assert field["verified"] in {"quoted", "judgment"}

    def test_forced_air_ceiling_is_the_verified_darpa_figure(self):
        assert max_heat_flux("forced_air") == pytest.approx(1.0)
        assert load_catalog()["forced_air"]["max_heat_flux_w_per_cm2"]["verified"] == "quoted"

    def test_unknown_class_rejected(self):
        with pytest.raises(KeyError, match="unknown cooling class"):
            max_heat_flux("magic")

    def test_assess_margin_and_feasibility(self):
        ok = assess(0.5, "forced_air")
        assert ok["cooling_feasible"] is True
        assert ok["cooling_margin_w_per_cm2"] == pytest.approx(0.5)
        bad = assess(4.0, "forced_air")
        assert bad["cooling_feasible"] is False
        assert bad["cooling_margin_w_per_cm2"] == pytest.approx(-3.0)

    def test_minimum_class_walks_the_ladder(self):
        assert minimum_class_for(0.01) == "natural_convection"
        assert minimum_class_for(0.5) == "forced_air"
        assert minimum_class_for(4.5) == "liquid_cold_plate"
        assert minimum_class_for(60.0) == "microchannel_two_phase"
        assert minimum_class_for(5000.0) is None


class TestCoolingInEvaluate:
    def _case(self, cooling_class, tx_w, duty=1.0):
        arch = _arch(tx_w=tx_w)
        arch.cooling = CoolingConfig(cooling_class=cooling_class)
        return evaluate_case(arch, _scenario(duty=duty))

    def test_feasible_design_passes(self):
        m = self._case("forced_air", tx_w=0.2, duty=0.1)
        assert m["cooling_feasible"] is True
        assert m["cooling_margin_w_per_cm2"] > 0

    def test_infeasible_design_is_flagged(self):
        """A CW design at 5 W per element cannot be forced-air cooled."""
        m = self._case("forced_air", tx_w=5.0, duty=1.0)
        assert m["heat_flux_w_per_cm2"] > 1.0
        assert m["cooling_feasible"] is False

    def test_no_cooling_config_no_metrics(self):
        m = evaluate_case(_arch(), _scenario())
        assert "cooling_feasible" not in m
        assert "heat_flux_w_per_cm2" in m

    def test_explicit_override_wins(self):
        arch = _arch(tx_w=5.0)
        arch.cooling = CoolingConfig(cooling_class="forced_air", max_heat_flux_w_per_cm2=99.0)
        m = evaluate_case(arch, _scenario())
        assert m["max_heat_flux_w_per_cm2"] == 99.0
        assert m["cooling_feasible"] is True


class TestJunctionTemperatureUnchanged:
    def test_thermal_refactor_preserves_junction_temp(self):
        """The energy balance moved into compute_thermal_load; the junction
        temperature it feeds must be numerically identical."""
        arch = _arch(tx_w=2.0, rx_power_w_per_elem=0.2)
        arch.reliability = ReliabilityConfig(thermal_resistance_c_per_w=20.0, ambient_temp_c=30.0)
        m = evaluate_case(arch, _scenario(duty=0.1))
        heat_per_elem = m["heat_dissipation_w"] / arch.array.n_elements
        assert m["junction_temp_c"] == pytest.approx(30.0 + 20.0 * heat_per_elem, rel=1e-12)

    def test_tj_max_margin_reported(self):
        arch = _arch(tx_w=2.0)
        arch.reliability = ReliabilityConfig(
            thermal_resistance_c_per_w=20.0, ambient_temp_c=30.0, tj_max_c=150.0
        )
        m = evaluate_case(arch, _scenario(duty=0.1))
        assert m["junction_temp_max_c"] == 150.0
        assert m["junction_temp_margin_c"] == pytest.approx(150.0 - m["junction_temp_c"])
        assert m["junction_temp_ok"] is True

    def test_tj_max_violation_flagged(self):
        arch = _arch(tx_w=10.0)
        arch.reliability = ReliabilityConfig(
            thermal_resistance_c_per_w=40.0, ambient_temp_c=40.0, tj_max_c=150.0
        )
        m = evaluate_case(arch, _scenario(duty=1.0))
        assert m["junction_temp_c"] > 150.0
        assert m["junction_temp_ok"] is False
        assert m["junction_temp_margin_c"] < 0


class TestPowerAperture:
    def test_effective_aperture_matches_gain_relation(self):
        from phased_array_systems.models.radar.search import effective_aperture_m2

        lam = C / 10e9
        a_e = effective_aperture_m2(30.0, 10e9)
        assert a_e == pytest.approx(1000.0 * lam**2 / (4 * math.pi), rel=1e-12)

    def test_required_scales_as_range_fourth(self):
        from phased_array_systems.models.radar.search import required_power_aperture_w_m2

        kw = {
            "target_rcs_m2": 1.0,
            "search_solid_angle_sr": 0.1,
            "frame_time_s": 2.0,
            "snr_required_db": 13.0,
            "system_noise_temp_k": 500.0,
        }
        near = required_power_aperture_w_m2(range_m=10e3, **kw)
        far = required_power_aperture_w_m2(range_m=20e3, **kw)
        assert far / near == pytest.approx(16.0, rel=1e-12)

    def test_required_scales_inversely_with_frame_time(self):
        from phased_array_systems.models.radar.search import required_power_aperture_w_m2

        kw = {
            "range_m": 20e3,
            "target_rcs_m2": 1.0,
            "search_solid_angle_sr": 0.1,
            "snr_required_db": 13.0,
            "system_noise_temp_k": 500.0,
        }
        slow = required_power_aperture_w_m2(frame_time_s=4.0, **kw)
        fast = required_power_aperture_w_m2(frame_time_s=2.0, **kw)
        assert fast / slow == pytest.approx(2.0, rel=1e-12)

    def test_product_is_power_times_area_not_a_density(self):
        """P*A is W*m^2 -- dimensionally the inverse of a power density.
        Doubling both power and area quadruples it."""
        from phased_array_systems.models.radar.search import power_aperture_product_w_m2

        base = power_aperture_product_w_m2(100.0, 2.0)
        both = power_aperture_product_w_m2(200.0, 4.0)
        assert both / base == pytest.approx(4.0)

    def test_evaluate_emits_margin_for_a_search_scenario(self):
        scenario = RadarDetectionScenario(
            freq_hz=9.5e9,
            bandwidth_hz=5e6,
            range_m=25e3,
            target_rcs_dbsm=0.0,
            duty_cycle=0.1,
            prf_hz=2000.0,
            n_pulses=16,
            search_az_extent_deg=90.0,
            search_el_extent_deg=20.0,
            search_frame_time_ms=3000.0,
        )
        m = evaluate_case(_arch(nx=32, ny=32, tx_w=5.0), scenario)
        assert m["effective_aperture_m2"] > 0
        assert m["power_aperture_product_w_m2"] > 0
        assert "power_aperture_required_w_m2" in m
        assert m["power_aperture_margin_db"] == pytest.approx(
            10 * math.log10(m["power_aperture_product_w_m2"] / m["power_aperture_required_w_m2"])
        )


class TestCommsScenarioStillWorks:
    def test_density_metrics_present_for_comms(self):
        arch = _arch()
        scenario = CommsLinkScenario(
            freq_hz=28e9, bandwidth_hz=100e6, range_m=500e3, required_snr_db=10.0
        )
        m = evaluate_case(arch, scenario)
        assert m["heat_flux_w_per_cm2"] > 0
        assert "power_aperture_product_w_m2" not in m
