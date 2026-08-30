# -*- coding: utf-8 -*-
"""Visvalingam-Whyatt & 3D Douglas-Peucker Geometry Simplifier for NCZ2Geo."""

from __future__ import annotations

import math
from typing import Any, Iterable, Sequence

from .ncz_engine.model import NetcadCoordinate, NetcadEntity


def _triangle_area_2d(p1: NetcadCoordinate, p2: NetcadCoordinate, p3: NetcadCoordinate) -> float:
    """Compute effective area of triangle formed by 3 vertices."""
    return 0.5 * abs(
        p1.x * (p2.y - p3.y) + p2.x * (p3.y - p1.y) + p3.x * (p1.y - p2.y)
    )


def visvalingam_whyatt_simplify(
    coords: Sequence[NetcadCoordinate],
    min_area_threshold: float = 1.0,
) -> list[NetcadCoordinate]:
    """Visvalingam-Whyatt line simplification based on minimum triangle area."""
    n = len(coords)
    if n <= 2:
        return list(coords)

    pts = list(coords)
    while len(pts) > 2:
        # Find vertex with minimum effective triangle area
        min_area = float("inf")
        min_idx = -1

        for i in range(1, len(pts) - 1):
            area = _triangle_area_2d(pts[i - 1], pts[i], pts[i + 1])
            if area < min_area:
                min_area = area
                min_idx = i

        if min_area < min_area_threshold and min_idx != -1:
            pts.pop(min_idx)
        else:
            break

    return pts


def _perpendicular_distance_3d(pt: NetcadCoordinate, line_start: NetcadCoordinate, line_end: NetcadCoordinate) -> float:
    """Perpendicular Euclidean distance from 3D point to line segment."""
    dx = line_end.x - line_start.x
    dy = line_end.y - line_start.y
    dz = line_end.z - line_start.z
    seg_len_sq = dx * dx + dy * dy + dz * dz
    if seg_len_sq <= 1e-9:
        return math.sqrt((pt.x - line_start.x) ** 2 + (pt.y - line_start.y) ** 2 + (pt.z - line_start.z) ** 2)

    # Projection factor t
    t = ((pt.x - line_start.x) * dx + (pt.y - line_start.y) * dy + (pt.z - line_start.z) * dz) / seg_len_sq
    t = max(0.0, min(1.0, t))
    proj_x = line_start.x + t * dx
    proj_y = line_start.y + t * dy
    proj_z = line_start.z + t * dz
    return math.sqrt((pt.x - proj_x) ** 2 + (pt.y - proj_y) ** 2 + (pt.z - proj_z) ** 2)


def douglas_peucker_3d(
    coords: Sequence[NetcadCoordinate],
    tolerance: float = 0.50,
) -> list[NetcadCoordinate]:
    """Recursive 3D Douglas-Peucker polyline simplification."""
    n = len(coords)
    if n <= 2:
        return list(coords)

    # Find point with maximum distance
    dmax = 0.0
    index = 0
    start = coords[0]
    end = coords[-1]

    for i in range(1, n - 1):
        d = _perpendicular_distance_3d(coords[i], start, end)
        if d > dmax:
            index = i
            dmax = d

    if dmax > tolerance:
        rec1 = douglas_peucker_3d(coords[: index + 1], tolerance)
        rec2 = douglas_peucker_3d(coords[index:], tolerance)
        return rec1[:-1] + rec2
    else:
        return [start, end]


def simplify_entities(
    entities: Iterable[NetcadEntity],
    method: str = "douglas_peucker",
    tolerance: float = 0.50,
) -> list[NetcadEntity]:
    """Simplify coordinates of all entities in drawing."""
    simplified: list[NetcadEntity] = []
    for e in entities:
        if not e.coordinates or len(e.coordinates) <= 2:
            simplified.append(e)
            continue

        if method == "visvalingam":
            new_coords = visvalingam_whyatt_simplify(e.coordinates, min_area_threshold=tolerance)
        else:
            new_coords = douglas_peucker_3d(e.coordinates, tolerance=tolerance)

        # If entity was closed, preserve closure
        if e.is_closed and len(new_coords) >= 3 and (new_coords[0].x != new_coords[-1].x or new_coords[0].y != new_coords[-1].y):
            new_coords.append(new_coords[0])

        simplified.append(
            NetcadEntity(
                geometry_kind=e.geometry_kind,
                layer_code=e.layer_code,
                layer_name=e.layer_name,
                color_argb=e.color_argb,
                name=e.name,
                label_text=e.label_text,
                text_height=e.text_height,
                rotation_degrees=e.rotation_degrees,
                box_width=e.box_width,
                box_height=e.box_height,
                scale=e.scale,
                grid_x=e.grid_x,
                grid_y=e.grid_y,
                radius=e.radius,
                start_angle=e.start_angle,
                end_angle=e.end_angle,
                is_closed=e.is_closed,
                coordinates=new_coords,
            )
        )

    return simplified
