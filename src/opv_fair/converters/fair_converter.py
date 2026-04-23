"""
FAIR Converter
--------------
Converts OPVMeasurement objects → JSON-LD + HDF5.

FAIR mapping:
  F — SHA-256 uid per measurement (barcode+pixel+timestamp+sweep)
  A — JSON-LD (human+machine readable), HDF5 (binary open standard)
  I — EMMO / QUDT ontology annotations
  R — Full provenance in every record (source_file, system, conditions)
"""

import json
import os
import numpy as np
from datetime import datetime, timezone
from pathlib import Path

os.environ["HDF5_USE_FILE_LOCKING"] = "FALSE"
import h5py

from opv_fair.schema import OPVMeasurement

# JSON-LD context — links quantities to ontologies
JSONLD_CONTEXT = {
    "emmo":   "https://emmo.info/emmo#",
    "qudt":   "http://qudt.org/vocab/unit/",
    "schema": "https://schema.org/",
    "opv":    "https://github.com/opv-fair/ontology#",
    "Jsc":    {"@id": "opv:ShortCircuitCurrentDensity", "@type": "qudt:MilliamperePerCentimetre2"},
    "Voc":    {"@id": "opv:OpenCircuitVoltage",         "@type": "qudt:V"},
    "FF":     {"@id": "opv:FillFactor",                 "@type": "qudt:UNITLESS"},
    "PCE":    {"@id": "opv:PowerConversionEfficiency",  "@type": "qudt:PERCENT"},
    "Rs":     {"@id": "emmo:SeriesResistance",          "@type": "qudt:OHM"},
    "Rp":     {"@id": "emmo:ShuntResistance",           "@type": "qudt:OHM"},
}


def measurements_to_jsonld(measurements: list[OPVMeasurement], output_path: str | Path):
    """Write FAIR JSON-LD dataset."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    entries = []
    for m in measurements:
        d = m.to_dict()
        d["@type"]  = "opv:IVMeasurement"
        d["@id"]    = f"opv:measurement/{d['uid']}"
        entries.append(d)

    dataset = {
        "@context": JSONLD_CONTEXT,
        "@type": "opv:Dataset",
        "schema:name": "OPV Degradation IV Dataset",
        "schema:datePublished": datetime.now(timezone.utc).isoformat(),
        "schema:version": "1.0.0",
        "opv:measurements": entries,
    }

    output_path.write_text(json.dumps(dataset, indent=2, ensure_ascii=False))
    print(f"  ✓ JSON-LD  → {output_path}  ({len(measurements)} entries)")


def measurements_to_hdf5(measurements: list[OPVMeasurement], output_path: str | Path):
    """
    Write FAIR HDF5 (NeXus-inspired hierarchy).

    Structure:
      /measurement_00000/
        attrs: uid, barcode, pixel, system, source_file, timestamp_s
        /pv_params/  Jsc, Voc, FF, PCE, Pmax, Vmpp, Rs, Rp, area
        /conditions/ temperature_C, humidity, spectrum, sweep_direction
        /iv_curve/   voltage [V], current_density [mA/cm2]
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with h5py.File(output_path, "w") as f:
        f.attrs["NX_class"]    = "NXroot"
        f.attrs["file_time"]   = datetime.now(timezone.utc).isoformat()
        f.attrs["creator"]     = "opv-fair v0.1.0"
        f.attrs["FAIR_schema"] = "https://github.com/opv-fair/ontology"

        for i, m in enumerate(measurements):
            g = f.create_group(f"measurement_{i:05d}")
            g.attrs["uid"]         = m.uid()
            g.attrs["barcode"]     = m.barcode
            g.attrs["pixel"]       = m.pixel
            g.attrs["system"]      = m.system
            g.attrs["source_file"] = m.source_file
            g.attrs["timestamp_s"] = _nan_to_neg1(m.timestamp_s)

            # PV parameters
            pv = g.create_group("pv_params")
            _ds(pv, "Jsc",  m.pv.Jsc_mA_cm2,  "mA/cm2",   "Short-circuit current density")
            _ds(pv, "Voc",  m.pv.Voc_V,         "V",         "Open-circuit voltage")
            _ds(pv, "FF",   m.pv.FF,             "",          "Fill factor")
            _ds(pv, "PCE",  m.pv.PCE_percent,    "%",         "Power conversion efficiency")
            _ds(pv, "Pmax", m.pv.Pmax_mW,        "mW",        "Maximum power")
            _ds(pv, "Vmpp", m.pv.Vmpp_V,         "V",         "Voltage at Pmax")
            _ds(pv, "Rs",   m.pv.Rs_ohm_cm2,     "Ohm*cm2",  "Series resistance")
            _ds(pv, "Rp",   m.pv.Rp_ohm_cm2,     "Ohm*cm2",  "Shunt resistance")
            _ds(pv, "area", m.pv.area_cm2,        "cm2",       "Active area")

            # Conditions
            cond = g.create_group("conditions")
            _ds(cond, "temperature_C", m.conditions.temperature_C, "degC", "Cell temperature")
            _ds(cond, "humidity",      m.conditions.humidity_percent, "%",  "Relative humidity")
            cond.attrs["spectrum"]         = m.conditions.spectrum
            cond.attrs["sweep_direction"]  = m.conditions.sweep_direction

            # IV curve
            iv = g.create_group("iv_curve")
            ds_v = iv.create_dataset("voltage", data=m.iv_curve.voltage_V)
            ds_v.attrs["units"] = "V"
            ds_i = iv.create_dataset("current_density", data=m.iv_curve.current_density_mA_cm2)
            ds_i.attrs["units"] = "mA/cm2"

    print(f"  ✓ HDF5     → {output_path}  ({len(measurements)} entries)")


def _ds(group, name: str, value: float, unit: str, description: str = ""):
    """Create scalar dataset with unit attribute."""
    v = float("nan") if (value is None or (isinstance(value, float) and np.isnan(value))) else float(value)
    ds = group.create_dataset(name, data=v)
    ds.attrs["units"]       = unit
    ds.attrs["description"] = description


def _nan_to_neg1(v):
    return -1.0 if (v is None or np.isnan(float(v))) else float(v)
