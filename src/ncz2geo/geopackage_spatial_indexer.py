# -*- coding: utf-8 -*-
"""GeoPackage R-Tree Spatial Index & Bounding Box Query Optimizer for NCZ2Geo."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Sequence

from ncz2geo.ncz_engine.model import NetcadEntity


@dataclass
class RTreeBoundingBoxFilter:
    min_x: float
    max_x: float
    min_y: float
    max_y: float


@dataclass
class SpatialIndexOptimizationReport:
    total_entities_indexed: int
    rtree_depth_levels: int
    spatial_extent: tuple[float, float, float, float]
    index_storage_estimate_bytes: int
    matching_entities_in_query: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "indexed_count": self.total_entities_indexed,
            "rtree_depth": self.rtree_depth_levels,
            "extent": [round(v, 2) for v in self.spatial_extent],
            "index_bytes": self.index_storage_estimate_bytes,
            "query_matches": self.matching_entities_in_query,
        }


def optimize_geopackage_spatial_rtree(
    entities: Sequence[NetcadEntity],
    test_query_bbox: RTreeBoundingBoxFilter | None = None,
    node_capacity_m: int = 32,
) -> SpatialIndexOptimizationReport:
    """Build and optimize in-memory R-Tree spatial index bounding boxes for OGC GeoPackage tables."""
    n = len(entities)
    if n == 0:
        return SpatialIndexOptimizationReport(0, 0, (0.0, 0.0, 0.0, 0.0), 0, 0)

    # Compute individual envelopes
    all_min_x: list[float] = []
    all_max_x: list[float] = []
    all_min_y: list[float] = []
    all_max_y: list[float] = []

    entity_boxes: list[tuple[float, float, float, float]] = []

    for ent in entities:
        if ent.coordinates:
            xs = [c.x for c in ent.coordinates]
            ys = [c.y for c in ent.coordinates]
            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)
        else:
            min_x, max_x, min_y, max_y = 0.0, 0.0, 0.0, 0.0

        all_min_x.append(min_x)
        all_max_x.append(max_x)
        all_min_y.append(min_y)
        all_max_y.append(max_y)
        entity_boxes.append((min_x, max_x, min_y, max_y))

    global_extent = (min(all_min_x), min(all_min_y), max(all_max_x), max(all_max_y))
    tree_depth = max(1, math.ceil(math.log(max(2, n), node_capacity_m)))
    bytes_est = n * 48  # ~48 bytes per SQLite R-Tree row (id + 4 floats + overhead)

    # Test spatial query
    matches = 0
    if test_query_bbox:
        qb = test_query_bbox
        for bx_min, bx_max, by_min, by_max in entity_boxes:
            # Overlap check
            if not (bx_max < qb.min_x or bx_min > qb.max_x or by_max < qb.min_y or by_min > qb.max_y):
                matches += 1
    else:
        matches = n

    return SpatialIndexOptimizationReport(
        total_entities_indexed=n,
        rtree_depth_levels=tree_depth,
        spatial_extent=global_extent,
        index_storage_estimate_bytes=bytes_est,
        matching_entities_in_query=matches,
    )
