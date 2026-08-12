"""Refresh the vendored EdgeFEM scan fixture from an EdgeFEM checkout.

Usage:
    python scripts/refresh_edgefem_fixture.py /path/to/EdgeFEM/python

Requires an environment where that checkout's `edgefem` package (and its
`pyedgefem` binding) imports. The fixture is producer-owned: regenerate it
here only when EdgeFEM bumps `edgefem.contract.FIXTURE_REVISION`.
phased-array-systems consumes only the scan CSV, so only that file is kept.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

DEST = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "edgefem"


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    edgefem_python = Path(sys.argv[1]).resolve()
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(
            [sys.executable, "-m", "edgefem.contract", tmp],
            cwd=edgefem_python,
            check=True,
        )
        DEST.mkdir(parents=True, exist_ok=True)
        shutil.copy(Path(tmp) / "golden_scan.csv", DEST / "golden_scan.csv")
    print(f"refreshed {DEST / 'golden_scan.csv'}")


if __name__ == "__main__":
    main()
