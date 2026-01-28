"""Base report configuration and generator classes."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from phased_array_systems import __version__


@dataclass
class ReportConfig:
    """Configuration for report generation.

    Attributes:
        title: Report title
        description: Optional report description
        author: Optional author name
        include_summary: Include summary statistics section
        include_pareto: Include Pareto frontier analysis
        include_plots: Include visualization plots
        max_rows: Maximum rows to show in tables (0 = all)
        objectives: List of (metric, direction) for Pareto analysis
        key_metrics: Metrics to highlight in summary
    """

    title: str = "Trade Study Report"
    description: str | None = None
    author: str | None = None
    include_summary: bool = True
    include_pareto: bool = True
    include_plots: bool = True
    max_rows: int = 50
    objectives: list[tuple[str, str]] = field(default_factory=list)
    key_metrics: list[str] = field(default_factory=list)


@dataclass
class ReportSection:
    """A section of the report.

    Attributes:
        title: Section title
        content: Section content (HTML or Markdown)
        level: Heading level (1-6)
    """

    title: str
    content: str
    level: int = 2


class ReportGenerator(ABC):
    """Abstract base class for report generators."""

    def __init__(self, config: ReportConfig | None = None):
        """Initialize the report generator.

        Args:
            config: Report configuration. Uses defaults if not provided.
        """
        self.config = config or ReportConfig()

    @abstractmethod
    def generate(self, results: pd.DataFrame) -> str:
        """Generate the report content.

        Args:
            results: DataFrame with trade study results

        Returns:
            Report content as string (HTML or Markdown)
        """
        pass

    def save(self, content: str, path: Path | str) -> None:
        """Save report content to file.

        Args:
            content: Report content string
            path: Output file path
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def _get_metadata(self) -> dict[str, Any]:
        """Get report metadata."""
        return {
            "generated_at": datetime.now().isoformat(),
            "generator_version": __version__,
            "title": self.config.title,
            "description": self.config.description,
            "author": self.config.author,
        }

    def _compute_summary_stats(self, results: pd.DataFrame) -> dict[str, Any]:
        """Compute summary statistics from results.

        Args:
            results: DataFrame with trade study results

        Returns:
            Dictionary with summary statistics
        """
        stats: dict[str, Any] = {
            "n_cases": len(results),
            "n_columns": len(results.columns),
        }

        # Check for feasibility column
        if "verification.passes" in results.columns:
            n_feasible = (results["verification.passes"] == 1.0).sum()
            stats["n_feasible"] = int(n_feasible)
            stats["feasible_pct"] = n_feasible / len(results) * 100 if len(results) > 0 else 0

        # Compute stats for numeric columns
        numeric_cols = results.select_dtypes(include=["number"]).columns
        stats["numeric_columns"] = len(numeric_cols)

        # Key metrics stats
        key_stats = {}
        for metric in self.config.key_metrics:
            if metric in results.columns:
                col = results[metric]
                key_stats[metric] = {
                    "min": col.min(),
                    "max": col.max(),
                    "mean": col.mean(),
                    "std": col.std(),
                }
        stats["key_metrics"] = key_stats

        return stats

    def _identify_columns(self, results: pd.DataFrame) -> dict[str, list[str]]:
        """Identify column types in results.

        Args:
            results: DataFrame with trade study results

        Returns:
            Dictionary mapping column type to list of column names
        """
        columns: dict[str, list[str]] = {
            "input": [],
            "output": [],
            "metadata": [],
            "verification": [],
        }

        for col in results.columns:
            if col.startswith("meta."):
                columns["metadata"].append(col)
            elif col.startswith("verification."):
                columns["verification"].append(col)
            elif "." in col and col.split(".")[0] in ("array", "rf", "cost"):
                columns["input"].append(col)
            else:
                columns["output"].append(col)

        return columns
