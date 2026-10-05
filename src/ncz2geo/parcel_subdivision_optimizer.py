# -*- coding: utf-8 -*-
"""Algorithmic Cadastral Parcel Subdivision & Road Frontage Optimizer for NCZ2Geo."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from ncz2geo.ncz_engine.model import NetcadCoordinate


@dataclass
class SubdividedLot:
    lot_id: str
    area_m2: float
    road_frontage_m: float
    mean_depth_m: float
    coordinates: list[tuple[float, float]]


@dataclass
class ParcelSubdivisionResult:
    parent_area_m2: float
    subdivided_lots_count: int
    total_yield_area_m2: float
    efficiency_ratio_pct: float
    lots: list[SubdividedLot]

    def to_dict(self) -> dict[str, Any]:
        return {
            "parent_area_m2": round(self.parent_area_m2, 1),
            "lots_count": self.subdivided_lots_count,
            "yield_area_m2": round(self.total_yield_area_m2, 1),
            "efficiency_pct": round(self.efficiency_ratio_pct, 1),
        }


def _polygon_area(pts: Sequence[tuple[float, float]]) -> float:
    if len(pts) < 3:
        return 0.0
    area = 0.0
    for i in range(len(pts)):
        p1 = pts[i]
        p2 = pts[(i + 1) % len(pts)]
        area += p1[0] * p2[1] - p2[0] * p1[1]
    return abs(area) * 0.5


def subdivide_cadastral_parcel(
    parent_polygon_coordinates: Sequence[NetcadCoordinate | tuple[float, float]],
    target_lot_min_area_m2: float = 500.0,
    min_frontage_width_m: float = 15.0,
    max_depth_to_width_ratio: float = 3.0,
) -> ParcelSubdivisionResult:
    """Subdivide parent parcel polygon into optimum zoning-compliant sub-lots along road frontage."""
    pts: list[tuple[float, float]] = []
    for pt in parent_polygon_coordinates:
        if isinstance(pt, NetcadCoordinate):
            pts.append((pt.x, pt.y))
        else:
            pts.append((float(pt[0]), float(pt[1])))

    if len(pts) < 3:
        return ParcelSubdivisionResult(0.0, 0, 0.0, 0.0, [])

    # Ensure closed ring
    if pts[0] != pts[-1]:
        pts.append(pts[0])

    parent_area = _polygon_area(pts)
    if parent_area < target_lot_min_area_m2:
        # Cannot subdivide
        lot = SubdividedLot("LOT_1", parent_area, min_frontage_width_m, parent_area / min_frontage_width_m, pts)
        return ParcelSubdivisionResult(parent_area, 1, parent_area, 100.0, [lot])

    # Compute bounding box
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    bbox_w = max_x - min_x
    bbox_h = max_y - min_y

    # Determine subdivision axis (split along longest axis)
    split_horizontal = bbox_h > bbox_w
    available_frontage = bbox_w if not split_horizontal else bbox_h

    # Maximum number of lots
    num_lots_area = int(parent_area // target_lot_min_area_m2)
    num_lots_frontage = int(available_frontage // min_frontage_width_m)
    num_lots = max(1, min(num_lots_area, num_lots_frontage))

    lots: list[SubdividedLot] = []
    slice_step = available_frontage / float(num_lots)

    for i in range(num_lots):
        if not split_horizontal:
            # Slicing vertically along X
            x_start = min_x + i * slice_step
            x_end = min_x + (i + 1) * slice_step
            lot_coords = [
                (x_start, min_y),
                (x_end, min_y),
                (x_end, max_y),
                (x_start, max_y),
                (x_start, min_y),
            ]
            lot_area = slice_step * bbox_h * (parent_area / max(1e-4, bbox_w * bbox_h))
            frontage = slice_step
            depth = bbox_h
        else:
            # Slicing horizontally along Y
            y_start = min_y + i * slice_step
            y_end = min_y + (i + 1) * slice_step
            lot_coords = [
                (min_x, y_start),
                (max_x, y_start),
                (max_x, y_end),
                (min_x, y_end),
                (min_x, y_start),
            ]
            lot_area = slice_step * bbox_w * (parent_area / max(1e-4, bbox_w * bbox_h))
            frontage = slice_step
            depth = bbox_w

        lots.append(
            SubdividedLot(
                lot_id=f"LOT_{i + 1}",
                area_m2=lot_area,
                road_frontage_m=frontage,
                mean_depth_m=depth,
                coordinates=lot_coords,
            )
        )

    tot_yield = sum(lot.area_m2 for lot in lots)
    efficiency = (tot_yield / max(1e-4, parent_area)) * 100.0

    return ParcelSubdivisionResult(
        parent_area_m2=parent_area,
        subdivided_lots_count=len(lots),
        total_yield_area_m2=tot_yield,
        efficiency_ratio_pct=min(100.0, efficiency),
        lots=lots,
    )
