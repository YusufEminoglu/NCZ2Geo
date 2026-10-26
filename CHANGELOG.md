# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

## [0.13.1] - 2026-10-27
### Changed
- Project URLs (Repository, Changelog) and all README and documentation-site links now point to the GitHub repository instead of GitLab.
- README shows the Zenodo DOI badge; `CITATION.cff` and the BibTeX entry carry the DOI.

## [0.13.0] - 2026-10-26
### Added
- **ESRI Shapefile export** (`export_entities_to_shapefile`): one shapefile per geometry type
  (`_points`, `_lines`, `_polygons`), PointZ/PolyLineZ/PolygonZ when the drawing has elevations,
  clockwise exterior rings, all PlanGML/e-Plan attributes under 10-character dBase names
  (`result.field_names`), UTF-8 `.cpg` and an ESRI `.prj`.
- **DXF export** (`export_entities_to_dxf`): ASCII DXF R12 with the Netcad layers, POINT, TEXT
  (height, rotation) and 2D/3D POLYLINE entities, Turkish ANSI_1254 code page.
- **Bundled CRS definitions** for TUREF and ED50 3° TM zones, UTM 35N–38N, WGS 84 and Web
  Mercator (PROJJSON, OGC WKT1, ESRI WKT; `supported_epsg_codes()`), generated from PROJ.
- **`ncz2geo convert` writes any format**: the output extension picks GeoJSON, GeoPackage,
  Shapefile, FlatGeobuf, GeoParquet, DXF, KML or KMZ, and the CRS defaults to the EPSG code
  stored in the drawing (`--srid` overrides it).
- `write_geojson(..., srid=...)` adds the GeoJSON 2008 `crs` member for projected drawings,
  so GDAL/QGIS place the plan correctly instead of assuming WGS 84 (the CLI passes it).

### Changed
- **FlatGeobuf is now the real format.** The previous writer produced a custom container that
  GDAL rejected ("Header failed consistency verification"). The new writer emits FlatGeobuf v3:
  FlatBuffers header with typed columns and EPSG CRS, a packed Hilbert R-tree index (node size
  16, or `index_node_size=0` for none) and FlatBuffers features with Z.
- **GeoParquet is now a real Parquet file.** The previous "Parquet-like" container could not be
  opened by any Parquet reader. The new pure-Python writer produces a single-row-group Parquet
  file with a WKB `geometry` column, typed attribute columns and GeoParquet 1.1 `geo` metadata
  with full PROJJSON (previously every CRS was labelled a GeographicCRS).
- **GeoPackage rewritten to the 1.2 specification**: points, lines and polygons are stored as
  such (everything used to be written as a POLYGON), all attributes are kept, the CRS gets its
  real WKT instead of a `PROJCS[...]` placeholder, the required SRS rows and `application_id`
  are present, and a `gpkg_rtree_index` spatial index with its triggers is built.
- **KML/KMZ coordinates are reprojected to WGS 84** via the new `srid` argument (inverse
  Transverse Mercator plus the EPSG ED50→WGS 84 Helmert for Turkey; under 1 mm from PROJ).
  Projected coordinates without `srid` now raise `ValueError` instead of producing a KML that
  places the plan off the globe. Points and text are written as `<Point>` again (they were
  emitted as one-vertex LineStrings because the geometry kinds were compared in upper case).
- All binary exporters share one feature table, so they carry exactly the geometry and
  attributes of `write_geojson`. Every format was checked against GDAL 3.13 (ogrinfo/ogr2ogr,
  `validate_gpkg.py`), and GeoParquet additionally against pyarrow and DuckDB.
- PyPI metadata: a plain-language summary, search keywords that match what users look for, and a working issue tracker link (GitHub issues; the GitLab issues page returned 404).

### Fixed
- GeoJSON: a single-vertex entity (e.g. a circle, which carries only its centre) was written as
  a one-position LineString, which is invalid GeoJSON; it is now a Point.
- NCZ Engine v2 decoders no longer leak `NaN`/`inf` from corrupt or unexpected field values
  into decoded entities. A non-finite box rotation used to turn every ring corner into `NaN`
  (written as invalid JSON by the GeoJSON exporters), and smart-object sizes, circle/arc
  radii and angles, and text/symbol/block rotations could carry `NaN`/`Infinity`. Such
  scalars now fall back to `0`, smart objects use their corner-point size, and polyline
  vertices with non-finite coordinates are skipped.
- NCZ Engine v2: an `@TAB` not followed by digits (for example the text `@TABLE`) is no longer
  taken as an attribute-table marker; it used to create a bogus table and truncate the
  preceding real record.
- NCZ Engine v2: a geometry record nested in a container block is now indexed when it ends
  exactly at the container's last byte (an off-by-one bound skipped it).
- NCZ Engine v2: an unterminated `SRS:"EPSG:..."` value in a `TILED_XML` block is read only to
  the end of its block and stops at NUL padding, instead of running on through the rest of the
  file and returning padding and the next blocks' bytes as the EPSG code.
- NCZ Engine v2: open polylines no longer report rectangle `box_width`/`box_height`/rotation
  when their cyclic vertex list happens to reduce to four corners; only closed rings do.
- NCZ index cache: a cache file holding well-formed JSON of the wrong shape (non-object
  document, non-object metadata, non-object summaries or tables) is now a cache miss instead
  of an `AttributeError` or a crash later in the reader, and a failed save no longer leaves an
  orphaned `*.json.tmp` file behind.
- `ncz2geo` CLI: output redirected to a file on Windows (ANSI code page) no longer aborts
  with `UnicodeEncodeError` on characters the encoding cannot represent (layer names, the
  validation report's status symbols); they are replaced instead.
- `calculate_zoning_capacity` folds Turkish letters before keyword matching, so catalog
  function names such as `TİCARET ALANI` and `PASİF YEŞİL ALAN` are classified as commercial
  and green (they fell through to the generic branch); office layers match `OFIS` (was the
  misspelt `OFIZ`).

## [0.12.1] - 2026-10-23
### Changed
- Completed docstrings and type annotations across the public API and NCZ Engine v2 internals, with no runtime behavior changes.
- Formatted `src` and `tests` with Ruff and resolved all lint findings.
- Expanded the README with detailed installation steps, verified usage examples, a feature list, and a public API reference table.
- Added edge-case and error-path tests for classification, validation, cadastral analysis, and the exporters.
- Aligned build metadata (`setuptools` requirement for the SPDX license expression) and the coverage badge with the current codebase.

### Added
- High-resolution GEOPHILO CDN logos and GitLab repository telemetry in the generated documentation.

## [0.12.0] - 2026-08-30
### Added
- **3D Cadastral Condominium & Strata Title Slicer (`cadastral_condominium_strata_slicer.py`)**: Added `slice_condominium_strata_units` generating 3D volumetric legal units (Kat Mülkiyeti) and calculating land ownership shares (Arsa Payı).
- **GeoPackage R-Tree Spatial Index Optimizer (`geopackage_spatial_indexer.py`)**: Added `optimize_geopackage_spatial_rtree` building fast in-memory R-Tree bounding box indices.

## [0.11.0] - 2026-08-30
### Added
- **Cadastral Boundary Dispute & Overlap Sliver Resolver (`cadastral_boundary_dispute_resolver.py`)**: Added `resolve_cadastral_boundary_disputes` detecting adjacent map sheet boundary overlaps and allocating micro-slivers cleanly.
- **Compressed Streaming GeoZip Spatial Archive Bundle (`geozip_stream_archiver.py`)**: Added `create_geozip_spatial_archive` packaging multi-layer vector geometries and manifest metadata into portable containers.

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
