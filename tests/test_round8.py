# -*- coding: utf-8 -*-
"""Unit tests for NCZ2Geo Round 8 features (Parcel Subdivision & GeoParquet Exporter)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ncz2geo import (
    GeoParquetExportResult,
    NetcadCoordinate,
    NetcadEntity,
    ParcelSubdivisionResult,
    export_entities_to_geoparquet,
    subdivide_cadastral_parcel,
)


class TestNCZ2GeoRound8(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_parcel_subdivision_optimizer(self) -> None:
        # 100m x 50m parent parcel (5000 m2)
        poly = [(0.0, 0.0), (100.0, 0.0), (100.0, 50.0), (0.0, 50.0), (0.0, 0.0)]
        res = subdivide_cadastral_parcel(poly, target_lot_min_area_m2=800.0, min_frontage_width_m=15.0)

        self.assertIsInstance(res, ParcelSubdivisionResult)
        self.assertEqual(res.parent_area_m2, 5000.0)
        self.assertGreater(res.subdivided_lots_count, 1)
        self.assertGreater(res.total_yield_area_m2, 0.0)
        self.assertEqual(len(res.lots), res.subdivided_lots_count)

        d = res.to_dict()
        self.assertIn("lots_count", d)
        self.assertIn("efficiency_pct", d)

    def test_geoparquet_export(self) -> None:
        coords = [
            NetcadCoordinate(0.0, 0.0),
            NetcadCoordinate(50.0, 0.0),
            NetcadCoordinate(50.0, 50.0),
            NetcadCoordinate(0.0, 50.0),
            NetcadCoordinate(0.0, 0.0),
        ]
        ent = NetcadEntity(
            geometry_kind="POLYGON",
            layer_code=1,
            layer_name="ZONING_LOT",
            is_closed=True,
            coordinates=coords,
        )

        gpq_path = self.tmp / "parcels.geoparquet"
        res = export_entities_to_geoparquet([ent], gpq_path)

        self.assertIsInstance(res, GeoParquetExportResult)
        self.assertEqual(res.feature_count, 1)
        self.assertEqual(res.geoparquet_version, "1.1.0")
        self.assertTrue(gpq_path.exists())
        self.assertGreater(res.file_size_bytes, 0)

        d = res.to_dict()
        self.assertIn("version", d)
        self.assertIn("bbox", d)
