# -*- coding: utf-8 -*-
"""Unit tests for NCZ2Geo Round 7 features (Boundary Simplification & FlatGeobuf Exporter)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ncz2geo import (
    BoundarySimplificationResult,
    FlatGeobufExportResult,
    NetcadCoordinate,
    NetcadEntity,
    export_entities_to_flatgeobuf,
    simplify_cadastral_boundaries,
)


class TestNCZ2GeoRound7(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_cadastral_boundary_simplification(self) -> None:
        # A rectangle with minor noisy collinear jitter points
        coords = [
            (0.0, 0.0),
            (25.0, 0.05),
            (50.0, 0.0),
            (75.0, -0.05),
            (100.0, 0.0),
            (100.0, 50.0),
            (0.0, 50.0),
            (0.0, 0.0),
        ]
        res = simplify_cadastral_boundaries(coords, min_effective_area_threshold_m2=2.0)

        self.assertIsInstance(res, BoundarySimplificationResult)
        self.assertEqual(res.original_vertex_count, 8)
        self.assertLess(res.simplified_vertex_count, 8)
        self.assertGreater(res.compression_ratio_pct, 0.0)

        d = res.to_dict()
        self.assertIn("compression_pct", d)
        self.assertIn("area_change_pct", d)

    def test_flatgeobuf_export(self) -> None:
        coords = [
            NetcadCoordinate(10.0, 20.0),
            NetcadCoordinate(30.0, 20.0),
            NetcadCoordinate(30.0, 40.0),
            NetcadCoordinate(10.0, 40.0),
            NetcadCoordinate(10.0, 20.0),
        ]
        ent = NetcadEntity(
            geometry_kind="POLYGON",
            layer_code=1,
            layer_name="PARCEL_BOUNDARY",
            is_closed=True,
            coordinates=coords,
        )

        fgb_path = self.tmp / "test_parcels.fgb"
        result = export_entities_to_flatgeobuf([ent], fgb_path)

        self.assertIsInstance(result, FlatGeobufExportResult)
        self.assertEqual(result.feature_count, 1)
        self.assertTrue(fgb_path.exists())
        self.assertGreater(result.file_size_bytes, 0)
        self.assertEqual(result.bounding_box_min_x, 10.0)
        self.assertEqual(result.bounding_box_max_y, 40.0)

        d = result.to_dict()
        self.assertIn("bbox", d)
        self.assertIn("feature_count", d)
