"""Behavioral load-pull model and EdgeFEM active-impedance ingestion.

A power amplifier delivers its rated power into the load it was matched
for. In a phased array the load an element PA sees is the *active*
impedance, which moves with scan angle because of mutual coupling, so
delivered power, PAE, and phase (AM-PM) all become scan-dependent. This
module closes that loop:

- :class:`LoadPullModel`: an analytic contour model mapping a load
  reflection coefficient to delivered-power drop, PAE drop, and AM-PM
  shift. Contours of constant degradation are ellipses around the optimum
  load ``gamma_opt`` — the standard first-order picture of measured
  load-pull contours near the optimum. It is a small-mismatch
  approximation: quadratic in mismatch distance for power and PAE, linear
  for AM-PM.
- :class:`LoadPullTable`: the same interface backed by measured or
  simulated contour data (CSV schema below), interpolated by inverse
  distance weighting. This is the seam where bench load-pull data enters.
- :func:`load_scan_csv`: reads EdgeFEM's ``export_scan_csv`` artifact
  (columns ``theta_deg, phi_deg, element_idx, Gamma_real, Gamma_imag,
  Z_real, Z_imag, VSWR``; degrees, linear Gamma, ohms) into per-scan-angle
  arrays. The format is producer-owned by EdgeFEM; the vendored golden
  fixture under ``tests/fixtures/edgefem/`` pins it.
- :func:`eirp_vs_scan`: per scan angle, runs every element's active Gamma
  through a load-pull model and aggregates the coherent EIRP change and
  mean PAE drop.

Table CSV schema (``LoadPullTable.from_csv``): header
``Gamma_real,Gamma_imag,pout_drop_db,pae_drop_pct,ampm_deg`` — one row per
measured load state, Gamma linear, drops relative to the optimum load.
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

SCAN_CSV_COLUMNS = [
    "theta_deg",
    "phi_deg",
    "element_idx",
    "Gamma_real",
    "Gamma_imag",
    "Z_real",
    "Z_imag",
    "VSWR",
]

TABLE_CSV_COLUMNS = [
    "Gamma_real",
    "Gamma_imag",
    "pout_drop_db",
    "pae_drop_pct",
    "ampm_deg",
]


@dataclass
class LoadPullResult:
    """Degradation of one PA at one load state, relative to the optimum."""

    pout_drop_db: float
    pae_drop_pct: float
    ampm_deg: float


class LoadPullModel:
    """Analytic elliptical-contour load-pull model.

    The mismatch distance is measured in a rotated, scaled frame so that
    contours of constant degradation are ellipses around ``gamma_opt``:

        d = |R(-rot) . (gamma - gamma_opt)| with the minor-axis component
        scaled up by ``contour_axial_ratio``

    and the degradations are

        pout_drop_db = pout_sensitivity_db * d^2
        pae_drop_pct = pae_sensitivity_pct * d^2
        ampm_deg     = ampm_deg_per_gamma * d

    Simplifications, stated plainly: quadratic contours only hold near the
    optimum (real contours flatten toward the Smith chart edge); the model
    has no drive-level dependence (pair it with the Rapp operating-point
    model for that); and AM-PM is direction-independent. For behavior a
    bench characterized, use :class:`LoadPullTable`.

    Args:
        gamma_opt: Optimum load reflection coefficient (complex)
        pout_sensitivity_db: Power drop at unit mismatch distance (dB).
            Survey-typical single-contour spacing puts ~1 dB inside
            |dGamma| ~ 0.2-0.4, i.e. sensitivities of roughly 6-25.
        pae_sensitivity_pct: PAE drop (percentage points) at unit distance
        ampm_deg_per_gamma: AM-PM shift per unit mismatch distance (deg)
        contour_axial_ratio: Ellipse major/minor axis ratio (1 = circles)
        contour_rotation_deg: Major-axis rotation in the Gamma plane (deg)
    """

    def __init__(
        self,
        gamma_opt: complex = 0.0 + 0.0j,
        pout_sensitivity_db: float = 10.0,
        pae_sensitivity_pct: float = 30.0,
        ampm_deg_per_gamma: float = 10.0,
        contour_axial_ratio: float = 1.0,
        contour_rotation_deg: float = 0.0,
    ) -> None:
        if abs(gamma_opt) >= 1.0:
            raise ValueError("gamma_opt must lie inside the unit circle")
        if contour_axial_ratio < 1.0:
            raise ValueError("contour_axial_ratio must be >= 1")
        self.gamma_opt = complex(gamma_opt)
        self.pout_sensitivity_db = pout_sensitivity_db
        self.pae_sensitivity_pct = pae_sensitivity_pct
        self.ampm_deg_per_gamma = ampm_deg_per_gamma
        self.contour_axial_ratio = contour_axial_ratio
        self.contour_rotation_deg = contour_rotation_deg

    def mismatch_distance(self, gamma_load: complex) -> float:
        """Elliptically weighted distance from the optimum load."""
        delta = complex(gamma_load) - self.gamma_opt
        rot = math.radians(self.contour_rotation_deg)
        rotated = delta * complex(math.cos(-rot), math.sin(-rot))
        return math.hypot(rotated.real, rotated.imag * self.contour_axial_ratio)

    def evaluate(self, gamma_load: complex) -> LoadPullResult:
        """Degradation at one load state."""
        d = self.mismatch_distance(gamma_load)
        return LoadPullResult(
            pout_drop_db=self.pout_sensitivity_db * d**2,
            pae_drop_pct=self.pae_sensitivity_pct * d**2,
            ampm_deg=self.ampm_deg_per_gamma * d,
        )


class LoadPullTable:
    """Load-pull behavior interpolated from measured or simulated contours.

    Query points are interpolated by inverse-distance weighting over the
    ``n_neighbors`` nearest table rows; an exact table point returns its
    row unchanged. The table should cover the Gamma region the array will
    actually present (use ``eirp_vs_scan`` diagnostics to check).
    """

    def __init__(
        self,
        gammas: np.ndarray,
        pout_drop_db: np.ndarray,
        pae_drop_pct: np.ndarray,
        ampm_deg: np.ndarray,
        n_neighbors: int = 4,
    ) -> None:
        if not (len(gammas) == len(pout_drop_db) == len(pae_drop_pct) == len(ampm_deg)):
            raise ValueError("all table columns must have equal length")
        if len(gammas) == 0:
            raise ValueError("empty load-pull table")
        self.gammas = np.asarray(gammas, dtype=complex)
        self.pout_drop_db = np.asarray(pout_drop_db, dtype=float)
        self.pae_drop_pct = np.asarray(pae_drop_pct, dtype=float)
        self.ampm_deg = np.asarray(ampm_deg, dtype=float)
        self.n_neighbors = min(n_neighbors, len(self.gammas))

    @classmethod
    def from_csv(cls, path: str | Path) -> LoadPullTable:
        """Read the table CSV schema defined in the module docstring."""
        with open(path, newline="") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames != TABLE_CSV_COLUMNS:
                raise ValueError(
                    f"load-pull table columns {reader.fieldnames} != {TABLE_CSV_COLUMNS}"
                )
            rows = list(reader)
        gammas = np.array([complex(float(r["Gamma_real"]), float(r["Gamma_imag"])) for r in rows])
        return cls(
            gammas=gammas,
            pout_drop_db=np.array([float(r["pout_drop_db"]) for r in rows]),
            pae_drop_pct=np.array([float(r["pae_drop_pct"]) for r in rows]),
            ampm_deg=np.array([float(r["ampm_deg"]) for r in rows]),
        )

    def evaluate(self, gamma_load: complex) -> LoadPullResult:
        """Interpolated degradation at one load state."""
        dist = np.abs(self.gammas - complex(gamma_load))
        exact = np.argmin(dist)
        if dist[exact] < 1e-12:
            return LoadPullResult(
                pout_drop_db=float(self.pout_drop_db[exact]),
                pae_drop_pct=float(self.pae_drop_pct[exact]),
                ampm_deg=float(self.ampm_deg[exact]),
            )
        idx = np.argsort(dist)[: self.n_neighbors]
        w = 1.0 / dist[idx] ** 2
        w /= w.sum()
        return LoadPullResult(
            pout_drop_db=float(np.dot(w, self.pout_drop_db[idx])),
            pae_drop_pct=float(np.dot(w, self.pae_drop_pct[idx])),
            ampm_deg=float(np.dot(w, self.ampm_deg[idx])),
        )


@dataclass
class ScanAngleData:
    """Per-element active-impedance data at one scan angle."""

    theta_deg: float
    phi_deg: float
    gamma: np.ndarray  # complex, per element
    z_ohm: np.ndarray  # complex, per element
    vswr: np.ndarray  # per element


def load_scan_csv(path: str | Path) -> list[ScanAngleData]:
    """Read an EdgeFEM ``export_scan_csv`` artifact.

    Columns are pinned by the EdgeFEM contract fixture (revision 2):
    ``theta_deg, phi_deg, element_idx, Gamma_real, Gamma_imag, Z_real,
    Z_imag, VSWR`` — angles in degrees, Gamma linear, Z in ohms. Rows are
    grouped per scan angle with element indices ascending; this loader
    verifies both.
    """
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != SCAN_CSV_COLUMNS:
            raise ValueError(f"scan CSV columns {reader.fieldnames} != {SCAN_CSV_COLUMNS}")
        rows = list(reader)
    if not rows:
        raise ValueError("empty scan CSV")

    result: list[ScanAngleData] = []
    current_key: tuple[float, float] | None = None
    gammas: list[complex] = []
    zs: list[complex] = []
    vswrs: list[float] = []
    elem_idx: list[int] = []

    def flush() -> None:
        if current_key is None:
            return
        if elem_idx != list(range(len(elem_idx))):
            raise ValueError(f"element indices not ascending from 0 at scan {current_key}")
        result.append(
            ScanAngleData(
                theta_deg=current_key[0],
                phi_deg=current_key[1],
                gamma=np.array(gammas),
                z_ohm=np.array(zs),
                vswr=np.array(vswrs),
            )
        )

    for row in rows:
        key = (float(row["theta_deg"]), float(row["phi_deg"]))
        if key != current_key:
            flush()
            current_key = key
            gammas, zs, vswrs, elem_idx = [], [], [], []
        gammas.append(complex(float(row["Gamma_real"]), float(row["Gamma_imag"])))
        zs.append(complex(float(row["Z_real"]), float(row["Z_imag"])))
        vswrs.append(float(row["VSWR"]))
        elem_idx.append(int(row["element_idx"]))
    flush()
    return result


def eirp_vs_scan(
    scan: list[ScanAngleData],
    model: LoadPullModel | LoadPullTable,
) -> list[dict[str, float]]:
    """Aggregate load-pull degradation over an active-impedance scan.

    Per scan angle, every element's active Gamma runs through the model.
    The EIRP change assumes co-phased elements, so element voltages add:

        eirp_delta_db = 20 log10( mean( 10^(-drop_i / 20) ) )

    which is 0 for a matched array and negative otherwise. This captures
    only the load-pull power term; scan loss from the element pattern is
    accounted elsewhere (the antenna model), and the AM-PM column is
    reported as a mean absolute phase shift for error-budget use, not
    applied to the pattern.

    Returns one dict per scan angle with keys ``theta_deg, phi_deg,
    mean_pout_drop_db, eirp_delta_db, mean_pae_drop_pct,
    mean_abs_ampm_deg, worst_vswr``.
    """
    out: list[dict[str, float]] = []
    for point in scan:
        results = [model.evaluate(g) for g in point.gamma]
        drops = np.array([r.pout_drop_db for r in results])
        paes = np.array([r.pae_drop_pct for r in results])
        ampms = np.array([r.ampm_deg for r in results])
        eirp_delta_db = 20.0 * math.log10(float(np.mean(10.0 ** (-drops / 20.0))))
        out.append(
            {
                "theta_deg": point.theta_deg,
                "phi_deg": point.phi_deg,
                "mean_pout_drop_db": float(np.mean(drops)),
                "eirp_delta_db": eirp_delta_db,
                "mean_pae_drop_pct": float(np.mean(paes)),
                "mean_abs_ampm_deg": float(np.mean(np.abs(ampms))),
                "worst_vswr": float(np.max(point.vswr)),
            }
        )
    return out
