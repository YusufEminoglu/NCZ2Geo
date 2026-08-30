# -*- coding: utf-8 -*-
"""NCZ2Geo — Pure-Python Netcad NCZ Cadastral Parser, PlanGML, 3D KML/KMZ & Topology Suite."""

from __future__ import annotations

from .anonymizer import (
    AnonymizationReport,
    anonymize_ncz_attributes,
    mask_pii_value,
)
from .geojson import entities_to_feature_collection, write_geojson
from .gml_exporter import (
    export_citygml_lods,
    export_plangml_gml,
)
from .kml_kmz_exporter import (
    KMLExportResult,
    KMLStyleConfig,
    export_to_kml_kmz,
)
from .ncz_engine import (
    NetcadAttributeRow,
    NetcadAttributeTable,
    NetcadCoordinate,
    NetcadEntity,
    NetcadParseResult,
)
from .plan_diff import (
    PlanDiffResult,
    ZoningChangeItem,
    compare_plans,
)
from .plangml import (
    LayerClassification,
    classify_entity,
    classify_layer,
    classify_layers,
    detect_plan_type,
    normalize_layer_name,
)
from .reader import LayerSummary, NetcadReader, inspect_source, parse_netcad
from .simplifier import (
    douglas_peucker_3d,
    simplify_entities,
    visvalingam_whyatt_simplify,
)
from .styler import (
    export_mapbox_style,
    export_plan_styles,
    export_qml,
    export_sld,
)
from .topological_validator import (
    TopologyIssue,
    TopologyValidationReport,
    validate_cadastral_topology,
)
from .geopackage_writer import (
    GeoPackageExportResult,
    export_entities_to_geopackage,
)
from .flatgeobuf_writer import (
    FlatGeobufExportResult,
    export_entities_to_flatgeobuf,
)
from .geoparquet_writer import (
    GeoParquetExportResult,
    GeoParquetMetadata,
    export_entities_to_geoparquet,
)
from .cadastral_boundary_simplifier import (
    BoundarySimplificationResult,
    simplify_cadastral_boundaries,
)
from .parcel_subdivision_optimizer import (
    ParcelSubdivisionResult,
    SubdividedLot,
    subdivide_cadastral_parcel,
)
from .land_consolidation import (
    ConsolidatedParcel,
    LandConsolidationReport,
    OwnershipShare,
    optimize_land_consolidation,
)
from .transformer import (
    DATUM_PARAMS,
    Helmert7Params,
    affine_transform_2d,
    helmert_7parameter_transform,
    transform_entities,
)
from .validator import (
    PlanValidationIssue,
    PlanValidationReport,
    validate_plan,
)
from .zoning_density import (
    ParcelCapacityItem,
    ZoningCapacityReport,
    calculate_zoning_capacity,
)

__version__ = "0.9.0"
__author__ = "Yusuf Eminoğlu"

__all__ = [
    "__version__",
    "NetcadReader",
    "inspect_source",
    "parse_netcad",
    "LayerSummary",
    "LayerClassification",
    "classify_entity",
    "classify_layer",
    "classify_layers",
    "detect_plan_type",
    "normalize_layer_name",
    "entities_to_feature_collection",
    "write_geojson",
    "PlanValidationIssue",
    "PlanValidationReport",
    "validate_plan",
    "PlanDiffResult",
    "ZoningChangeItem",
    "compare_plans",
    "AnonymizationReport",
    "anonymize_ncz_attributes",
    "mask_pii_value",
    "export_mapbox_style",
    "export_plan_styles",
    "export_qml",
    "export_sld",
    "DATUM_PARAMS",
    "Helmert7Params",
    "helmert_7parameter_transform",
    "affine_transform_2d",
    "transform_entities",
    "export_plangml_gml",
    "export_citygml_lods",
    "NetcadCoordinate",
    "NetcadEntity",
    "NetcadAttributeRow",
    "NetcadAttributeTable",
    "NetcadParseResult",
    # Zoning Density & Demographic Capacity
    "calculate_zoning_capacity",
    "ZoningCapacityReport",
    "ParcelCapacityItem",
    # Simplifier
    "visvalingam_whyatt_simplify",
    "douglas_peucker_3d",
    "simplify_entities",
    # KML & KMZ 3D Exporter
    "export_to_kml_kmz",
    "KMLExportResult",
    "KMLStyleConfig",
    # Cadastral Topological QA
    "validate_cadastral_topology",
    "TopologyValidationReport",
    "TopologyIssue",
    # Land Consolidation & DOP Re-allotment
    "optimize_land_consolidation",
    "LandConsolidationReport",
    "ConsolidatedParcel",
    "OwnershipShare",
    # OGC GeoPackage Exporter
    "export_entities_to_geopackage",
    "GeoPackageExportResult",
    # Cadastral Boundary Simplification
    "simplify_cadastral_boundaries",
    "BoundarySimplificationResult",
    # FlatGeobuf Exporter
    "export_entities_to_flatgeobuf",
    "FlatGeobufExportResult",
    # Parcel Subdivision & Frontage Optimizer
    "subdivide_cadastral_parcel",
    "ParcelSubdivisionResult",
    "SubdividedLot",
    # GeoParquet Exporter
    "export_entities_to_geoparquet",
    "GeoParquetExportResult",
    "GeoParquetMetadata",
]
