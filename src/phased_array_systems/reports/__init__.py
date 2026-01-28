"""Report generation for trade study results."""

from phased_array_systems.reports.generator import ReportConfig
from phased_array_systems.reports.html import HTMLReport
from phased_array_systems.reports.markdown import MarkdownReport

__all__ = [
    "HTMLReport",
    "MarkdownReport",
    "ReportConfig",
]
