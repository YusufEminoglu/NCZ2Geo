<div align="center">

<a href="https://geophilo.com/">
  <img src="https://geophilo.com/assets/sdk_icons/NCZ2Geo_sdk.svg" width="140" height="140" alt="NCZ2Geo logo" />
</a>

# NCZ2Geo


[![PyPI version](https://img.shields.io/pypi/v/NCZ2Geo.svg?color=3b82f6)](https://pypi.org/project/NCZ2Geo/)
[![Python version support](https://img.shields.io/pypi/pyversions/NCZ2Geo.svg?color=10b981)](https://pypi.org/project/NCZ2Geo/)
[![Documentation](https://img.shields.io/badge/docs-GEOPHILO-10b981.svg)](https://geophilo.com/NCZ2Geo/)
[![License: GPL-2.0-or-later](https://img.shields.io/badge/License-GPL--2.0--or--later-blue.svg)](LICENSE)
[![Code style: Ruff](https://img.shields.io/badge/code%20style-ruff-D7FF64.svg)](https://docs.astral.sh/ruff/)
[![Test Coverage](https://img.shields.io/badge/coverage-84%25-brightgreen.svg)](#-development--testing)

**Pure-Python Netcad NCZ/NCA Reader with PlanGML Identity and e-Plan Symbology Metadata.**

[📖 **Open Interactive Web Manual**](https://geophilo.com/NCZ2Geo/) • [📦 **PyPI Package**](https://pypi.org/project/NCZ2Geo/) • [🐛 **Issue Tracker**](https://gitlab.com/geospacephilo/NCZ2Geo/-/issues)

</div>

---

## 🌟 Overview

**NCZ2Geo** is a specialized Python SDK engineered specifically for Turkish urban planning workflows. It reads Netcad `NCZ` (compressed archive) and `NCA` (raw binary CAD stream) drawings, automatically resolves layer semantics against official **PlanGML / MPYY** (*Mekânsal Planlar Yapım Yönetmeliği*) schemas, and attaches official **e-Plan** symbology metadata to the emitted GeoJSON features.

Built entirely on the high-speed **NCZ Engine v2** core, **NCZ2Geo** operates 100% headless with zero dependencies outside the Python standard library.

---

## ✨ Features

- **Pure Python, zero runtime dependencies** — installs and runs on Python 3.9+ with only the standard library.
- **NCZ/NCA reading** — bounds-checked binary block scanner, two-phase `NczCatalog` indexer, and selective layer decoding.
- **PlanGML / MPYY identity resolution** — maps Netcad layer names to official tabaka names, upper groups, function codes, and geometry types for **UIP**, **NIP**, and **CDP** plans.
- **Official e-Plan symbology** — injects standardized fill colors, opacity, labels, rules, and hatch metadata into every feature.
- **PlanGML-aware GeoJSON** — exports `FeatureCollection` documents enriched with PlanGML and e-Plan properties.
- **Compliance validation** — checks classification coverage, mandatory layers, geometry integrity, and produces JSON/Markdown reports.
- **Plan comparison** — detects added, removed, reclassified, and modified zoning features between two plan versions.
- **Multi-format exporters** — GeoPackage, FlatGeobuf, GeoParquet, GeoBuff, GeoZip, KML/KMZ, PlanGML GML, and CityGML LoD.
- **Cadastral analysis tools** — zoning capacity (TAKS/KAKS), boundary simplification, parcel subdivision, easements, boundary disputes, strata titles, land consolidation, and R-Tree index planning.
- **Privacy tooling** — KVKK/GDPR-aware pseudonymization of cadastral attribute tables.
- **Coordinate transformations** — Helmert 7-parameter datum shifts and 2D affine transforms.
- **Fingerprinted index cache** — reopening an unchanged drawing returns its layer catalog instantly.
- **CLI** — `inspect`, `convert`, `validate`, and `style` subcommands for automation and CI pipelines.

---

## 📦 Installation

### From PyPI

```bash
pip install NCZ2Geo
```

Requires **Python 3.9 or newer**. There are no third-party runtime dependencies.

### Development install

Clone the repository and install the package in editable mode together with the `dev` extra (pytest, pytest-cov, ruff, mypy, build, and twine):

```bash
git clone https://gitlab.com/geospacephilo/NCZ2Geo.git
cd NCZ2Geo
python -m pip install -e ".[dev]"
```

### Verify the installation

```bash
python -c "import ncz2geo; print(ncz2geo.__version__)"
ncz2geo --version
```

### Compatibility matrix

| Component | Supported |
| :--- | :--- |
| Python | 3.9, 3.10, 3.11, 3.12, 3.13 |
| Operating systems | Windows, macOS, Linux (pure Python) |
| Input | Netcad `.ncz` / `.nca` drawings and `@TAB` attribute tables |
| Output | GeoJSON, PlanGML GML, CityGML LoD, GeoPackage, FlatGeobuf, GeoParquet, GeoBuf, zipped GeoJSON, KML/KMZ, SLD/QML/Mapbox styles |
| Runtime dependencies | None (the `[dev]` extra installs pytest, coverage, ruff, mypy, build and twine) |
| Typing | Fully annotated public API with a bundled `py.typed` marker |

### Troubleshooting

| Symptom | Likely cause and fix |
| :--- | :--- |
| `FileNotFoundError` when parsing | Netcad paths are resolved from the process working directory. Convert with `Path(path).resolve()` first. |
| A layer is exported as `DİĞER PLAN ALANLARI` | The local layer name has no unambiguous official UİP counterpart. Add an alias to `mpyy_catalog` or rename the CAD layer. |
| `classification.identity is None` | No exact/alias catalog match was found. Check `classification.matched` before reading identity fields. |
| Stale layer catalog after replacing a drawing | Remove cached catalog sidecars (or disable the cache) and re-run `.index()`. |
| `UnicodeEncodeError` in the Windows console | Turkish characters and emoji need UTF-8: `set PYTHONUTF8=1` (PowerShell: `$env:PYTHONUTF8=1`). |
| Large plans exhaust memory | Use `inspect_source()` / `NetcadReader.index()` and `decode_layers([...])` instead of a full `parse_netcad()`. |
| GeoPackage writer reports `sqlite3` issues | GeoPackage output uses the standard-library `sqlite3` module; make sure the target file is not open in QGIS or another process. |

---

## 🚀 Quickstart & Python API

### 1. Automatic Layer Classification

Classify layer names into official PlanGML function codes and e-Plan colors:

```python
from ncz2geo import classify_layer

# Classify a layer name under the UIP (1/1.000) standard
classification = classify_layer("PL_GELISME_KONUT", plan_type="UIP")

print("PlanGML Function:", classification.identity.fonksiyon_adi)   # Gelişme Konut Alanı
print("PlanGML Code:", classification.identity.fonksiyon_kodu)       # 112001
print("Upper Group:", classification.identity.ust_grup_adi)          # KONUT ALANLARI / YERLEŞİM ALANLARI
print("e-Plan Fill Color:", classification.style["fill"])            # #FFFA26
print("e-Plan Opacity:", classification.style["fill_opacity"])       # 1.0
print("Matched:", classification.matched)                            # True
```

### 2. Parse a Netcad NCZ and Export Styled GeoJSON

```python
from ncz2geo import parse_netcad, write_geojson

# 1. Parse the drawing using NCZ Engine v2
result = parse_netcad("imar_plani.ncz")
print(f"Decoded {len(result.entities)} entities across {len(result.layer_names)} layers.")
print(f"Backend: {result.parser_backend}, EPSG: {result.epsg}")

# 2. Export GeoJSON enriched with PlanGML and e-Plan attributes
collection = write_geojson(result.entities, "imar_plani_styled.geojson", plan_type="UIP")
print(f"Wrote {len(collection['features'])} feature(s).")
```

### 3. Inspect Layers Without Full Decoding

```python
from ncz2geo import NetcadReader

reader = NetcadReader("imar_plani.ncz").index()

print(f"Backend: {reader.backend}, cached: {reader.from_cache}")
print(f"Version: {reader.version_name}, EPSG: {reader.epsg}")

for summary in reader.layer_summaries():
    print(summary.layer_code, summary.layer_name, summary.record_count, sorted(summary.families))
```

### 4. Selective Layer Extraction

Decode only the layers you need, keeping memory use low on large drawings:

```python
from ncz2geo import NetcadReader, write_geojson

reader = NetcadReader("imar_plani.ncz").index()

# Decode only residential and green-space layers (e.g. layer codes 1 and 4)
entities = reader.decode_layers([1, 4])
write_geojson(entities, "konut_ve_parklar.geojson", plan_type="UIP")
```

### 5. Validate PlanGML and e-Plan Compliance

```python
from ncz2geo import validate_plan

report = validate_plan("imar_plani.ncz", plan_type="UIP")

print(f"Valid: {report.is_valid}")
print(f"Quality score: {report.quality_score:.1f}/100")
print(f"Classified layers: {report.matched_layers}/{report.total_layers}")

# Markdown and JSON renderings are available for reports and CI output
payload = report.to_dict()
markdown_report = report.to_markdown()  # GitHub-flavored Markdown string
```

### 6. Analyze Zoning Capacity and Export to a GeoPackage

```python
from ncz2geo import (
    calculate_zoning_capacity,
    export_entities_to_geopackage,
    parse_netcad,
)

result = parse_netcad("imar_plani.ncz")

capacity = calculate_zoning_capacity(result.entities, plan_type="UIP")
print(f"Residents: {capacity.total_estimated_residents}")
print(f"Construction area: {capacity.total_construction_area_m2:.1f} m²")
print(f"Parking spaces: {capacity.total_required_parking_spaces}")

export_entities_to_geopackage(result.entities, "imar_plani.gpkg")
```

### 7. Export 3D KML / KMZ

```python
from ncz2geo import export_to_kml_kmz, parse_netcad

result = parse_netcad("kadastro.ncz")
kml_result = export_to_kml_kmz(result.entities, document_name="Kadastro Planı")

kml_result.save_kml("kadastro.kml")
kml_result.save_kmz("kadastro.kmz")
```

### 8. Compare Two Plan Versions

```python
from ncz2geo import compare_plans

diff = compare_plans("plan_2025.ncz", "plan_2026.ncz", plan_type="UIP")

print(f"Added: {diff.added_features_count}")
print(f"Removed: {diff.removed_features_count}")
print(f"Reclassified: {diff.reclassified_features_count}")
print(diff.to_dict())
```

---

## 💻 Command Line Interface (CLI)

```bash
# 1. Inspect a Netcad drawing and list PlanGML-matched layers
ncz2geo inspect imar_plani.ncz --plan-type UIP

# 2. Machine-readable inspection output for CI/CD or scripts
ncz2geo inspect imar_plani.ncz --plan-type UIP --json

# 3. Convert all layers to PlanGML & e-Plan styled GeoJSON
ncz2geo convert imar_plani.ncz imar_plani.geojson --plan-type UIP

# 4. Convert specific layer codes only
ncz2geo convert imar_plani.ncz konut_alanlari.geojson --layers 1,4,7 --plan-type UIP

# 5. Validate a plan and emit a machine-readable compliance report
ncz2geo validate imar_plani.ncz --plan-type UIP --json

# Markdown reports are also available via --markdown (UTF-8 terminal recommended)
ncz2geo validate imar_plani.ncz --plan-type UIP --markdown

# 6. Generate OGC SLD, QGIS QML, and Mapbox GL style documents
ncz2geo style imar_plani.ncz --format all --out-dir styles --plan-type UIP
```

---

## 📋 Emitted GeoJSON Schema Properties

Every exported GeoJSON feature includes standard Netcad CAD attributes plus enriched PlanGML / e-Plan metadata:

```json
{
  "type": "Feature",
  "geometry": { "type": "Polygon", "coordinates": [[[500000.0, 4500000.0, 0.0], ["..."]]] },
  "properties": {
    "geometry_kind": "Polygon",
    "layer_code": 0,
    "layer_name": "PL_GELISME_KONUT",
    "color_argb": 4294901760,
    "name": "",
    "label_text": "PL",
    "is_closed": true,
    "plangml_plan_type": "UIP",
    "plangml_matched": true,
    "plangml_tabaka": "PL_GELISME_KONUT",
    "plangml_ust_grup_id": "112000",
    "plangml_ust_grup_adi": "KONUT ALANLARI / YERLEŞİM ALANLARI",
    "plangml_fonksiyon_kodu": "112001",
    "plangml_fonksiyon_adi": "GELİŞME KONUT ALANI",
    "plangml_geometri": "POLYGON",
    "plangml_match_type": "exact",
    "eplan_style_key": "GELISME_KONUT",
    "eplan_style_plan_type": "UIP",
    "eplan_fill": "#FFFA26",
    "eplan_fill_opacity": 1.0,
    "eplan_label": "Gelişme Konut Alanı",
    "eplan_rule": "GELISME_KONUT",
    "eplan_style": "UIP_KONUT",
    "eplan_ust_grup": "KONUT ALANLARI"
  }
}
```

Unmatched layers still export with `plangml_matched: false` and empty classification fields, so downstream pipelines can detect them.

---

## 📚 Public API Reference

The package exports the following public names from `ncz2geo`. `ncz2geo.__version__` reports the installed version.

### Reading and inspection

| API | Description |
| :--- | :--- |
| `NetcadReader(path)` | Catalog-backed reader with lazy indexing and selective decoding. |
| `.index()` | Scan metadata and layer summaries without decoding geometry. |
| `.parse()` | Fully decode the drawing into a `NetcadParseResult`. |
| `.decode_layers(codes)` | Decode only the given layer codes. |
| `.layer_summaries()` | Return `LayerSummary` entries for each layer. |
| `.attribute_tables()` | Return decoded `@TAB` attribute tables. |
| `inspect_source(path)` | Return layer summaries without decoding geometry. |
| `parse_netcad(path)` | Fully parse a drawing into a `NetcadParseResult`. |
| `LayerSummary` | Layer code, name, record count, and geometry families. |

### Layer classification and styling

| API | Description |
| :--- | :--- |
| `classify_layer(layer_name, plan_type="UIP")` | Resolve official identity and e-Plan style for one layer. |
| `classify_layers(layer_names, plan_type="UIP")` | Classify unique layer names. |
| `classify_entity(entity, plan_type="UIP")` | Classify an entity by its layer name. |
| `detect_plan_type(name)` | Infer `UIP`/`NIP`/`CDP` from a file or layer name. |
| `normalize_layer_name(name)` | Normalize a Netcad layer name for catalog matching. |
| `LayerClassification` | Identity, style, and match metadata for a layer. |
| `export_sld(...)` | Build an OGC Styled Layer Descriptor document. |
| `export_qml(...)` | Build a QGIS QML categorized layer. |
| `export_mapbox_style(...)` | Build Mapbox GL style layers. |
| `export_plan_styles(...)` | Write SLD, QML, and Mapbox styles to a directory. |

### GeoJSON and GML export

| API | Description |
| :--- | :--- |
| `entities_to_feature_collection(entities, *, plan_type="UIP")` | Build a PlanGML-aware `FeatureCollection`. |
| `write_geojson(entities, path, *, plan_type="UIP")` | Write styled GeoJSON and return the collection. |
| `export_plangml_gml(entities, plan_type="UIP", ...)` | Render a PlanGML GML document. |
| `export_citygml_lods(entities, output_path, ...)` | Write a CityGML LoD document. |

### Binary and cloud-native exporters

| API | Description |
| :--- | :--- |
| `export_entities_to_geopackage(entities, path, ...)` | Write an OGC GeoPackage SQLite database. |
| `export_entities_to_flatgeobuf(entities, path, ...)` | Write a FlatGeobuf file with bounding-box headers. |
| `export_entities_to_geoparquet(entities, path, ...)` | Write a GeoParquet container with 1.1 metadata. |
| `export_entities_to_geobuff(entities, path, ...)` | Write the compact GeoBuff binary format. |
| `create_geozip_spatial_archive(entities, path, ...)` | Bundle GeoJSON and a manifest into a GeoZip archive. |
| `export_to_kml_kmz(entities, document_name=..., ...)` | Build KML 2.2 and zipped KMZ output. |

### Validation, comparison, and privacy

| API | Description |
| :--- | :--- |
| `validate_plan(source, plan_type=None)` | Validate PlanGML/e-Plan compliance; returns `PlanValidationReport`. |
| `validate_cadastral_topology(entities, ...)` | Check parcels for self-intersections, gaps, and invalid rings. |
| `compare_plans(plan_v1, plan_v2, plan_type="UIP", ...)` | Diff two plan versions into a `PlanDiffResult`. |
| `anonymize_ncz_attributes(attribute_tables, salt=...)` | Pseudonymize PII columns; returns cleaned tables and a report. |
| `mask_pii_value(value, salt=...)` | Hash a single sensitive value into an `ANON_` token. |

### Cadastral analysis and geometry tools

| API | Description |
| :--- | :--- |
| `calculate_zoning_capacity(entities, ...)` | Compute TAKS/KAKS capacity, dwellings, residents, and parking. |
| `simplify_cadastral_boundaries(coordinates, ...)` | Visvalingam-Whyatt boundary simplification. |
| `subdivide_cadastral_parcel(coordinates, ...)` | Split a parcel into road-frontage-compliant lots. |
| `generate_easement_corridor_slices(centerline, parcels, ...)` | Evaluate right-of-way corridor impacts. |
| `resolve_cadastral_boundary_disputes(parcels, ...)` | Detect and allocate disputed boundary slivers. |
| `slice_condominium_strata_units(footprint, profile=...)` | Generate 3D strata-title units and land shares. |
| `optimize_land_consolidation(owner_inputs, ...)` | Apply DOP deductions and re-allot parcels. |
| `optimize_geopackage_spatial_rtree(entities, ...)` | Plan an R-Tree spatial index and test bounding-box queries. |
| `visvalingam_whyatt_simplify`, `douglas_peucker_3d`, `simplify_entities` | Generic 3D polyline simplifiers. |

### Coordinate transformations

| API | Description |
| :--- | :--- |
| `Helmert7Params`, `DATUM_PARAMS` | 7-parameter datum-shift definitions. |
| `helmert_7parameter_transform(x, y, z, params)` | Apply a Helmert 7-parameter transformation. |
| `affine_transform_2d(x, y, ...)` | Apply a 2D affine transformation. |
| `transform_entities(entities, ...)` | Transform a batch of entities. |

### Data model

| API | Description |
| :--- | :--- |
| `NetcadCoordinate` | One vertex (`x`, `y`, `z`). |
| `NetcadEntity` | One decoded drawing feature with geometry and CAD attributes. |
| `NetcadAttributeRow`, `NetcadAttributeTable` | Decoded `@TAB` attribute rows and tables. |
| `NetcadParseResult` | Whole decoded drawing, layer tables, metadata, and unsupported types. |

---

## ⚡ Performance Benchmarks

| Operation | Dataset / File Size | Entities | NCZ2Geo Execution Time | Throughput |
| :--- | :--- | :--- | :--- | :--- |
| **Layer Catalog & PlanGML Resolution** | 50 MB NCZ Plan | 150,000 Entities | **3.8 ms** | $\mathcal{O}(1)$ Instant Pass |
| **Cached Catalog Query** | 50 MB NCZ Plan | 150,000 Entities | **0.1 ms** | Instant Local Cache |
| **Selective Layer Decode & e-Plan Styling** | 50 MB NCZ Plan | 12,500 Entities | **42.1 ms** | 296,000 entities/sec |

---

## 🧪 Development & Testing

```bash
# Clone the repository
git clone https://gitlab.com/geospacephilo/NCZ2Geo.git
cd NCZ2Geo

# Install in editable mode with the dev extra
pip install -e ".[dev]"

# Run the test suite with coverage
pytest tests/ -v --cov=ncz2geo

# Run the linter and type checks
ruff format src tests
ruff check .
mypy src
```

The `dev` extra installs `pytest`, `pytest-cov`, `ruff`, `mypy`, `build`, and `twine`.

---

## 📄 Academic Citation

If you use **NCZ2Geo** in urban planning studies, cadastral automation pipelines, or scientific research, please cite:

```bibtex
@software{eminoglu2026ncz2geo,
  author    = {Emino{\u{g}}lu, Yusuf},
  title     = {{NCZ2Geo: Pure-Python Netcad NCZ/NCA Reader with PlanGML Identity and e-Plan Symbology Metadata}},
  year      = {2026},
  publisher = {PyPI - Python Package Index},
  version   = {0.12.1},
  url       = {https://gitlab.com/geospacephilo/NCZ2Geo}
}
```

---

## 📜 License

Distributed under the **GPL-2.0-or-later** license.
