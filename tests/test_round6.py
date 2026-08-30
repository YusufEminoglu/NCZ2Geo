# -*- coding: utf-8 -*-
"""Unit tests for NCZ2Geo Round 6 features (Land Consolidation & GeoPackage Exporter)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ncz2geo import (
    ConsolidatedParcel,
    GeoPackageExportResult,
    LandConsolidationReport,
    NetcadCoordinate,
    NetcadEntity,
    OwnershipShare,
    export_entities_to_geopackage,
    optimize_land_consolidation,
)


class TestNCZ2GeoRound6(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_land_consolidation_and_dop(self) -> None:
        shares = [
            OwnershipShare(owner_id="Ali_Yilmaz", pre_consolidation_area_m2=5000.0, land_value_index=1.0),
            OwnershipShare(owner_id="Ayse_Demir", pre_consolidation_area_m2=3000.0, land_value_index=0.9),
            OwnershipShare(owner_id="Mehmet_Kaya", pre_consolidation_area_m2=2000.0, land_value_index=1.1),
        ]

        report = optimize_land_consolidation(shares, target_dop_rate_pct=40.0, target_parcel_min_width_m=25.0)

        self.assertIsInstance(report, LandConsolidationReport)
        self.assertEqual(report.total_pre_area_m2, 10000.0)
        self.assertEqual(report.total_public_deduction_m2, 4000.0)
        self.assertEqual(report.number_of_owners, 3)
        self.assertEqual(report.number_of_consolidated_parcels, 3)

        for p in report.parcels:
            self.assertIsInstance(p, ConsolidatedParcel)
            self.assertGreater(p.net_area_m2, 0.0)
            self.assertGreaterEqual(p.road_frontage_m, 25.0)
            self.assertEqual(len(p.boundary_polygon), 5)

        d = report.to_dict()
        self.assertIn("dop_rate_pct", d)
        self.assertIn("total_pre_area_m2", d)

    def test_geopackage_sqlite_export(self) -> None:
        coords = [
            NetcadCoordinate(0.0, 0.0),
            NetcadCoordinate(100.0, 0.0),
            NetcadCoordinate(100.0, 100.0),
            NetcadCoordinate(0.0, 100.0),
            NetcadCoordinate(0.0, 0.0),
        ]
        ent = NetcadEntity(
            geometry_kind="POLYGON",
            layer_code=1,
            layer_name="KADASTRAL_PARSEL",
            is_closed=True,
            coordinates=coords,
        )

        gpkg_path = self.tmp / "cadastre.gpkg"
        res = export_entities_to_geopackage([ent], gpkg_path, table_name="parcels", srs_id=5254)

        self.assertIsInstance(res, GeoPackageExportResult)
        self.assertTrue(gpkg_path.exists())
        self.assertEqual(res.total_features_written, 1)
        self.assertEqual(res.table_name, "parcels")
        self.assertGreater(res.file_size_bytes, 0)

        d = res.to_dict()
        self.assertIn("srs_id", d)
        self.assertIn("total_features", d)
