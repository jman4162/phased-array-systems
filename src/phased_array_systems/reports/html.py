"""HTML report generator."""

from __future__ import annotations

from typing import Any

import pandas as pd

from phased_array_systems.reports.generator import ReportConfig, ReportGenerator


class HTMLReport(ReportGenerator):
    """Generate HTML reports from trade study results."""

    def __init__(self, config: ReportConfig | None = None):
        """Initialize the HTML report generator.

        Args:
            config: Report configuration
        """
        super().__init__(config)

    def generate(self, results: pd.DataFrame) -> str:
        """Generate HTML report content.

        Args:
            results: DataFrame with trade study results

        Returns:
            Complete HTML document as string
        """
        metadata = self._get_metadata()
        stats = self._compute_summary_stats(results)
        columns = self._identify_columns(results)

        sections = []

        # Summary section
        if self.config.include_summary:
            sections.append(self._generate_summary_section(stats, columns))

        # Results table section
        sections.append(self._generate_table_section(results, columns))

        # Statistics section
        sections.append(self._generate_statistics_section(results, columns))

        return self._wrap_html(sections, metadata)

    def _wrap_html(self, sections: list[str], metadata: dict[str, Any]) -> str:
        """Wrap sections in HTML document structure.

        Args:
            sections: List of HTML section strings
            metadata: Report metadata

        Returns:
            Complete HTML document
        """
        title = metadata.get("title", "Trade Study Report")
        description = metadata.get("description", "")
        generated_at = metadata.get("generated_at", "")
        version = metadata.get("generator_version", "")

        header_meta = ""
        if description:
            header_meta += f'<p class="description">{description}</p>'
        if metadata.get("author"):
            header_meta += f'<p class="author">Author: {metadata["author"]}</p>'

        body_content = "\n".join(sections)

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="generator" content="phased-array-systems v{version}">
    <title>{title}</title>
    <style>
        :root {{
            --primary-color: #2563eb;
            --success-color: #16a34a;
            --warning-color: #ca8a04;
            --danger-color: #dc2626;
            --bg-color: #f8fafc;
            --card-bg: #ffffff;
            --text-color: #1e293b;
            --border-color: #e2e8f0;
        }}
        * {{
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: var(--text-color);
            background-color: var(--bg-color);
            margin: 0;
            padding: 20px;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        header {{
            background: linear-gradient(135deg, var(--primary-color), #1d4ed8);
            color: white;
            padding: 30px;
            border-radius: 12px;
            margin-bottom: 30px;
        }}
        header h1 {{
            margin: 0 0 10px 0;
            font-size: 2em;
        }}
        header .description {{
            margin: 10px 0;
            opacity: 0.9;
        }}
        header .author {{
            margin: 5px 0;
            font-size: 0.9em;
            opacity: 0.8;
        }}
        header .meta {{
            font-size: 0.85em;
            opacity: 0.7;
            margin-top: 15px;
        }}
        .card {{
            background: var(--card-bg);
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            padding: 25px;
            margin-bottom: 25px;
        }}
        .card h2 {{
            margin-top: 0;
            color: var(--primary-color);
            border-bottom: 2px solid var(--border-color);
            padding-bottom: 10px;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }}
        .stat-box {{
            background: var(--bg-color);
            padding: 20px;
            border-radius: 8px;
            text-align: center;
        }}
        .stat-box .value {{
            font-size: 2em;
            font-weight: bold;
            color: var(--primary-color);
        }}
        .stat-box .label {{
            font-size: 0.9em;
            color: #64748b;
            margin-top: 5px;
        }}
        .stat-box.success .value {{
            color: var(--success-color);
        }}
        .stat-box.warning .value {{
            color: var(--warning-color);
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9em;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid var(--border-color);
        }}
        th {{
            background: var(--bg-color);
            font-weight: 600;
            position: sticky;
            top: 0;
        }}
        tr:hover {{
            background: #f1f5f9;
        }}
        .table-container {{
            overflow-x: auto;
            max-height: 500px;
            overflow-y: auto;
        }}
        .pass {{
            color: var(--success-color);
            font-weight: bold;
        }}
        .fail {{
            color: var(--danger-color);
            font-weight: bold;
        }}
        .metric-stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 15px;
        }}
        .metric-card {{
            background: var(--bg-color);
            padding: 15px;
            border-radius: 6px;
        }}
        .metric-card h4 {{
            margin: 0 0 10px 0;
            font-size: 0.95em;
            color: var(--text-color);
        }}
        .metric-card .stat-row {{
            display: flex;
            justify-content: space-between;
            padding: 5px 0;
            font-size: 0.85em;
        }}
        .metric-card .stat-row .label {{
            color: #64748b;
        }}
        footer {{
            text-align: center;
            padding: 20px;
            color: #64748b;
            font-size: 0.85em;
        }}
        footer a {{
            color: var(--primary-color);
            text-decoration: none;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>{title}</h1>
            {header_meta}
            <p class="meta">Generated: {generated_at} | phased-array-systems v{version}</p>
        </header>
        {body_content}
        <footer>
            Generated by <a href="https://github.com/johnhodge/phased-array-systems">phased-array-systems</a>
        </footer>
    </div>
</body>
</html>"""

    def _generate_summary_section(
        self, stats: dict[str, Any], columns: dict[str, list[str]]
    ) -> str:
        """Generate summary statistics section.

        Args:
            stats: Summary statistics dictionary
            columns: Column classification dictionary

        Returns:
            HTML string for summary section
        """
        n_cases = stats.get("n_cases", 0)
        n_feasible = stats.get("n_feasible", "N/A")
        feasible_pct = stats.get("feasible_pct", 0)
        n_inputs = len(columns.get("input", []))
        n_outputs = len(columns.get("output", []))

        feasible_class = ""
        if isinstance(n_feasible, int):
            if feasible_pct >= 50:
                feasible_class = "success"
            elif feasible_pct >= 20:
                feasible_class = "warning"

        feasible_display = f"{n_feasible} ({feasible_pct:.1f}%)" if isinstance(n_feasible, int) else n_feasible

        return f"""
        <div class="card">
            <h2>Summary</h2>
            <div class="stats-grid">
                <div class="stat-box">
                    <div class="value">{n_cases}</div>
                    <div class="label">Total Cases</div>
                </div>
                <div class="stat-box {feasible_class}">
                    <div class="value">{feasible_display}</div>
                    <div class="label">Feasible Designs</div>
                </div>
                <div class="stat-box">
                    <div class="value">{n_inputs}</div>
                    <div class="label">Input Variables</div>
                </div>
                <div class="stat-box">
                    <div class="value">{n_outputs}</div>
                    <div class="label">Output Metrics</div>
                </div>
            </div>
        </div>
        """

    def _generate_table_section(
        self, results: pd.DataFrame, columns: dict[str, list[str]]
    ) -> str:
        """Generate results table section.

        Args:
            results: DataFrame with results
            columns: Column classification dictionary

        Returns:
            HTML string for table section
        """
        # Select columns to display
        display_cols = []

        # Add case_id if present
        if "case_id" in results.columns:
            display_cols.append("case_id")

        # Add verification passes if present
        if "verification.passes" in results.columns:
            display_cols.append("verification.passes")

        # Add input columns
        display_cols.extend(columns.get("input", [])[:10])

        # Add key output columns
        key_outputs = [
            "g_peak_db", "eirp_dbw", "snr_rx_db", "link_margin_db",
            "snr_margin_db", "detection_range_m", "cost_usd", "prime_power_w"
        ]
        for col in key_outputs:
            if col in results.columns and col not in display_cols:
                display_cols.append(col)

        # Limit rows
        display_df = results[display_cols].head(self.config.max_rows)

        # Build table HTML
        header_cells = "".join(f"<th>{col}</th>" for col in display_cols)

        rows = []
        for _, row in display_df.iterrows():
            cells = []
            for col in display_cols:
                val = row[col]
                if col == "verification.passes":
                    cell_class = "pass" if val == 1.0 else "fail"
                    cell_text = "PASS" if val == 1.0 else "FAIL"
                    cells.append(f'<td class="{cell_class}">{cell_text}</td>')
                elif isinstance(val, float):
                    if abs(val) > 10000:
                        cells.append(f"<td>{val:,.0f}</td>")
                    else:
                        cells.append(f"<td>{val:.3f}</td>")
                else:
                    cells.append(f"<td>{val}</td>")
            rows.append(f"<tr>{''.join(cells)}</tr>")

        table_rows = "\n".join(rows)
        n_shown = len(display_df)
        n_total = len(results)
        showing_text = f"Showing {n_shown} of {n_total} cases" if n_shown < n_total else f"Showing all {n_total} cases"

        return f"""
        <div class="card">
            <h2>Results</h2>
            <p>{showing_text}</p>
            <div class="table-container">
                <table>
                    <thead>
                        <tr>{header_cells}</tr>
                    </thead>
                    <tbody>
                        {table_rows}
                    </tbody>
                </table>
            </div>
        </div>
        """

    def _generate_statistics_section(
        self, results: pd.DataFrame, columns: dict[str, list[str]]
    ) -> str:
        """Generate statistics section for key metrics.

        Args:
            results: DataFrame with results
            columns: Column classification dictionary

        Returns:
            HTML string for statistics section
        """
        # Identify key numeric output columns
        output_cols = columns.get("output", [])
        numeric_outputs = [
            col for col in output_cols
            if col in results.columns and pd.api.types.is_numeric_dtype(results[col])
        ]

        # Prioritize certain metrics
        priority_metrics = [
            "g_peak_db", "eirp_dbw", "snr_rx_db", "link_margin_db",
            "snr_margin_db", "detection_range_m", "cost_usd", "prime_power_w",
            "dc_power_w", "n_elements"
        ]

        display_metrics = []
        for m in priority_metrics:
            if m in numeric_outputs:
                display_metrics.append(m)

        # Add remaining metrics up to 12 total
        for m in numeric_outputs:
            if m not in display_metrics and len(display_metrics) < 12:
                display_metrics.append(m)

        if not display_metrics:
            return ""

        metric_cards = []
        for metric in display_metrics:
            col = results[metric].dropna()
            if len(col) == 0:
                continue

            stats_rows = f"""
                <div class="stat-row"><span class="label">Min</span><span>{col.min():.3f}</span></div>
                <div class="stat-row"><span class="label">Max</span><span>{col.max():.3f}</span></div>
                <div class="stat-row"><span class="label">Mean</span><span>{col.mean():.3f}</span></div>
                <div class="stat-row"><span class="label">Std Dev</span><span>{col.std():.3f}</span></div>
            """
            metric_cards.append(f"""
                <div class="metric-card">
                    <h4>{metric}</h4>
                    {stats_rows}
                </div>
            """)

        return f"""
        <div class="card">
            <h2>Metric Statistics</h2>
            <div class="metric-stats">
                {''.join(metric_cards)}
            </div>
        </div>
        """
