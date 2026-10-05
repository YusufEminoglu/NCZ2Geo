# -*- coding: utf-8 -*-
"""Unit tests for NCZ2Geo Round 10 features (Dispute Resolver & GeoZip Archiver)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ncz2geo import (
    BoundaryDisputeResolutionReport,
    GeoZipArchiveResult,
    NetcadCoordinate,
    NetcadEntity,
    create_geozip_spatial_archive,
    resolve_cadastral_boundary_disputes,
)


class TestNCZ2GeoRound10(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_cadastral_boundary_dispute_resolver(self) -> None:
        parcels = [
            {"id": "Parcel_A", "cx": 100.0, "cy": 100.0, "area": 1200.0},
            {"id": "Parcel_B", "cx": 120.0, "cy": 110.0, "area": 1500.0},
            {"id": "Parcel_C", "cx": 500.0, "cy": 500.0, "area": 3000.0},
        ]

        report = resolve_cadastral_boundary_disputes(parcels, sliver_area_tolerance_m2=20.0)

        self.assertIsInstance(report, BoundaryDisputeResolutionReport)
        self.assertEqual(report.total_parcels_evaluated, 3)
        self.assertGreaterEqual(report.disputed_slivers_found_count, 1)

        d = report.to_dict()
        self.assertIn("evaluated_parcels", d)
        self.assertIn("slivers_found", d)

    def test_geozip_spatial_archiver(self) -> None:
        coords = [
            NetcadCoordinate(29.0, 41.0),
            NetcadCoordinate(29.1, 41.0),
            NetcadCoordinate(29.1, 41.1),
            NetcadCoordinate(29.0, 41.1),
            NetcadCoordinate(29.0, 41.0),
        ]
        ent = NetcadEntity(
            geometry_kind="POLYGON",
            layer_code=10,
            layer_name="RESIDENTIAL_ZONE",
            is_closed=True,
            coordinates=coords,
        )

        zip_path = self.tmp / "dataset.geozip"
        res = create_geozip_spatial_archive([ent], zip_path)

        self.assertIsInstance(res, GeoZipArchiveResult)
        self.assertTrue(zip_path.exists())
        self.assertGreaterEqual(res.total_files_count, 2)
        self.assertGreater(res.compressed_size_bytes, 0)

        d = res.to_dict()
        self.assertIn("archive_path", d)
        self.assertIn("files_count", d)
