# Changelog

All notable changes to this project will be documented in this file.

## [0.10.0] - 2026-08-30
### Added
- **Cadastral Right-of-Way Easement Slicer (`cadastral_right_of_way_easement.py`)**: Added `generate_easement_corridor_slices` for BOTAŞ/TEİAŞ infrastructure servitude buffers and compensation assessments.
- **GeoBuff Protocol-Buffer Binary Vector Serializer (`geobuff_encoder.py`)**: Added `export_entities_to_geobuff` writing delta-packed zigzag integers for ultra-compact mobile GIS streams.

## [0.9.0] - 2026-08-30
### Added
- **Cadastral Parcel Subdivision & Road Frontage Optimizer (`parcel_subdivision_optimizer.py`)**: Added `subdivide_cadastral_parcel` slicing parent parcel polygons into optimum zoning-compliant sub-lots along frontage axes.
- **Cloud-Native GeoParquet 1.1 Exporter (`geoparquet_writer.py`)**: Added `export_entities_to_geoparquet` writing OGC WKB vector records with GeoParquet 1.1 embedded metadata.

## [0.8.0] - 2026-08-30
### Added
- **Visvalingam-Whyatt Cadastral Boundary Simplifier (`cadastral_boundary_simplifier.py`)**: Added `simplify_cadastral_boundaries` using minimum triangle effective area preservation.
- **Cloud-Native FlatGeobuf (.fgb) Binary Exporter (`flatgeobuf_writer.py`)**: Added `export_entities_to_flatgeobuf` streaming Netcad geometries into FlatGeobuf vector binary containers.

## [0.7.0] - 2026-08-30
### Added
- **Cadastral Land Consolidation & DOP Re-allotment Optimizer (`land_consolidation.py`)**: Added `optimize_land_consolidation` with public participation deduction (DOP), soil quality indices, and shape compactness parcellation.
- **OGC GeoPackage (.gpkg) SQLite Vector Exporter (`geopackage_writer.py`)**: Added `export_entities_to_geopackage` writing standard OGC GeoPackage binary geometry blobs and metadata tables.

## [0.6.0] - 2026-08-30
### Added
- **Google Earth 3D KML & KMZ Exporter (`kml_kmz_exporter.py`)**: Added `export_to_kml_kmz` with 3D volumetric extrusion, balloon metadata, and in-memory compressed KMZ archive output.
- **Cadastral Plan Topology QA & Error Detector (`topological_validator.py`)**: Added `validate_cadastral_topology` identifying self-intersections, unclosed polygon rings, duplicate vertices, and zero-area anomalies.

## [0.5.0] - 2026-08-30
### Added
- **Zoning Capacity & Demographic EMSAL Calculator (`zoning_density.py`)**: Added `calculate_zoning_capacity` evaluating net building footprints (TAKS), total construction floor areas (KAKS/EMSAL), population capacities, and parking space quotas.
- **Visvalingam-Whyatt & 3D Douglas-Peucker Line Simplifier (`simplifier.py`)**: Added `visvalingam_whyatt_simplify`, `douglas_peucker_3d`, and `simplify_entities` for polygon and polyline vertex reduction.

## 0.4.0 - 2026-08-30

- **Plan-to-Plan Spatial Difference Engine (`plan_diff.py`)**: Added `compare_plans` to detect zoning amendments, reclassified parcels, and net area changes.
- **Cadastral Attribute KVKK / GDPR Anonymizer (`anonymizer.py`)**: Added `anonymize_ncz_attributes` to scrub sensitive cadastral PII while preserving data model linkages.
- **OGC PlanGML GML 3.2.1 & CityGML Exporter (`gml_exporter.py`)**: Added `export_plangml_gml` and `export_citygml_lods`.
- **7-Parameter 3D Helmert & 2D Affine Transformation Engine (`transformer.py`)**: Added `helmert_7parameter_transform` (ED50 <-> ITRF96) and `transform_entities`.

## 0.2.0 - 2026-08-30

- **PlanGML & e-Plan Compliance Validator (`validator.py`)**: Added automated spatial and semantic validation engine (`validate_plan`) with quality scoring, land-use breakdown, and missing mandatory layer detection.
- **OGC SLD, QGIS QML & Mapbox GL Style Exporter (`styler.py`)**: Added full GIS stylesheet generation (`export_sld`, `export_qml`, `export_mapbox_style`, `export_plan_styles`) directly from official ministry palettes.
- **CLI Enhancements**: Added `ncz2geo validate` (with `--json` and `--markdown` reports) and `ncz2geo style` commands.

## 0.1.0 - 2026-08-25

- Added V2-only Netcad NCZ/NCA reader API.
- Added MPYY PlanGML layer identity matching.
- Added e-Plan symbology metadata matching for UIP/NIP/CDP.
- Added PlanGML-aware GeoJSON export.
- Added `ncz2geo inspect` and `ncz2geo convert` CLI commands.
