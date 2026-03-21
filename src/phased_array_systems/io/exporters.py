"""Results export utilities."""

import json
from pathlib import Path
from typing import Literal

import pandas as pd


def export_results(
    results: pd.DataFrame,
    path: str | Path,
    format: Literal["parquet", "csv", "json"] | None = None,
    include_metadata: bool = True,
) -> Path:
    """Export evaluation results to file.

    Args:
        results: DataFrame with evaluation results
        path: Output file path
        format: Output format (auto-detected from extension if None)
        include_metadata: Include export metadata (timestamp, version)

    Returns:
        Path to exported file
    """
    path = Path(path)

    if format is None:
        suffix = path.suffix.lower()
        if suffix == ".parquet":
            format = "parquet"
        elif suffix == ".csv":
            format = "csv"
        elif suffix == ".json":
            format = "json"
        else:
            format = "parquet"  # Default

    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    if format == "parquet":
        _export_parquet(results, path, include_metadata)
    elif format == "csv":
        _export_csv(results, path)
    elif format == "json":
        _export_json(results, path, include_metadata)
    else:
        raise ValueError(f"Unknown format: {format}")

    return path


def _export_parquet(
    results: pd.DataFrame,
    path: Path,
    include_metadata: bool,
) -> None:
    """Export to Parquet format with optional metadata."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    table = pa.Table.from_pandas(results)

    if include_metadata:
        from datetime import datetime

        from phased_array_systems import __version__

        custom_meta = {
            "export_timestamp": datetime.now().isoformat(),
            "package_version": __version__,
            "n_cases": str(len(results)),
        }

        existing_meta = table.schema.metadata or {}
        merged_meta = {**existing_meta, **{k.encode(): v.encode() for k, v in custom_meta.items()}}
        table = table.replace_schema_metadata(merged_meta)

    pq.write_table(table, path)


def _export_csv(results: pd.DataFrame, path: Path) -> None:
    """Export to CSV format."""
    results.to_csv(path, index=False)


def _export_json(
    results: pd.DataFrame,
    path: Path,
    include_metadata: bool,
) -> None:
    """Export to JSON format."""
    data = results.to_dict(orient="records")

    if include_metadata:
        from datetime import datetime

        from phased_array_systems import __version__

        output = {
            "metadata": {
                "export_timestamp": datetime.now().isoformat(),
                "package_version": __version__,
                "n_cases": len(results),
            },
            "results": data,
        }
    else:
        output = {"results": data}

    with open(path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, default=str)


def load_results(path: str | Path) -> pd.DataFrame:
    """Load previously exported results.

    Args:
        path: Path to results file

    Returns:
        DataFrame with results
    """
    path = Path(path)
    suffix = path.suffix.lower()

    if suffix == ".parquet":
        return pd.read_parquet(path)
    elif suffix == ".csv":
        return pd.read_csv(path)
    elif suffix == ".json":
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if "results" in data:
            return pd.DataFrame(data["results"])
        else:
            return pd.DataFrame(data)
    else:
        raise ValueError(f"Unknown format: {suffix}")


def get_export_metadata(path: str | Path) -> dict | None:
    """Get metadata from an exported results file.

    Args:
        path: Path to results file

    Returns:
        Metadata dictionary or None if no metadata
    """
    path = Path(path)
    suffix = path.suffix.lower()

    if suffix == ".parquet":
        import pyarrow.parquet as pq

        meta = pq.read_metadata(path)
        if meta.schema.metadata:
            return {
                k.decode(): v.decode()
                for k, v in meta.schema.metadata.items()
                if k.decode().startswith(("export_", "package_", "n_"))
            }
        return None

    elif suffix == ".json":
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("metadata")

    else:
        return None
