#!/usr/bin/env python3
"""
OPV FAIR Pipeline — Demo Script
Usage: python run_pipeline.py [--limit N] [--out ./output]
"""

import argparse
import sys
import time
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent / "src"))

from opv_fair.parsers.l1_parser import L1Parser
from opv_fair.parsers.dc_parser import DCParser, DegradationTempParser
from opv_fair.converters.fair_converter import measurements_to_jsonld, measurements_to_hdf5

# ─────────────────────────────────────────────────────────────────────────────
def banner(t): print(f"\n{'='*60}\n  {t}\n{'='*60}")
def step(n, t): print(f"\n[{n}] {t}")
# ─────────────────────────────────────────────────────────────────────────────

def run(data_root: Path, out_dir: Path, limit: int):
    t0 = time.time()
    banner("OPV Degradation → FAIR Pipeline  (opv-fair v0.1.0)")

    # ── 1. Parse L1 ──────────────────────────────────────────────────────────
    step(1, "L1 Solar Simulator — regex parse")
    l1_parser = L1Parser()
    l1_all = []
    for f in sorted((data_root / "L1").glob("*.txt")):
        ms = l1_parser.parse_file(f)
        l1_all.extend(ms)
        print(f"   {f.name:<55} → {len(ms):>5} measurements")
    print(f"   {'TOTAL L1':55} → {len(l1_all):>5}")

    # ── 2. Parse DC ──────────────────────────────────────────────────────────
    step(2, "DC Degradation Chamber — regex parse")
    dc_parser   = DCParser()
    temp_parser = DegradationTempParser()
    dc_all  = []
    temp_df = pd.DataFrame()

    for f in sorted((data_root / "DC").glob("*")):
        if f.suffix == ".txt":
            ms = dc_parser.parse_file(f)
            dc_all.extend(ms)
            print(f"   {f.name:<55} → {len(ms):>5} measurements")
        elif f.suffix == ".csv":
            temp_df = temp_parser.parse_file(f)
            print(f"   {f.name:<55} → {len(temp_df):>5} temp records "
                  f"(mean {temp_df['temp_mean_C'].mean():.1f}°C)")

    print(f"   {'TOTAL DC':55} → {len(dc_all):>5}")

    # ── 3. Convert → FAIR ────────────────────────────────────────────────────
    step(3, f"Convert → FAIR  (limit={limit} per system for demo)")
    out_dir.mkdir(parents=True, exist_ok=True)

    demo = l1_all[:limit] + dc_all[:limit]
    measurements_to_jsonld(demo, out_dir / "opv_dataset.json")
    measurements_to_hdf5(demo,  out_dir / "opv_dataset.h5")

    # Tidy summary CSV
    rows = [m.to_dict() for m in demo]
    summary = pd.json_normalize(rows, sep="_")
    summary.to_csv(out_dir / "opv_summary.csv", index=False)
    print(f"  ✓ CSV      → {out_dir/'opv_summary.csv'}  ({len(summary)} rows)")

    # ── 4. Stats ─────────────────────────────────────────────────────────────
    step(4, "Dataset statistics")
    pv = summary.filter(regex="pv_")
    print(f"   Unique barcodes  : {summary['barcode'].nunique()}")
    print(f"   L1 measurements  : {len(l1_all):,}  (total parsed)")
    print(f"   DC measurements  : {len(dc_all):,}  (total parsed)")
    for col, label in [
        ("pv_Voc_V",       "Voc [V]       "),
        ("pv_Jsc_mA_cm2",  "Jsc [mA/cm²]  "),
        ("pv_FF",          "FF             "),
        ("pv_PCE_percent", "PCE [%]        "),
    ]:
        if col in summary.columns:
            s = summary[col].dropna()
            if len(s):
                print(f"   {label}: {s.min():.3f} – {s.max():.3f}  (mean {s.mean():.3f})")

    # ── 5. FAIR checklist ────────────────────────────────────────────────────
    step(5, "FAIR compliance")
    checks = [
        ("F", "Findable",      "SHA-256 uid per measurement (barcode+pixel+timestamp+sweep)"),
        ("A", "Accessible",    "Open formats: JSON-LD + HDF5 — no proprietary software"),
        ("I", "Interoperable", "EMMO + QUDT ontology, SI units, NeXus-inspired HDF5"),
        ("R", "Reusable",      "Full provenance: source_file, system, sweep, conditions"),
    ]
    for code, name, detail in checks:
        print(f"   ✓ {code} ({name:<14}) {detail}")

    print(f"\n{'='*60}")
    print(f"  Outputs → {out_dir}/")
    print(f"  Done in {time.time()-t0:.1f}s")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--data",  default="data/raw",  help="Raw data root (default: data/raw)")
    p.add_argument("--out",   default="data/fair", help="Output dir (default: data/fair)")
    p.add_argument("--limit", default=500, type=int, help="Measurements per system in demo outputs")
    args = p.parse_args()

    run(Path(args.data), Path(args.out), args.limit)
