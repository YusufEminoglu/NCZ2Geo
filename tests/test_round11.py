# -*- coding: utf-8 -*-
"""Unit tests for NCZ2Geo Round 11 features (Condominium Strata Slicer & GeoPackage Spatial Indexer)."""

from __future__ import annotations

import unittest

from ncz2geo import (
    BuildingFloorStrataProfile,
    NetcadCoordinate,
    NetcadEntity,
    RTreeBoundingBoxFilter,
    SpatialIndexOptimizationReport,
    StrataTitleUnitResult,
    optimize_geopackage_spatial_rtree,
    slice_condominium_strata_units,
)


class TestNCZ2GeoRound11(unittest.TestCase):
    def test_condominium_strata_slicer(self) -> None:
        poly = [(0.0, 0.0), (20.0, 0.0), (20.0, 20.0), (0.0, 20.0)]
        prof = BuildingFloorStrataProfile(
            building_id="Rezidans_A",
            number_of_floors=4,
            units_per_floor=3,
            gross_floor_area_m2=360.0,
        )

        res = slice_condominium_strata_units(poly, profile=prof, base_elevation_m=10.0)

        self.assertIsInstance(res, StrataTitleUnitResult)
        self.assertEqual(res.total_strata_units_count, 12)
        self.assertGreater(res.total_net_residential_area_m2, 0.0)
        self.assertAlmostEqual(res.unit_land_share_ratio, 1.0 / 12.0, places=4)

        d = res.to_dict()
        self.assertIn("building_id", d)
        self.assertIn("total_units", d)
        self.assertIn("land_share_per_unit", d)

    def test_geopackage_spatial_indexer(self) -> None:
        coords1 = [NetcadCoordinate(10.0, 10.0), NetcadCoordinate(20.0, 20.0)]
        coords2 = [NetcadCoordinate(100.0, 100.0), NetcadCoordinate(110.0, 110.0)]
        ent1 = NetcadEntity(geometry_kind="LINESTRING", layer_code=1, layer_name="ROAD", is_closed=False, coordinates=coords1)
        ent2 = NetcadEntity(geometry_kind="LINESTRING", layer_code=1, layer_name="ROAD", is_closed=False, coordinates=coords2)

        bbox_filter = RTreeBoundingBoxFilter(min_x=0.0, max_x=50.0, min_y=0.0, max_y=50.0)
        report = optimize_geopackage_spatial_rtree([ent1, ent2], test_query_bbox=bbox_filter)

        self.assertIsInstance(report, SpatialIndexOptimizationReport)
        self.assertEqual(report.total_entities_indexed, 2)
        self.assertEqual(report.matching_entities_in_query, 1)

        d = report.to_dict()
        self.assertIn("indexed_count", d)
        self.assertIn("rtree_depth", d)
