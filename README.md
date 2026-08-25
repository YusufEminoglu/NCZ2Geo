# netcad2plangml

`netcad2plangml` is a focused Python SDK for Netcad planning drawings.
It reads Netcad `NCZ`/`NCA` files with the NCZ Engine v2 reader, resolves
PlanGML/MPYY layer identity, and attaches e-Plan symbology metadata to GeoJSON
features.

This package is intentionally narrower than `cad2geo`: it only targets Netcad
files and planning symbology workflows.

## Install

```bash
pip install netcad2plangml
```

## Python API

```python
from netcad2plangml import classify_layer, parse_netcad, write_geojson

result = parse_netcad("imar_plani.ncz")
classification = classify_layer("PL_GELISME_KONUT", plan_type="UIP")

print(classification.identity)
print(classification.style)

write_geojson(result.entities, "imar_plani.geojson", plan_type="UIP")
```

GeoJSON properties include the original Netcad fields plus PlanGML/e-Plan
metadata such as:

- `plangml_tabaka`
- `plangml_ust_grup_id`
- `plangml_ust_grup_adi`
- `plangml_fonksiyon_kodu`
- `plangml_fonksiyon_adi`
- `plangml_geometri`
- `eplan_style_key`
- `eplan_fill`
- `eplan_fill_opacity`
- `eplan_stroke`
- `eplan_line_color`
- `eplan_dash`
- `eplan_tarama`

## CLI

Inspect a Netcad file and show PlanGML matches:

```bash
netcad2plangml inspect imar_plani.ncz --plan-type UIP
```

Machine-readable inspection:

```bash
netcad2plangml inspect imar_plani.ncz --plan-type UIP --json
```

Convert every supported geometry to styled GeoJSON:

```bash
netcad2plangml convert imar_plani.ncz imar_plani.geojson --plan-type UIP
```

Convert selected Netcad layer codes:

```bash
netcad2plangml convert imar_plani.ncz konut.geojson --layers 1,4 --plan-type UIP
```

## Scope

The SDK assigns portable PlanGML identity and e-Plan style metadata. It does not
create QGIS renderer objects or validate a full PlanGML XML package. Renderer
implementations can consume the emitted properties.

The NCZ reader path is V2-only. V1/legacy third-party parser code is not bundled.

## Development

```bash
python -m pip install -e ".[dev]"
python -m ruff check .
python -m pytest
python -m build
```
