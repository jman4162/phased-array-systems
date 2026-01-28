"""Tests for report generation."""

import tempfile
from pathlib import Path

import pandas as pd
import pytest

from phased_array_systems.reports import HTMLReport, MarkdownReport, ReportConfig


@pytest.fixture
def sample_results():
    """Create sample results DataFrame for testing."""
    return pd.DataFrame({
        "case_id": ["case_001", "case_002", "case_003", "case_004", "case_005"],
        "array.nx": [8, 8, 16, 16, 32],
        "array.ny": [8, 8, 16, 16, 32],
        "rf.tx_power_w_per_elem": [5.0, 10.0, 5.0, 10.0, 5.0],
        "g_peak_db": [25.1, 25.1, 31.2, 31.2, 37.3],
        "eirp_dbw": [42.1, 45.1, 51.2, 54.2, 61.3],
        "link_margin_db": [3.5, 6.5, 12.6, 15.6, 22.7],
        "cost_usd": [50000, 55000, 150000, 160000, 500000],
        "prime_power_w": [500, 800, 1500, 2500, 5000],
        "verification.passes": [1.0, 1.0, 1.0, 1.0, 0.0],
    })


class TestReportConfig:
    """Tests for ReportConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = ReportConfig()
        assert config.title == "Trade Study Report"
        assert config.include_summary is True
        assert config.include_pareto is True
        assert config.include_plots is True
        assert config.max_rows == 50

    def test_custom_config(self):
        """Test custom configuration."""
        config = ReportConfig(
            title="My Trade Study",
            description="A description",
            author="Test Author",
            max_rows=100,
        )
        assert config.title == "My Trade Study"
        assert config.description == "A description"
        assert config.author == "Test Author"
        assert config.max_rows == 100


class TestHTMLReport:
    """Tests for HTMLReport."""

    def test_report_creation(self):
        """Test report generator can be created."""
        report = HTMLReport()
        assert report.config is not None

    def test_generate_basic(self, sample_results):
        """Test basic HTML generation."""
        report = HTMLReport()
        html = report.generate(sample_results)

        # Check it's valid HTML
        assert html.startswith("<!DOCTYPE html>")
        assert "</html>" in html

        # Check title is present
        assert "Trade Study Report" in html

        # Check data is present
        assert "case_001" in html
        assert "5" in html  # number of cases

    def test_generate_with_custom_title(self, sample_results):
        """Test HTML generation with custom title."""
        config = ReportConfig(title="Custom Report Title")
        report = HTMLReport(config)
        html = report.generate(sample_results)

        assert "Custom Report Title" in html

    def test_generate_with_description(self, sample_results):
        """Test HTML generation with description."""
        config = ReportConfig(
            title="Test Report",
            description="This is a test description",
        )
        report = HTMLReport(config)
        html = report.generate(sample_results)

        assert "This is a test description" in html

    def test_generate_with_author(self, sample_results):
        """Test HTML generation with author."""
        config = ReportConfig(author="Test Author")
        report = HTMLReport(config)
        html = report.generate(sample_results)

        assert "Test Author" in html

    def test_summary_section(self, sample_results):
        """Test summary section is generated."""
        report = HTMLReport()
        html = report.generate(sample_results)

        # Check summary stats
        assert "Total Cases" in html
        assert "Feasible Designs" in html
        assert "4" in html  # 4 feasible out of 5

    def test_table_section(self, sample_results):
        """Test results table is generated."""
        report = HTMLReport()
        html = report.generate(sample_results)

        # Check table headers
        assert "case_id" in html
        assert "PASS" in html or "FAIL" in html

    def test_statistics_section(self, sample_results):
        """Test statistics section is generated."""
        report = HTMLReport()
        html = report.generate(sample_results)

        # Check metric stats
        assert "Min" in html
        assert "Max" in html
        assert "Mean" in html

    def test_save(self, sample_results):
        """Test saving HTML report to file."""
        report = HTMLReport()
        html = report.generate(sample_results)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "report.html"
            report.save(html, path)

            assert path.exists()
            content = path.read_text()
            assert "<!DOCTYPE html>" in content


class TestMarkdownReport:
    """Tests for MarkdownReport."""

    def test_report_creation(self):
        """Test report generator can be created."""
        report = MarkdownReport()
        assert report.config is not None

    def test_generate_basic(self, sample_results):
        """Test basic Markdown generation."""
        report = MarkdownReport()
        md = report.generate(sample_results)

        # Check title
        assert md.startswith("# Trade Study Report")

        # Check sections exist
        assert "## Summary" in md
        assert "## Results" in md
        assert "## Metric Statistics" in md

    def test_generate_with_custom_title(self, sample_results):
        """Test Markdown generation with custom title."""
        config = ReportConfig(title="Custom Report Title")
        report = MarkdownReport(config)
        md = report.generate(sample_results)

        assert "# Custom Report Title" in md

    def test_generate_with_description(self, sample_results):
        """Test Markdown generation with description."""
        config = ReportConfig(
            title="Test Report",
            description="This is a test description",
        )
        report = MarkdownReport(config)
        md = report.generate(sample_results)

        assert "This is a test description" in md

    def test_generate_with_author(self, sample_results):
        """Test Markdown generation with author."""
        config = ReportConfig(author="Test Author")
        report = MarkdownReport(config)
        md = report.generate(sample_results)

        assert "Test Author" in md

    def test_summary_table(self, sample_results):
        """Test summary table is generated."""
        report = MarkdownReport()
        md = report.generate(sample_results)

        # Check markdown table syntax
        assert "| Metric | Value |" in md
        assert "|--------|-------|" in md
        assert "Total Cases" in md

    def test_results_table(self, sample_results):
        """Test results table is generated."""
        report = MarkdownReport()
        md = report.generate(sample_results)

        # Check for case IDs in table
        assert "case_001" in md

    def test_statistics_table(self, sample_results):
        """Test statistics table is generated."""
        report = MarkdownReport()
        md = report.generate(sample_results)

        # Check stats table
        assert "| Metric | Min | Max | Mean | Std Dev |" in md

    def test_footer(self, sample_results):
        """Test footer is generated."""
        report = MarkdownReport()
        md = report.generate(sample_results)

        assert "Generated by" in md
        assert "phased-array-systems" in md

    def test_save(self, sample_results):
        """Test saving Markdown report to file."""
        report = MarkdownReport()
        md = report.generate(sample_results)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "report.md"
            report.save(md, path)

            assert path.exists()
            content = path.read_text()
            assert "# Trade Study Report" in content


class TestReportGenerator:
    """Tests for shared ReportGenerator functionality."""

    def test_metadata(self, sample_results):
        """Test metadata generation."""
        config = ReportConfig(
            title="Test",
            description="Description",
            author="Author",
        )
        report = HTMLReport(config)
        metadata = report._get_metadata()

        assert metadata["title"] == "Test"
        assert metadata["description"] == "Description"
        assert metadata["author"] == "Author"
        assert "generated_at" in metadata
        assert "generator_version" in metadata

    def test_summary_stats(self, sample_results):
        """Test summary statistics computation."""
        report = HTMLReport()
        stats = report._compute_summary_stats(sample_results)

        assert stats["n_cases"] == 5
        assert stats["n_feasible"] == 4
        assert stats["feasible_pct"] == 80.0

    def test_column_identification(self, sample_results):
        """Test column type identification."""
        report = HTMLReport()
        columns = report._identify_columns(sample_results)

        assert "array.nx" in columns["input"]
        assert "array.ny" in columns["input"]
        assert "rf.tx_power_w_per_elem" in columns["input"]
        assert "verification.passes" in columns["verification"]
        assert "g_peak_db" in columns["output"]
        assert "cost_usd" in columns["output"]
