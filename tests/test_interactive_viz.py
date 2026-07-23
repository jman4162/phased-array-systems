"""Tests for interactive plotly figures and report embeds ([plotting] extra)."""

import pandas as pd
import pytest

pytest.importorskip("plotly", reason="plotly required for interactive viz tests")

from phased_array_systems.reports import HTMLReport  # noqa: E402
from phased_array_systems.reports.generator import ReportConfig  # noqa: E402
from phased_array_systems.viz.interactive import (  # noqa: E402
    figure_to_html_div,
    pareto_plot_interactive,
    trade_space_plot_interactive,
)


@pytest.fixture
def results():
    return pd.DataFrame(
        {
            "case_id": [f"case_{i:05d}" for i in range(6)],
            "cost_usd": [1e3, 2e3, 3e3, 4e3, 5e3, 6e3],
            "eirp_dbw": [30.0, 35.0, 33.0, 40.0, 38.0, 44.0],
            "prime_power_w": [50.0, 90.0, 70.0, 150.0, 120.0, 200.0],
            "verification.passes": [1.0, 1.0, 0.0, 1.0, 1.0, 1.0],
        }
    )


class TestInteractiveFigures:
    def test_pareto_plot_traces(self, results):
        front = results.iloc[[0, 1, 5]]
        mask = results["verification.passes"] == 1.0
        fig = pareto_plot_interactive(
            results, "cost_usd", "eirp_dbw", pareto_front=front, feasible_mask=mask
        )
        names = [t.name for t in fig.data]
        assert "Infeasible" in names
        assert "Feasible" in names
        assert "Pareto optimal" in names

    def test_hover_includes_case_id(self, results):
        fig = pareto_plot_interactive(results, "cost_usd", "eirp_dbw")
        assert "case_00000" in fig.data[0].text[0]

    def test_trade_space_3d(self, results):
        fig = trade_space_plot_interactive(results, "cost_usd", "eirp_dbw", "prime_power_w")
        assert fig.data[0].type == "scatter3d"

    def test_html_div_is_self_contained(self, results):
        import re

        fig = pareto_plot_interactive(results, "cost_usd", "eirp_dbw")
        div = figure_to_html_div(fig)
        # plotly.js inlined: no external script sources anywhere
        assert not re.findall(r"<script[^>]*\ssrc=", div)
        assert len(div) > 1_000_000  # the bundled library is present


class TestReportEmbed:
    def test_report_embeds_plot_with_objectives(self, results):
        cfg = ReportConfig(
            title="t", objectives=[("cost_usd", "minimize"), ("eirp_dbw", "maximize")]
        )
        html = HTMLReport(cfg).generate(results)
        assert "Interactive Trade-off" in html

    def test_report_without_objectives_has_no_plot(self, results):
        html = HTMLReport(ReportConfig(title="t")).generate(results)
        assert "Interactive Trade-off" not in html

    def test_report_with_missing_columns_omits_plot(self, results):
        cfg = ReportConfig(title="t", objectives=[("nope", "minimize"), ("eirp_dbw", "maximize")])
        html = HTMLReport(cfg).generate(results)
        assert "Interactive Trade-off" not in html
