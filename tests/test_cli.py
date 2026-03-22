"""Tests for CLI."""

import argparse
import json
import subprocess
import sys
from pathlib import Path


class TestCLIHelp:
    """Tests for CLI help output."""

    def test_help_flag(self):
        """Test --help flag shows usage."""
        result = subprocess.run(
            [sys.executable, "-m", "phased_array_systems.cli", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "pasys" in result.stdout
        assert "Phased array system design" in result.stdout

    def test_version_flag(self):
        """Test --version flag shows version."""
        result = subprocess.run(
            [sys.executable, "-m", "phased_array_systems.cli", "--version"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "pasys" in result.stdout

    def test_run_help(self):
        """Test run subcommand help."""
        result = subprocess.run(
            [sys.executable, "-m", "phased_array_systems.cli", "run", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "config" in result.stdout

    def test_doe_help(self):
        """Test doe subcommand help."""
        result = subprocess.run(
            [sys.executable, "-m", "phased_array_systems.cli", "doe", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "samples" in result.stdout
        assert "method" in result.stdout

    def test_report_help(self):
        """Test report subcommand help."""
        result = subprocess.run(
            [sys.executable, "-m", "phased_array_systems.cli", "report", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "results" in result.stdout
        assert "format" in result.stdout

    def test_pareto_help(self):
        """Test pareto subcommand help."""
        result = subprocess.run(
            [sys.executable, "-m", "phased_array_systems.cli", "pareto", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "-x" in result.stdout
        assert "-y" in result.stdout


class TestCLIParser:
    """Tests for CLI argument parser."""

    def test_parser_creation(self):
        """Test parser can be created."""
        from phased_array_systems.cli import create_parser

        parser = create_parser()
        assert parser is not None
        assert parser.prog == "pasys"

    def test_parser_subcommands(self):
        """Test parser has all subcommands."""
        from phased_array_systems.cli import create_parser

        parser = create_parser()

        # Parse run command
        args = parser.parse_args(["run", "test.yaml"])
        assert args.command == "run"
        assert str(args.config) == "test.yaml"

        # Parse doe command
        args = parser.parse_args(["doe", "test.yaml", "-n", "100"])
        assert args.command == "doe"
        assert args.samples == 100

        # Parse report command
        args = parser.parse_args(["report", "results.parquet", "--format", "html"])
        assert args.command == "report"
        assert args.format == "html"

        # Parse pareto command
        args = parser.parse_args(["pareto", "results.parquet", "-x", "cost_usd", "-y", "eirp_dbw"])
        assert args.command == "pareto"
        assert args.x == "cost_usd"
        assert args.y == "eirp_dbw"

    def test_doe_defaults(self):
        """Test DOE command has correct defaults."""
        from phased_array_systems.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["doe", "test.yaml"])

        assert args.samples == 50
        assert args.method == "lhs"
        assert args.seed == 42
        assert args.workers == 1

    def test_report_format_choices(self):
        """Test report format choices."""
        from phased_array_systems.cli import create_parser

        parser = create_parser()

        # Valid formats
        for fmt in ["html", "markdown", "md"]:
            args = parser.parse_args(["report", "results.parquet", "--format", fmt])
            assert args.format == fmt


class TestCLICommands:
    """Tests for CLI command functions."""

    def test_run_missing_file(self):
        """Test run command with missing file."""
        result = subprocess.run(
            [sys.executable, "-m", "phased_array_systems.cli", "run", "nonexistent.yaml"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "Error" in result.stderr

    def test_pareto_missing_file(self):
        """Test pareto command with missing file."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "phased_array_systems.cli",
                "pareto",
                "nonexistent.parquet",
                "-x",
                "cost",
                "-y",
                "eirp",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "Error" in result.stderr

    def test_report_missing_file(self):
        """Test report command with missing file."""
        result = subprocess.run(
            [sys.executable, "-m", "phased_array_systems.cli", "report", "nonexistent.parquet"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "Error" in result.stderr


class TestPrintMetricsTable:
    """Tests for print_metrics_table function."""

    def test_metrics_table_output(self, capsys):
        """Test metrics table formatting."""
        from phased_array_systems.cli import print_metrics_table

        metrics = {
            "g_peak_db": 30.5,
            "eirp_dbw": 45.2,
            "cost_usd": 50000.0,
            "prime_power_w": 1500.0,
            "verification.passes": 1.0,
        }

        print_metrics_table(metrics, "Test Results")
        captured = capsys.readouterr()

        assert "Test Results" in captured.out
        assert "g_peak_db" in captured.out
        assert "30.5" in captured.out or "30.50" in captured.out

    def test_metrics_grouping(self, capsys):
        """Test metrics are grouped by category."""
        from phased_array_systems.cli import print_metrics_table

        metrics = {
            "g_peak_db": 30.0,
            "eirp_dbw": 45.0,
            "cost_usd": 50000.0,
            "prime_power_w": 1500.0,
            "verification.passes": 1.0,
        }

        print_metrics_table(metrics)
        captured = capsys.readouterr()

        # Check groups appear
        assert "Antenna" in captured.out or "Link Budget" in captured.out
        assert "Cost" in captured.out or "Power" in captured.out


CONFIGS_DIR = Path(__file__).parent.parent / "examples" / "configs"


class TestCLIEndToEnd:
    """End-to-end tests for CLI command functions."""

    def test_cmd_run_comms(self, capsys):
        """Test cmd_run with comms_basic.yaml and JSON output."""
        from phased_array_systems.cli import cmd_run

        args = argparse.Namespace(
            config=CONFIGS_DIR / "comms_basic.yaml",
            format="json",
            output=None,
        )
        ret = cmd_run(args)
        assert ret == 0

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "g_peak_db" in data
        assert "eirp_dbw" in data
        assert "cascade_nf_db" in data

    def test_cmd_run_radar(self, capsys):
        """Test cmd_run with radar_basic.yaml and JSON output."""
        from phased_array_systems.cli import cmd_run

        args = argparse.Namespace(
            config=CONFIGS_DIR / "radar_basic.yaml",
            format="json",
            output=None,
        )
        ret = cmd_run(args)
        assert ret == 0

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "snr_margin_db" in data or "snr_single_pulse_db" in data
        assert "g_peak_db" in data

    def test_cmd_run_output_file(self, tmp_path, capsys):
        """Test cmd_run writes output file."""
        from phased_array_systems.cli import cmd_run

        out_file = tmp_path / "result.json"
        args = argparse.Namespace(
            config=CONFIGS_DIR / "comms_basic.yaml",
            format="table",
            output=out_file,
        )
        ret = cmd_run(args)
        assert ret == 0
        assert out_file.exists()

        data = json.loads(out_file.read_text())
        assert "g_peak_db" in data

    def test_cmd_doe_comms(self, tmp_path, capsys):
        """Test cmd_doe with comms_doe.yaml."""
        from phased_array_systems.cli import cmd_doe

        args = argparse.Namespace(
            config=CONFIGS_DIR / "comms_doe.yaml",
            output=tmp_path,
            samples=5,
            method="lhs",
            seed=42,
            workers=1,
        )
        ret = cmd_doe(args)
        assert ret == 0

        result_path = tmp_path / "results.parquet"
        assert result_path.exists()

        import pandas as pd

        df = pd.read_parquet(result_path)
        assert len(df) == 5

    def test_cmd_doe_radar(self, tmp_path, capsys):
        """Test cmd_doe with radar_doe.yaml."""
        from phased_array_systems.cli import cmd_doe

        args = argparse.Namespace(
            config=CONFIGS_DIR / "radar_doe.yaml",
            output=tmp_path,
            samples=5,
            method="lhs",
            seed=42,
            workers=1,
        )
        ret = cmd_doe(args)
        assert ret == 0

        result_path = tmp_path / "results.parquet"
        assert result_path.exists()

        import pandas as pd

        df = pd.read_parquet(result_path)
        assert len(df) == 5

    def test_cmd_report_html(self, tmp_path, capsys):
        """Test cmd_report generates HTML output."""
        from phased_array_systems.cli import cmd_doe, cmd_report

        # Generate results first
        args_doe = argparse.Namespace(
            config=CONFIGS_DIR / "comms_doe.yaml",
            output=tmp_path,
            samples=5,
            method="lhs",
            seed=42,
            workers=1,
        )
        cmd_doe(args_doe)

        result_path = tmp_path / "results.parquet"
        report_path = tmp_path / "report.html"
        args_report = argparse.Namespace(
            results=result_path,
            output=report_path,
            format="html",
            title="Test Report",
        )
        ret = cmd_report(args_report)
        assert ret == 0
        assert report_path.exists()
        content = report_path.read_text()
        assert "<html" in content

    def test_cmd_report_markdown(self, tmp_path, capsys):
        """Test cmd_report generates Markdown output."""
        from phased_array_systems.cli import cmd_doe, cmd_report

        # Generate results first
        args_doe = argparse.Namespace(
            config=CONFIGS_DIR / "comms_doe.yaml",
            output=tmp_path,
            samples=5,
            method="lhs",
            seed=42,
            workers=1,
        )
        cmd_doe(args_doe)

        result_path = tmp_path / "results.parquet"
        report_path = tmp_path / "report.md"
        args_report = argparse.Namespace(
            results=result_path,
            output=report_path,
            format="markdown",
            title="Test Report",
        )
        ret = cmd_report(args_report)
        assert ret == 0
        assert report_path.exists()
        content = report_path.read_text()
        assert "# Test Report" in content

    def test_cmd_pareto(self, tmp_path, capsys):
        """Test cmd_pareto extracts Pareto frontier."""
        from phased_array_systems.cli import cmd_doe, cmd_pareto

        # Generate results first
        args_doe = argparse.Namespace(
            config=CONFIGS_DIR / "comms_doe.yaml",
            output=tmp_path,
            samples=10,
            method="lhs",
            seed=42,
            workers=1,
        )
        cmd_doe(args_doe)

        result_path = tmp_path / "results.parquet"
        pareto_path = tmp_path / "pareto.parquet"
        args_pareto = argparse.Namespace(
            results=result_path,
            x="cost_usd",
            y="eirp_dbw",
            output=pareto_path,
            plot=False,
        )
        ret = cmd_pareto(args_pareto)
        assert ret == 0

    def test_cmd_sensitivity(self, tmp_path, capsys):
        """Test cmd_sensitivity runs OAT analysis."""
        from phased_array_systems.cli import cmd_sensitivity

        args = argparse.Namespace(
            config=CONFIGS_DIR / "comms_doe.yaml",
            output=None,
            steps=3,
            plot=False,
            metric="g_peak_db",
        )
        ret = cmd_sensitivity(args)
        assert ret == 0
