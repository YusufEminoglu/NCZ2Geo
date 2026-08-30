# -*- coding: utf-8 -*-
"""Unit tests for NCZ2Geo Round 9 features (ROW Easement Slicer & GeoBuff Encoder)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ncz2geo import (
    EasementCorridorResult,
    GeoBuffExportResult,
    NetcadCoordinate,
    NetcadEntity,
    export_entities_to_geobuff,
    generate_easement_corridor_slices,
)


class TestNCZ2GeoRound9(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_cadastral_right_of_way_easement(self) -> None:
        centerline = [(0.0, 0.0), (500.0, 0.0)]
        parcels = [
            {"id": "Ada101_Parsel1", "area_m2": 3000.0, "center": (100.0, 5.0)},
            {"id": "Ada101_Parsel2", "area_m2": 4000.0, "center": (300.0, 50.0)},
        ]

        res = generate_easement_corridor_slices(centerline, parcels, corridor_half_width_m=20.0)

        self.assertIsInstance(res, EasementCorridorResult)
        self.assertEqual(res.corridor_length_m, 500.0)
        self.assertEqual(res.corridor_width_m, 40.0)
        self.assertGreater(res.total_easement_area_m2, 0.0)
        self.assertGreaterEqual(res.impacted_parcels_count, 1)

        d = res.to_dict()
        self.assertIn("length_m", d)
        self.assertIn("total_easement_area_m2", d)

    def test_geobuff_compact_export(self) -> None:
        coords = [
            NetcadCoordinate(29.0, 41.0),
            NetcadCoordinate(29.1, 41.0),
            NetcadCoordinate(29.1, 41.1),
            NetcadCoordinate(29.0, 41.1),
            NetcadCoordinate(29.0, 41.0),
        ]
        ent = NetcadEntity(
            geometry_kind="POLYGON",
            layer_code=5,
            layer_name="FOREST_ZONE",
            is_closed=True,
            coordinates=coords,
        )

        gbuf_path = self.tmp / "test.geobuff"
        res = export_entities_to_geobuff([ent], gbuf_path)

        self.assertIsInstance(res, GeoBuffExportResult)
        self.assertEqual(res.feature_count, 1)
        self.assertTrue(gbuf_path.exists())
        self.assertGreater(res.file_size_bytes, 0)

        d = res.to_dict()
        self.assertIn("feature_count", d)
        self.assertIn("size_bytes", d)
