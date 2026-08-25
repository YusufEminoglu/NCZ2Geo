"""Netcad NCZ/NCA reader with PlanGML and e-Plan style metadata."""

from .geojson import entities_to_feature_collection, write_geojson
from .plangml import (
    LayerClassification,
    classify_entity,
    classify_layer,
    classify_layers,
    detect_plan_type,
    normalize_layer_name,
)
from .reader import LayerSummary, NetcadReader, inspect_source, parse_netcad

__version__ = "0.1.0"

__all__ = [
    "LayerClassification",
    "LayerSummary",
    "NetcadReader",
    "__version__",
    "classify_entity",
    "classify_layer",
    "classify_layers",
    "detect_plan_type",
    "entities_to_feature_collection",
    "inspect_source",
    "normalize_layer_name",
    "parse_netcad",
    "write_geojson",
]
