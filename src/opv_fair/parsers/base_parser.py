"""
Base IV7 Parser — Regex-based
-------------------------------
The IV7 format (both L1 and DC) is a tab-separated file with cp874 encoding.

Header row layout (tab-separated):
  col 0        : barcode
  col 3        : time (s)
  col 5        : pixel
  col 6        : spectrum
  col 8        : temp (°C)
  col 9        : humidity
  col 16       : Jsc (mA/cm2)
  col 17       : Voc (V)
  col 18       : FF
  col 19       : Pmax
  col 20       : Vmpp (V)
  col 21       : Rs (Ohm/cm2)
  col 23       : Rp (Ohm/cm2)
  col 25       : area (cm2)
  col 26       : sweep direction
  col 31+      : IV curve current values (voltages in header, col 32+)

Regex patterns cover:
  - Scientific notation: -1.0000E+0, 2.4700E+1, etc.
  - Barcode format: digits + optional _pixel suffix
  - Spectrum strings: "AM1.5", "5sun", "60degree", etc.
"""

import re
import numpy as np
from pathlib import Path
from typing import Optional

from opv_fair.schema import OPVMeasurement, PVParameters, MeasurementConditions, IVCurveData

# ── Regex patterns ─────────────────────────────────────────────────────────

# Scientific notation float (handles E+, E-, e+, e-)
RE_FLOAT = re.compile(r"^[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?$")

# Barcode: 13-digit number, optionally followed by _N (pixel)
RE_BARCODE = re.compile(r"^(\d{7,16})(?:_(\d+))?$")

# Spectrum: extract sun count or angle info
RE_SPECTRUM = re.compile(r"(\d+(?:\.\d+)?)\s*sun", re.IGNORECASE)
RE_ANGLE    = re.compile(r"(\d+)\s*degree", re.IGNORECASE)

# IV7 encoding
ENCODING = "cp874"

# Column indices (fixed by IV7 format spec)
COL = {
    "barcode": 0,
    "timestamp_s": 3,
    "pixel": 5,
    "spectrum": 6,
    "temp_C": 8,
    "humidity": 9,
    "Jsc": 16,
    "Voc": 17,
    "FF": 18,
    "Pmax": 19,
    "Vmpp": 20,
    "Rs": 21,
    "Rp": 23,
    "area": 25,
    "sweep": 26,
    "iv_start": 31,   # first current value
    "iv_v_start": 32, # first voltage in header
}


def _safe_float(value: str) -> float:
    """Parse float with regex guard; return nan on failure."""
    v = value.strip()
    if RE_FLOAT.match(v):
        return float(v)
    return float("nan")


def _parse_barcode(raw: str) -> tuple[str, str]:
    """Split '2501311325863_8' → ('2501311325863', '8')."""
    m = RE_BARCODE.match(raw.strip())
    if m:
        return m.group(1), (m.group(2) or "")
    return raw.strip(), ""


def _parse_voltages(header_cols: list[str]) -> np.ndarray:
    """
    Extract voltage axis from header row (cols 32+).
    Voltages are stored as scientific notation strings.
    """
    voltages = []
    for col in header_cols[COL["iv_v_start"]:]:
        v = col.strip()
        if RE_FLOAT.match(v):
            voltages.append(float(v))
        else:
            break  # voltages are contiguous; stop at first non-numeric
    return np.array(voltages, dtype=np.float64)


def _parse_currents(row_cols: list[str], n_voltages: int) -> np.ndarray:
    """
    Extract current density values from a data row.
    Current values start at col iv_start+1 and span n_voltages columns.
    """
    start = COL["iv_start"] + 1
    end   = start + n_voltages
    raw_vals = row_cols[start:end]
    currents = np.full(n_voltages, np.nan)
    for i, v in enumerate(raw_vals):
        currents[i] = _safe_float(v)
    return currents


class IV7Parser:
    """
    Regex-based parser for IV7 tab-separated measurement files.
    Subclassed by L1Parser and DCParser (system label only differs).
    """

    SYSTEM: str = "UNKNOWN"

    def parse_file(self, filepath: str | Path) -> list[OPVMeasurement]:
        filepath = Path(filepath)
        raw   = filepath.read_bytes()
        text  = raw.decode(ENCODING, errors="replace")
        lines = text.strip().split("\n")

        if len(lines) < 2:
            return []

        header_cols = lines[0].split("\t")
        voltages    = _parse_voltages(header_cols)
        n_v         = len(voltages)

        measurements: list[OPVMeasurement] = []

        for line in lines[1:]:
            line = line.rstrip("\r")
            if not line.strip():
                continue

            cols = line.split("\t")
            if len(cols) < COL["iv_start"] + 2:
                continue

            m = self._parse_row(cols, voltages, n_v, filepath.name)
            if m is not None:
                measurements.append(m)

        return measurements

    def _parse_row(
        self,
        cols: list[str],
        voltages: np.ndarray,
        n_v: int,
        fname: str,
    ) -> Optional[OPVMeasurement]:

        def col(idx: int) -> str:
            try:
                return cols[idx].strip()
            except IndexError:
                return ""

        # ── Identifiers ──────────────────────────────────────────────────
        barcode_raw  = col(COL["barcode"])
        barcode, pix = _parse_barcode(barcode_raw)

        # Use pixel from barcode suffix if col[5] is empty
        pixel = col(COL["pixel"]) or pix

        # ── IV curve ─────────────────────────────────────────────────────
        currents = _parse_currents(cols, n_v)
        if np.all(np.isnan(currents)):
            return None  # skip empty rows

        # ── PV parameters ─────────────────────────────────────────────────
        pv = PVParameters(
            Jsc_mA_cm2 = _safe_float(col(COL["Jsc"])),
            Voc_V      = _safe_float(col(COL["Voc"])),
            FF         = _safe_float(col(COL["FF"])),
            Pmax_mW    = _safe_float(col(COL["Pmax"])),
            Vmpp_V     = _safe_float(col(COL["Vmpp"])),
            Rs_ohm_cm2 = _safe_float(col(COL["Rs"])),
            Rp_ohm_cm2 = _safe_float(col(COL["Rp"])),
            area_cm2   = _safe_float(col(COL["area"])),
        )

        # PCE = Pmax / (illumination * area) — approximate from Pmax if area known
        if not (np.isnan(pv.Pmax_mW) or np.isnan(pv.area_cm2) or pv.area_cm2 == 0):
            pv.PCE_percent = (pv.Pmax_mW / pv.area_cm2) / 10.0  # mW/cm² → % at 1sun

        # ── Conditions ────────────────────────────────────────────────────
        spectrum_raw = col(COL["spectrum"])
        sweep_raw    = col(COL["sweep"]).lower()
        sweep        = "forward" if "for" in sweep_raw else (
                       "reverse" if "rev" in sweep_raw else "unknown")

        conditions = MeasurementConditions(
            temperature_C = _safe_float(col(COL["temp_C"])),
            humidity_percent = _safe_float(col(COL["humidity"])),
            spectrum      = spectrum_raw,
            sweep_direction = sweep,
        )

        # Extract illumination intensity from spectrum string
        m_sun = RE_SPECTRUM.search(spectrum_raw)
        if m_sun:
            conditions.illumination_intensity = float(m_sun.group(1))

        return OPVMeasurement(
            barcode    = barcode,
            pixel      = pixel,
            system     = self.SYSTEM,
            timestamp_s = _safe_float(col(COL["timestamp_s"])),
            source_file = fname,
            pv         = pv,
            conditions = conditions,
            iv_curve   = IVCurveData(
                voltage_V = voltages,
                current_density_mA_cm2 = currents,
            ),
        )
