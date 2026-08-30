# -*- coding: utf-8 -*-
"""Visvalingam-Whyatt Area-Preserving Cadastral Boundary Simplifier for NCZ2Geo."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Sequence
from ncz2geo.ncz_engine.model import NetcadCoordinate, NetcadEntity


@dataclass
class BoundarySimplificationResult:
    original_vertex_count: int
    simplified_vertex_count: int
    compression_ratio_pct: float
    total_area_change_pct: float
    simplified_coordinates: list[tuple[float, float]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "original_vertices": self.original_vertex_count,
            "simplified_vertices": self.simplified_vertex_count,
            "compression_pct": round(self.compression_ratio_pct, 1),
            "area_change_pct": round(self.total_area_change_pct, 4),
        }


def _triangle_area(p1: tuple[float, float], p2: tuple[float, float], p3: tuple[float, float]) -> float:
    return abs(p1[0] * (p2[1] - p3[1]) + p2[0] * (p3[1] - p1[1]) + p3[0] * (p1[1] - p2[1])) * 0.5


def _polygon_area(pts: Sequence[tuple[float, float]]) -> float:
    if len(pts) < 3:
        return 0.0
    area = 0.0
    for i in range(len(pts)):
        p1 = pts[i]
        p2 = pts[(i + 1) % len(pts)]
        area += p1[0] * p2[1] - p2[0] * p1[1]
    return abs(area) * 0.5


def simplify_cadastral_boundaries(
    coordinates: Sequence[NetcadCoordinate | tuple[float, float]],
    min_effective_area_threshold_m2: float = 2.0,
    min_vertices_to_retain: int = 4,
) -> BoundarySimplificationResult:
    """Simplify parcel boundary polylines using Visvalingam-Whyatt minimum effective area metric."""
    pts: list[tuple[float, float]] = []
    for pt in coordinates:
        if isinstance(pt, NetcadCoordinate):
            pts.append((pt.x, pt.y))
        else:
            pts.append((float(pt[0]), float(pt[1])))

    if len(pts) <= min_vertices_to_retain:
        orig_area = _polygon_area(pts)
        return BoundarySimplificationResult(
            original_vertex_count=len(pts),
            simplified_vertex_count=len(pts),
            compression_ratio_pct=0.0,
            total_area_change_pct=0.0,
            simplified_coordinates=pts,
        )

    is_closed = (math.hypot(pts[0][0] - pts[-1][0], pts[0][1] - pts[-1][1]) < 1e-4)
    orig_area = _polygon_area(pts)

    working = list(pts)
    if is_closed and len(working) > 1:
        working.pop()  # Work with unclosed ring

    while len(working) > min_vertices_to_retain:
        min_area = float("inf")
        min_idx = -1

        n = len(working)
        for i in range(n):
            prev_pt = working[(i - 1) % n]
            curr_pt = working[i]
            next_pt = working[(i + 1) % n]
            area = _triangle_area(prev_pt, curr_pt, next_pt)
            if area < min_area:
                min_area = area
                min_idx = i

        if min_area < min_effective_area_threshold_m2:
            working.pop(min_idx)
        else:
            break

    if is_closed:
        working.append(working[0])

    simplified_area = _polygon_area(working)
    area_change = (abs(simplified_area - orig_area) / max(1e-4, orig_area)) * 100.0 if orig_area > 0 else 0.0
    compression = ((len(pts) - len(working)) / max(1, len(pts))) * 100.0

    return BoundarySimplificationResult(
        original_vertex_count=len(pts),
        simplified_vertex_count=len(working),
        compression_ratio_pct=compression,
        total_area_change_pct=area_change,
        simplified_coordinates=working,
    )
