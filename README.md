<div align="center">

<a href="https://yusufeminoglu.github.io/NCZ2Geo/">
  <img src="https://raw.githubusercontent.com/YusufEminoglu/NCZ2Geo/main/docs/icons/logo.svg" width="140" height="140" alt="NCZ2Geo logo" />
</a>

# NCZ2Geo

[![CI](https://github.com/YusufEminoglu/NCZ2Geo/actions/workflows/ci.yml/badge.svg)](https://github.com/YusufEminoglu/NCZ2Geo/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/NCZ2Geo.svg?color=3b82f6)](https://pypi.org/project/NCZ2Geo/)
[![Python version support](https://img.shields.io/pypi/pyversions/NCZ2Geo.svg?color=10b981)](https://pypi.org/project/NCZ2Geo/)
[![Documentation](https://img.shields.io/badge/docs-GitHub%20Pages-06b6d4.svg)](https://yusufeminoglu.github.io/NCZ2Geo/)
[![License: GPL-2.0-or-later](https://img.shields.io/badge/License-GPL--2.0--or--later-blue.svg)](LICENSE)
[![Code style: Ruff](https://img.shields.io/badge/code%20style-ruff-D7FF64.svg)](https://docs.astral.sh/ruff/)
[![Test Coverage](https://img.shields.io/badge/coverage-90%25%2B-brightgreen.svg)](#-development--testing)

**Pure-Python Netcad NCZ/NCA Reader with PlanGML Identity and e-Plan Symbology Metadata.**

[📖 **Open Interactive Web Manual (GitHub Pages)**](https://yusufeminoglu.github.io/NCZ2Geo/) • [📦 **PyPI Package**](https://pypi.org/project/NCZ2Geo/) • [🐛 **Issue Tracker**](https://github.com/YusufEminoglu/NCZ2Geo/issues)

</div>

---

## 🌟 Overview

**NCZ2Geo** is a specialized Python SDK engineered specifically for Turkish urban planning workflows. It reads Netcad `NCZ` (compressed archive) and `NCA` (raw binary CAD stream) drawings, automatically resolves layer semantics against official **PlanGML / MPYY** (*Mekânsal Planlar Yapım Yönetmeliği*) schemas, and attaches official **e-Plan** symbology metadata to the emitted GeoJSON features.

Built entirely on the high-speed **NCZ Engine v2** core, **NCZ2Geo** operates 100% headless with zero dependencies outside the Python standard library.

---

## 🔬 Core Capabilities

1. **PlanGML & MPYY Standard Hierarchy Resolution:**
   - Automatically maps arbitrary Netcad layer names (e.g. `PL_GELISME_KONUT`, `PARK_ALANI`, `TICARET`) into standard function codes, upper groups, and geometry types for:
     * **UIP:** *Uygulama İmar Planı (1/1.000)*
     * **NIP:** *Nazım İmar Planı (1/5.000)*
     * **CDP:** *Çevre Düzeni Planı (1/25.000 &middot; 1/50.000 &middot; 1/100.000)*
2. **Official e-Plan Symbology Color & Hatching Injection:**
   - Injects standardized hex colors (`#RRGGBB`), opacity values, stroke widths, dash styles, and hatching patterns (`eplan_tarama`) into every GeoJSON feature.
3. **V2-Only Bounds-Checked Binary Block Scanner:**
   - Employs a clamped binary `Cursor` and two-phase `NczCatalog` indexer to prevent out-of-bounds reads and ensure memory safety on corrupt or non-standard Netcad drawings.
4. **Instant $\mathcal{O}(1)$ Fingerprinted Index Cache:**
   - Reopening an unchanged drawing serves catalog queries in **0.1 ms** with zero file I/O overhead.
5. **Selective Layer Decoding & Memory Optimization:**
   - Reads only specified layer IDs, skipping unneeded geometry byte streams to accelerate automated ingestion pipelines.

---

## 📦 Installation

```bash
pip install NCZ2Geo
```

---

## 🚀 Quickstart & Python API

### 1. Automatic Layer Classification
Classify layer names into official PlanGML function codes and e-Plan colors:

```python
from ncz2geo import classify_layer

# Classify layer name under UIP (1/1.000) standard
classification = classify_layer("PL_GELISME_KONUT", plan_type="UIP")

print("PlanGML Function:", classification.identity.fonksiyon_adi)  # Gelişme Konut Alanı
print("PlanGML Code:", classification.identity.fonksiyon_kodu)     # 1102
print("e-Plan Fill Color:", classification.style.fill)              # #ffcc00
print("e-Plan Opacity:", classification.style.fill_opacity)         # 0.70
```

### 2. Parse Netcad NCZ & Export Styled GeoJSON

```python
from ncz2geo import parse_netcad, write_geojson

# 1. Parse drawing using NCZ Engine v2
result = parse_netcad("imar_plani.ncz")
print(f"Decoded {len(result.entities)} entities across {len(result.layers)} layers.")

# 2. Export GeoJSON enriched with PlanGML and e-Plan attributes
write_geojson(result.entities, "imar_plani_styled.geojson", plan_type="UIP")
```

### 3. Selective Layer Extraction

```python
from ncz2geo import parse_netcad, write_geojson

# Extract only residential and green space layers (e.g. Layers 1 and 4)
result = parse_netcad("imar_plani.ncz", target_layers=[1, 4])
write_geojson(result.entities, "konut_ve_parklar.geojson", plan_type="UIP")
```

---

## 💻 Command Line Interface (CLI)

```bash
# 1. Inspect Netcad drawing and list PlanGML matched layers
ncz2geo inspect imar_plani.ncz --plan-type UIP

# 2. Machine-readable inspection output for CI/CD or scripts
ncz2geo inspect imar_plani.ncz --plan-type UIP --json

# 3. Convert all layers to PlanGML & e-Plan styled GeoJSON
ncz2geo convert imar_plani.ncz imar_plani.geojson --plan-type UIP

# 4. Convert specific layer codes only
ncz2geo convert imar_plani.ncz konut_alanlari.geojson --layers 1,4,7 --plan-type UIP
```

---

## 📋 Emitted GeoJSON Schema Properties

Every exported GeoJSON feature includes standard Netcad CAD attributes plus enriched PlanGML / e-Plan metadata:

```json
{
  "type": "Feature",
  "geometry": { "type": "Polygon", "coordinates": [...] },
  "properties": {
    "layer_code": 1,
    "layer_name": "PL_GELISME_KONUT",
    "netcad_color": 3,
    "plangml_tabaka": "PL_GELISME_KONUT",
    "plangml_ust_grup_id": 1,
    "plangml_ust_grup_adi": "Kentsel Yerleşme Alanları",
    "plangml_fonksiyon_kodu": 1102,
    "plangml_fonksiyon_adi": "Gelişme Konut Alanı",
    "plangml_geometri": "Polygon",
    "eplan_style_key": "uip_1102",
    "eplan_fill": "#ffcc00",
    "eplan_fill_opacity": 0.70,
    "eplan_stroke": "#333333",
    "eplan_line_color": "#ffaa00",
    "eplan_dash": "solid",
    "eplan_tarama": "none"
  }
}
```

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
git clone https://github.com/YusufEminoglu/NCZ2Geo.git
cd NCZ2Geo

# Install in editable mode with test dependencies
pip install -e ".[dev]"

# Run test suite
pytest tests/ -v --cov=ncz2geo

# Run linter and type checks
ruff check .
mypy src
```

---

## 📄 Academic Citation

If you use **NCZ2Geo** in urban planning studies, cadastral automation pipelines, or scientific research, please cite:

```bibtex
@software{eminoglu2026ncz2geo,
  author    = {Emino{\u{g}}lu, Yusuf},
  title     = {{NCZ2Geo: Pure-Python Netcad NCZ/NCA Reader with PlanGML Identity and e-Plan Symbology Metadata}},
  year      = {2026},
  publisher = {PyPI - Python Package Index},
  version   = {0.1.0},
  url       = {https://github.com/YusufEminoglu/NCZ2Geo}
}
```

---

## 📜 License

Distributed under the **GPL-2.0-or-later** license.
