"""Markdown report generator."""

from __future__ import annotations

from typing import Any

import pandas as pd

from phased_array_systems.reports.generator import ReportConfig, ReportGenerator


class MarkdownReport(ReportGenerator):
    """Generate Markdown reports from trade study results."""

    def __init__(self, config: ReportConfig | None = None):
        """Initialize the Markdown report generator.

        Args:
            config: Report configuration
        """
        super().__init__(config)

    def generate(self, results: pd.DataFrame) -> str:
        """Generate Markdown report content.

        Args:
            results: DataFrame with trade study results

        Returns:
            Markdown document as string
        """
        metadata = self._get_metadata()
        stats = self._compute_summary_stats(results)
        columns = self._identify_columns(results)

        sections = []

        # Title and metadata
        sections.append(self._generate_header(metadata))

        # Summary section
        if self.config.include_summary:
            sections.append(self._generate_summary_section(stats, columns))

        # Results table section
        sections.append(self._generate_table_section(results, columns))

        # Statistics section
        sections.append(self._generate_statistics_section(results, columns))

        # Footer
        sections.append(self._generate_footer(metadata))

        return "\n\n".join(sections)

    def _generate_header(self, metadata: dict[str, Any]) -> str:
        """Generate report header.

        Args:
            metadata: Report metadata

        Returns:
            Markdown string for header
        """
        title = metadata.get("title", "Trade Study Report")
        lines = [f"# {title}"]

        if metadata.get("description"):
            lines.append(f"\n{metadata['description']}")

        meta_items = []
        if metadata.get("author"):
            meta_items.append(f"**Author:** {metadata['author']}")
        meta_items.append(f"**Generated:** {metadata.get('generated_at', 'N/A')}")
        meta_items.append(f"**Version:** phased-array-systems v{metadata.get('generator_version', 'N/A')}")

        lines.append("\n" + " | ".join(meta_items))

        return "\n".join(lines)

    def _generate_summary_section(
        self, stats: dict[str, Any], columns: dict[str, list[str]]
    ) -> str:
        """Generate summary statistics section.

        Args:
            stats: Summary statistics dictionary
            columns: Column classification dictionary

        Returns:
            Markdown string for summary section
        """
        lines = ["## Summary"]

        n_cases = stats.get("n_cases", 0)
        n_feasible = stats.get("n_feasible", "N/A")
        feasible_pct = stats.get("feasible_pct", 0)
        n_inputs = len(columns.get("input", []))
        n_outputs = len(columns.get("output", []))

        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| Total Cases | {n_cases} |")

        if isinstance(n_feasible, int):
            lines.append(f"| Feasible Designs | {n_feasible} ({feasible_pct:.1f}%) |")

        lines.append(f"| Input Variables | {n_inputs} |")
        lines.append(f"| Output Metrics | {n_outputs} |")

        return "\n".join(lines)

    def _generate_table_section(
        self, results: pd.DataFrame, columns: dict[str, list[str]]
    ) -> str:
        """Generate results table section.

        Args:
            results: DataFrame with results
            columns: Column classification dictionary

        Returns:
            Markdown string for table section
        """
        lines = ["## Results"]

        # Select columns to display
        display_cols = []

        # Add case_id if present
        if "case_id" in results.columns:
            display_cols.append("case_id")

        # Add verification passes if present
        if "verification.passes" in results.columns:
            display_cols.append("verification.passes")

        # Add key input columns (limit to fit in table)
        input_cols = columns.get("input", [])[:5]
        display_cols.extend(input_cols)

        # Add key output columns
        key_outputs = [
            "g_peak_db", "eirp_dbw", "link_margin_db",
            "snr_margin_db", "cost_usd"
        ]
        for col in key_outputs:
            if col in results.columns and col not in display_cols:
                display_cols.append(col)

        # Limit columns for readability
        display_cols = display_cols[:10]

        # Limit rows
        display_df = results[display_cols].head(self.config.max_rows)

        n_shown = len(display_df)
        n_total = len(results)
        if n_shown < n_total:
            lines.append(f"\n*Showing {n_shown} of {n_total} cases*\n")

        # Build table header
        header = "| " + " | ".join(display_cols) + " |"
        separator = "| " + " | ".join(["---"] * len(display_cols)) + " |"
        lines.append(header)
        lines.append(separator)

        # Build table rows
        for _, row in display_df.iterrows():
            cells = []
            for col in display_cols:
                val = row[col]
                if col == "verification.passes":
                    cells.append("PASS" if val == 1.0 else "FAIL")
                elif isinstance(val, float):
                    if abs(val) > 10000:
                        cells.append(f"{val:,.0f}")
                    else:
                        cells.append(f"{val:.2f}")
                else:
                    cells.append(str(val))
            lines.append("| " + " | ".join(cells) + " |")

        return "\n".join(lines)

    def _generate_statistics_section(
        self, results: pd.DataFrame, columns: dict[str, list[str]]
    ) -> str:
        """Generate statistics section for key metrics.

        Args:
            results: DataFrame with results
            columns: Column classification dictionary

        Returns:
            Markdown string for statistics section
        """
        lines = ["## Metric Statistics"]

        # Identify key numeric output columns
        output_cols = columns.get("output", [])
        numeric_outputs = [
            col for col in output_cols
            if col in results.columns and pd.api.types.is_numeric_dtype(results[col])
        ]

        # Prioritize certain metrics
        priority_metrics = [
            "g_peak_db", "eirp_dbw", "snr_rx_db", "link_margin_db",
            "snr_margin_db", "detection_range_m", "cost_usd", "prime_power_w"
        ]

        display_metrics = []
        for m in priority_metrics:
            if m in numeric_outputs:
                display_metrics.append(m)

        # Add remaining metrics up to 8 total
        for m in numeric_outputs:
            if m not in display_metrics and len(display_metrics) < 8:
                display_metrics.append(m)

        if not display_metrics:
            return ""

        # Build statistics table
        lines.append("")
        lines.append("| Metric | Min | Max | Mean | Std Dev |")
        lines.append("|--------|-----|-----|------|---------|")

        for metric in display_metrics:
            col = results[metric].dropna()
            if len(col) == 0:
                continue

            lines.append(
                f"| {metric} | {col.min():.3f} | {col.max():.3f} | "
                f"{col.mean():.3f} | {col.std():.3f} |"
            )

        return "\n".join(lines)

    def _generate_footer(self, metadata: dict[str, Any]) -> str:
        """Generate report footer.

        Args:
            metadata: Report metadata

        Returns:
            Markdown string for footer
        """
        version = metadata.get("generator_version", "N/A")
        return f"""---

*Generated by [phased-array-systems](https://github.com/johnhodge/phased-array-systems) v{version}*"""
