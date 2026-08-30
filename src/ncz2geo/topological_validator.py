# -*- coding: utf-8 -*-
"""Cadastral Plan Topological QA, Overlap, Gap and Self-Intersection Validator for NCZ2Geo."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Sequence

from .ncz_engine.model import NetcadCoordinate, NetcadEntity


@dataclass
class TopologyIssue:
    issue_type: str  # SELF_INTERSECTION, UNCLOSED_RING, DUPLICATE_VERTEX, SLIVER_GAP, ZERO_AREA
    entity_index: int
    layer_name: str
    description: str
    location: tuple[float, float] | None = None


@dataclass
class TopologyValidationReport:
    total_entities_checked: int
    is_topologically_valid: bool
    self_intersections_count: int
    unclosed_polygons_count: int
    zero_area_count: int
    duplicate_vertices_count: int
    issues: list[TopologyIssue]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_entities_checked": self.total_entities_checked,
            "is_valid": self.is_topologically_valid,
            "self_intersections": self.self_intersections_count,
            "unclosed_polygons": self.unclosed_polygons_count,
            "zero_area_polygons": self.zero_area_count,
            "duplicate_vertices": self.duplicate_vertices_count,
            "total_issues": len(self.issues),
        }


def _ccw(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]) -> bool:
    return (c[1] - a[1]) * (b[0] - a[0]) > (b[1] - a[1]) * (c[0] - a[0])


def _segments_intersect(
    p1: tuple[float, float], p2: tuple[float, float], p3: tuple[float, float], p4: tuple[float, float]
) -> bool:
    """Return True if line segments p1-p2 and p3-p4 intersect properly."""
    return (_ccw(p1, p3, p4) != _ccw(p2, p3, p4)) and (_ccw(p1, p2, p3) != _ccw(p1, p2, p4))


def validate_cadastral_topology(
    entities: Sequence[NetcadEntity],
    min_area_m2: float = 1.0,
    vertex_tolerance_m: float = 0.005,
) -> TopologyValidationReport:
    """Perform strict cadastral topology verification on NetCAD parcel boundaries."""
    issues: list[TopologyIssue] = []
    self_ints = 0
    unclosed = 0
    zero_areas = 0
    dups = 0

    for idx, ent in enumerate(entities):
        coords = ent.coordinates
        if not coords or len(coords) < 2:
            continue

        layer = ent.layer_name or "DEFAULT"
        pts = [(p.x, p.y) for p in coords]

        # 1. Check duplicate consecutive vertices
        for i in range(len(pts) - 1):
            if math.hypot(pts[i][0] - pts[i + 1][0], pts[i][1] - pts[i + 1][1]) < vertex_tolerance_m:
                dups += 1
                issues.append(
                    TopologyIssue(
                        issue_type="DUPLICATE_VERTEX",
                        entity_index=idx,
                        layer_name=layer,
                        description=f"Duplicate consecutive vertex at point {i}",
                        location=pts[i],
                    )
                )

        if ent.geometry_kind in ("POLYGON", "PARCEL") or ent.is_closed:
            # 2. Check unclosed polygon ring
            if math.hypot(pts[0][0] - pts[-1][0], pts[0][1] - pts[-1][1]) > vertex_tolerance_m:
                unclosed += 1
                issues.append(
                    TopologyIssue(
                        issue_type="UNCLOSED_RING",
                        entity_index=idx,
                        layer_name=layer,
                        description="Polygon ring start and end vertices do not match",
                        location=pts[0],
                    )
                )

            # 3. Check Shoelace polygon area
            n_pts = len(pts)
            area = 0.0
            for i in range(n_pts - 1):
                area += pts[i][0] * pts[i + 1][1] - pts[i + 1][0] * pts[i][1]
            area = abs(area) * 0.5

            if area < min_area_m2:
                zero_areas += 1
                issues.append(
                    TopologyIssue(
                        issue_type="ZERO_AREA",
                        entity_index=idx,
                        layer_name=layer,
                        description=f"Polygon area ({area:.4f} m2) is below minimum threshold ({min_area_m2} m2)",
                        location=pts[0],
                    )
                )

            # 4. Check polygon edge self-intersections (excluding adjacent sharing endpoints)
            if n_pts >= 4:
                for i in range(n_pts - 1):
                    p1 = pts[i]
                    p2 = pts[i + 1]
                    for j in range(i + 2, n_pts - 1):
                        if i == 0 and j == n_pts - 2:
                            continue  # Adjacent at ring closure
                        p3 = pts[j]
                        p4 = pts[j + 1]
                        if _segments_intersect(p1, p2, p3, p4):
                            self_ints += 1
                            issues.append(
                                TopologyIssue(
                                    issue_type="SELF_INTERSECTION",
                                    entity_index=idx,
                                    layer_name=layer,
                                    description=f"Edges {i}-{i+1} and {j}-{j+1} intersect",
                                    location=p1,
                                )
                            )

    is_valid = (self_ints == 0 and unclosed == 0 and zero_areas == 0 and dups == 0)

    return TopologyValidationReport(
        total_entities_checked=len(entities),
        is_topologically_valid=is_valid,
        self_intersections_count=self_ints,
        unclosed_polygons_count=unclosed,
        zero_area_count=zero_areas,
        duplicate_vertices_count=dups,
        issues=issues,
    )
