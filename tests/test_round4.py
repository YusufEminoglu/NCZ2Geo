# -*- coding: utf-8 -*-
"""Unit tests for NCZ2Geo Round 4 features (Zoning Capacity & Simplifier)."""

from __future__ import annotations

import unittest

from ncz2geo import (
    ZoningCapacityReport,
    calculate_zoning_capacity,
    douglas_peucker_3d,
    simplify_entities,
    visvalingam_whyatt_simplify,
)
from ncz2geo.ncz_engine.model import NetcadCoordinate, NetcadEntity


class TestNCZ2GeoRound4(unittest.TestCase):
    def test_zoning_density_and_demographic_capacity(self) -> None:
        coords_res = [
            NetcadCoordinate(0.0, 0.0),
            NetcadCoordinate(100.0, 0.0),
            NetcadCoordinate(100.0, 100.0),
            NetcadCoordinate(0.0, 100.0),
            NetcadCoordinate(0.0, 0.0),
        ]
        entities = [
            NetcadEntity(geometry_kind="POLYGON", layer_code=1, layer_name="PL_GELISME_KONUT", is_closed=True, coordinates=coords_res),
            NetcadEntity(geometry_kind="POLYGON", layer_code=2, layer_name="PL_TICARET", is_closed=True, coordinates=coords_res),
        ]

        report = calculate_zoning_capacity(entities, plan_type="UIP", default_emsal=1.80)
        self.assertIsInstance(report, ZoningCapacityReport)
        self.assertGreater(report.total_plan_area_m2, 0.0)
        self.assertGreater(report.total_estimated_residents, 0)
        self.assertGreater(report.total_required_parking_spaces, 0)

        d = report.to_dict()
        self.assertIn("total_plan_area_ha", d)
        self.assertIn("gross_density_persons_per_ha", d)

    def test_geometry_simplifiers(self) -> None:
        pts = [
            NetcadCoordinate(0.0, 0.0, 0.0),
            NetcadCoordinate(10.0, 0.1, 0.0),  # Minor jitter
            NetcadCoordinate(20.0, -0.1, 0.0), # Minor jitter
            NetcadCoordinate(30.0, 10.0, 0.0), # Major vertex
            NetcadCoordinate(50.0, 10.0, 0.0),
        ]

        # Visvalingam-Whyatt
        vw = visvalingam_whyatt_simplify(pts, min_area_threshold=2.0)
        self.assertLess(len(vw), len(pts))
        self.assertEqual(vw[0].x, 0.0)
        self.assertEqual(vw[-1].x, 50.0)

        # Douglas-Peucker 3D
        dp = douglas_peucker_3d(pts, tolerance=0.50)
        self.assertLess(len(dp), len(pts))
        self.assertEqual(dp[0].x, 0.0)
        self.assertEqual(dp[-1].x, 50.0)

        # Entity wrapper
        e = NetcadEntity(geometry_kind="POLYLINE", layer_code=0, layer_name="ROAD", coordinates=pts)
        simplified = simplify_entities([e], method="douglas_peucker", tolerance=0.50)
        self.assertEqual(len(simplified), 1)
        self.assertLess(len(simplified[0].coordinates), len(pts))
