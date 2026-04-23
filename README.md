# opv-fair — FAIR Pipeline for OPV Degradation Data

NOMAD-compatible parser + FAIR converter for OPV IV measurements (L1 + DC systems).

## Quick Start (local)

```bash
git clone https://github.com/YOUR_USERNAME/opv-fair
cd opv-fair

pip install -e .           # installs package + entry points
python run_pipeline.py     # runs full pipeline
```

Output in `data/fair/`: `opv_dataset.json` · `opv_dataset.h5` · `opv_summary.csv`

## Docker

```bash
docker build -t opv-fair .
docker run -v $(pwd)/data:/app/data opv-fair
```

## Project Structure

```
opv-fair/
├── src/opv_fair/
│   ├── schema.py                  # MetaInfo: OPVMeasurement, PVParameters, ...
│   ├── parsers/
│   │   ├── base_parser.py         # IV7Parser — regex-based core
│   │   ├── l1_parser.py           # L1Parser  (solar simulator)
│   │   └── dc_parser.py           # DCParser  (degradation chamber) + TempParser
│   └── converters/
│       └── fair_converter.py      # → JSON-LD + HDF5
├── data/raw/
│   ├── L1/                        # IV7 .txt files (cp874)
│   └── DC/                        # IV7 .txt + DegradationTemp .csv
├── run_pipeline.py                # CLI entry point
├── Dockerfile
└── pyproject.toml                 # NOMAD plugin entry points
```

## Data Format

IV7 tab-separated, encoding `cp874`. Both L1 and DC share the same format:

| Cols | Content |
|------|---------|
| 0, 3, 5–6, 8–9 | barcode, timestamp, pixel, spectrum, T, RH |
| 16–25 | Jsc · Voc · FF · Pmax · Vmpp · Rs · Rp · area |
| 26 | sweep direction (forward/reverse) |
| 32+ | voltage axis (header) / current density rows |

Regex pattern for floats: `^[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?$`

## FAIR Compliance

| | Principle | Implementation |
|--|-----------|---------------|
| **F** | Findable | SHA-256 uid = `hash(barcode + pixel + timestamp + sweep)` |
| **A** | Accessible | JSON-LD + HDF5 — open formats, no licence required |
| **I** | Interoperable | EMMO + QUDT ontology annotations, NeXus-inspired HDF5 |
| **R** | Reusable | Full provenance in every record (source_file, system, conditions) |

## NOMAD Integration

Registered as NOMAD plugin via `pyproject.toml` entry points:
- `opv_parser_l1` → matches `*IV7*.txt`
- `opv_parser_dc` → matches `*deg_chamb*.txt`
- `opv_schema`    → OPVMeasurement MetaInfo section

Install into a NOMAD Oasis:
```bash
pip install -e ".[dev]"
# add to nomad.yaml plugins list: opv_fair
```

## Dataset (from your files)

| System | Files | Measurements |
|--------|-------|-------------|
| L1 (solar sim) | 4 | 18,234 |
| DC (deg. chamber) | 4 | 21,127 |
| Temperature CSV | 1 | 11,170 records · mean 45.0°C |
