"""Command-line interface for phased-array-systems."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from phased_array_systems import __version__


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog="pasys",
        description="Phased array system design and trade study tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  pasys run config.yaml              Run single-case evaluation
  pasys doe config.yaml -n 100       Run DOE with 100 samples
  pasys report results.parquet       Generate HTML report
  pasys pareto results.parquet -x cost_usd -y eirp_dbw
        """,
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # pasys run <config>
    run_parser = subparsers.add_parser("run", help="Run single-case evaluation")
    run_parser.add_argument("config", type=Path, help="Config file (YAML/JSON)")
    run_parser.add_argument("-o", "--output", type=Path, help="Output file")
    run_parser.add_argument(
        "--format",
        choices=["json", "yaml", "table"],
        default="table",
        help="Output format (default: table)",
    )

    # pasys doe <config>
    doe_parser = subparsers.add_parser("doe", help="Run DOE batch study")
    doe_parser.add_argument("config", type=Path, help="Config file (YAML/JSON)")
    doe_parser.add_argument("-o", "--output", type=Path, help="Output directory")
    doe_parser.add_argument("-n", "--samples", type=int, default=50, help="Number of DOE samples")
    doe_parser.add_argument(
        "--method",
        choices=["lhs", "random", "grid"],
        default="lhs",
        help="Sampling method (default: lhs)",
    )
    doe_parser.add_argument("--seed", type=int, default=42, help="Random seed")
    doe_parser.add_argument("-j", "--workers", type=int, default=1, help="Parallel workers")

    # pasys report <results>
    report_parser = subparsers.add_parser("report", help="Generate report from results")
    report_parser.add_argument("results", type=Path, help="Results file (parquet/csv)")
    report_parser.add_argument("-o", "--output", type=Path, help="Output file")
    report_parser.add_argument(
        "--format",
        choices=["html", "markdown", "md"],
        default="html",
        help="Report format (default: html)",
    )
    report_parser.add_argument("--title", type=str, help="Report title")

    # pasys pareto <results>
    pareto_parser = subparsers.add_parser("pareto", help="Extract Pareto frontier")
    pareto_parser.add_argument("results", type=Path, help="Results file")
    pareto_parser.add_argument("-x", required=True, help="X-axis metric (minimize)")
    pareto_parser.add_argument("-y", required=True, help="Y-axis metric (maximize)")
    pareto_parser.add_argument("-o", "--output", type=Path, help="Output file")
    pareto_parser.add_argument("--plot", action="store_true", help="Generate plot")

    return parser


def print_metrics_table(metrics: dict[str, Any], title: str = "Metrics") -> None:
    """Print metrics as a formatted table."""
    print(f"\n{title}")
    print("=" * 60)

    # Group metrics by prefix
    groups: dict[str, list[tuple[str, Any]]] = {}
    for key, value in sorted(metrics.items()):
        if key.startswith("meta."):
            group = "Metadata"
        elif key.startswith("verification."):
            group = "Verification"
        elif key in ("g_peak_db", "beamwidth_az_deg", "beamwidth_el_deg", "sll_db", "directivity_db"):
            group = "Antenna"
        elif key in ("eirp_dbw", "path_loss_db", "snr_rx_db", "link_margin_db", "rx_power_dbw"):
            group = "Link Budget"
        elif key in ("snr_single_pulse_db", "snr_integrated_db", "snr_margin_db", "detection_range_m"):
            group = "Radar"
        elif key in ("cost_usd", "recurring_cost_usd", "total_cost_usd"):
            group = "Cost"
        elif key in ("rf_power_w", "dc_power_w", "prime_power_w"):
            group = "Power"
        else:
            group = "Other"

        if group not in groups:
            groups[group] = []
        groups[group].append((key, value))

    # Print each group
    for group_name, items in groups.items():
        print(f"\n{group_name}:")
        for key, value in items:
            if isinstance(value, float):
                if abs(value) > 1000:
                    print(f"  {key}: {value:,.1f}")
                else:
                    print(f"  {key}: {value:.4f}")
            else:
                print(f"  {key}: {value}")


def cmd_run(args: argparse.Namespace) -> int:
    """Execute single-case evaluation."""
    from phased_array_systems.evaluate import evaluate_config
    from phased_array_systems.io import load_config

    if not args.config.exists():
        print(f"Error: Config file not found: {args.config}", file=sys.stderr)
        return 1

    try:
        config = load_config(args.config)
        metrics = evaluate_config(config)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if args.format == "table":
        print_metrics_table(metrics, f"Results for {args.config.name}")
    elif args.format == "json":
        # Convert non-serializable values
        safe_metrics = {k: (v if not isinstance(v, float) or v == v else None) for k, v in metrics.items()}
        print(json.dumps(safe_metrics, indent=2))
    elif args.format == "yaml":
        import yaml
        print(yaml.dump(dict(metrics), default_flow_style=False))

    if args.output:
        with open(args.output, "w") as f:
            json.dump(metrics, f, indent=2)
        print(f"\nSaved to: {args.output}")

    return 0


def cmd_doe(args: argparse.Namespace) -> int:
    """Execute DOE batch study."""
    from phased_array_systems.io import export_results, load_config
    from phased_array_systems.trades import (
        BatchRunner,
        DesignSpace,
        generate_doe,
    )

    if not args.config.exists():
        print(f"Error: Config file not found: {args.config}", file=sys.stderr)
        return 1

    try:
        config = load_config(args.config)
    except Exception as e:
        print(f"Error loading config: {e}", file=sys.stderr)
        return 1

    # Get scenario and requirements
    scenario = config.get_scenario()
    requirements = config.get_requirement_set()

    if scenario is None:
        print("Error: Config must define a scenario", file=sys.stderr)
        return 1

    # Build design space from config
    design_space_config = getattr(config, "design_space", None)
    if design_space_config is None:
        print("Error: Config must define a design_space for DOE", file=sys.stderr)
        return 1

    # Create design space
    design_space = DesignSpace(name=config.name or "DOE")
    for var in design_space_config.get("variables", []):
        design_space.add_variable(
            var["name"],
            type=var["type"],
            low=var.get("low"),
            high=var.get("high"),
            values=var.get("values"),
        )

    print(f"Design Space: {design_space.n_dims} variables")
    print(f"Generating {args.samples} samples using {args.method}...")

    # Generate DOE
    doe = generate_doe(design_space, method=args.method, n_samples=args.samples, seed=args.seed)

    # Run batch
    print("Running batch evaluation...")
    runner = BatchRunner(scenario, requirements)

    def progress(completed: int, total: int) -> None:
        pct = completed / total * 100
        if completed % max(1, total // 10) == 0 or completed == total:
            print(f"  Progress: {completed}/{total} ({pct:.0f}%)")

    results = runner.run(doe, n_workers=args.workers, progress_callback=progress)

    # Summary
    n_total = len(results)
    n_feasible = (results.get("verification.passes", 0) == 1.0).sum()

    print(f"\nCompleted: {n_total} cases")
    print(f"Feasible: {n_feasible} ({n_feasible/n_total*100:.1f}%)")

    # Export
    output_dir = args.output or Path("./results")
    output_dir.mkdir(parents=True, exist_ok=True)

    export_results(results, output_dir / "results.parquet")
    print(f"\nResults saved to: {output_dir / 'results.parquet'}")

    return 0


def cmd_report(args: argparse.Namespace) -> int:
    """Generate report from results."""
    import pandas as pd

    from phased_array_systems.reports import HTMLReport, MarkdownReport, ReportConfig

    if not args.results.exists():
        print(f"Error: Results file not found: {args.results}", file=sys.stderr)
        return 1

    # Load results
    if args.results.suffix == ".parquet":
        results = pd.read_parquet(args.results)
    elif args.results.suffix == ".csv":
        results = pd.read_csv(args.results)
    else:
        print(f"Error: Unsupported format: {args.results.suffix}", file=sys.stderr)
        return 1

    # Configure report
    config = ReportConfig(
        title=args.title or f"Trade Study Report: {args.results.stem}",
    )

    # Generate report
    fmt = args.format if args.format != "md" else "markdown"
    if fmt == "html":
        generator = HTMLReport(config)
        ext = ".html"
    else:
        generator = MarkdownReport(config)
        ext = ".md"

    content = generator.generate(results)

    # Output
    output_path = args.output or args.results.with_suffix(ext)
    generator.save(content, output_path)
    print(f"Report saved to: {output_path}")

    return 0


def cmd_pareto(args: argparse.Namespace) -> int:
    """Extract and display Pareto frontier."""
    import pandas as pd

    from phased_array_systems.io import export_results
    from phased_array_systems.trades import extract_pareto, rank_pareto

    if not args.results.exists():
        print(f"Error: Results file not found: {args.results}", file=sys.stderr)
        return 1

    # Load results
    if args.results.suffix == ".parquet":
        results = pd.read_parquet(args.results)
    elif args.results.suffix == ".csv":
        results = pd.read_csv(args.results)
    else:
        print(f"Error: Unsupported format: {args.results.suffix}", file=sys.stderr)
        return 1

    # Check columns exist
    if args.x not in results.columns:
        print(f"Error: Column '{args.x}' not found in results", file=sys.stderr)
        return 1
    if args.y not in results.columns:
        print(f"Error: Column '{args.y}' not found in results", file=sys.stderr)
        return 1

    # Extract Pareto
    objectives = [
        (args.x, "minimize"),
        (args.y, "maximize"),
    ]

    pareto = extract_pareto(results, objectives)
    ranked = rank_pareto(pareto, objectives)

    print(f"\nPareto Frontier: {len(pareto)} designs")
    print("=" * 70)

    # Show top designs
    for i, (_, row) in enumerate(ranked.head(10).iterrows()):
        case_id = row.get("case_id", f"row_{i}")
        print(f"  {case_id}: {args.x}={row[args.x]:.2f}, {args.y}={row[args.y]:.2f}")

    # Save if requested
    if args.output:
        export_results(ranked, args.output)
        print(f"\nPareto front saved to: {args.output}")

    # Plot if requested
    if args.plot:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(10, 7))
        ax.scatter(results[args.x], results[args.y], alpha=0.5, label="All designs")
        ax.scatter(pareto[args.x], pareto[args.y], c="red", s=100, label="Pareto optimal")

        sorted_pareto = pareto.sort_values(args.x)
        ax.plot(sorted_pareto[args.x], sorted_pareto[args.y], "r--", alpha=0.5)

        ax.set_xlabel(args.x)
        ax.set_ylabel(args.y)
        ax.set_title(f"Pareto Frontier: {args.x} vs {args.y}")
        ax.legend()
        ax.grid(True, alpha=0.3)

        plot_path = args.output.with_suffix(".png") if args.output else Path("pareto_plot.png")
        fig.savefig(plot_path, dpi=150, bbox_inches="tight")
        print(f"Plot saved to: {plot_path}")
        plt.close()

    return 0


def main() -> int:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    commands = {
        "run": cmd_run,
        "doe": cmd_doe,
        "report": cmd_report,
        "pareto": cmd_pareto,
    }

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
