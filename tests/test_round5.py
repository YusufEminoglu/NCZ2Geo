# -*- coding: utf-8 -*-
"""Unit tests for NCZ2Geo Round 5 features (KML/KMZ 3D Exporter & Topological Validator)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ncz2geo import (
    KMLExportResult,
    KMLStyleConfig,
    NetcadCoordinate,
    NetcadEntity,
    TopologyIssue,
    TopologyValidationReport,
    export_to_kml_kmz,
    validate_cadastral_topology,
)


class TestNCZ2GeoRound5(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.temp_dir.name)

        # Standard clean square parcel
        self.clean_coords = [
            NetcadCoordinate(0.0, 0.0, 5.0),
            NetcadCoordinate(100.0, 0.0, 5.0),
            NetcadCoordinate(100.0, 100.0, 5.0),
            NetcadCoordinate(0.0, 100.0, 5.0),
            NetcadCoordinate(0.0, 0.0, 5.0),
        ]
        self.clean_entity = NetcadEntity(
            geometry_kind="POLYGON",
            layer_name="PL_KONUT",
            layer_code=1,
            is_closed=True,
            coordinates=self.clean_coords,
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_kml_kmz_exporter(self) -> None:
        cfg = KMLStyleConfig(line_color_abgr="ffff0000", extrude_3d=True, default_height_m=15.0)
        res = export_to_kml_kmz([self.clean_entity], document_name="Istanbul Kadastro", style_config=cfg)

        self.assertIsInstance(res, KMLExportResult)
        self.assertEqual(res.feature_count, 1)
        self.assertIn("<Polygon>", res.kml_string)
        self.assertIn("<extrude>1</extrude>", res.kml_string)
        self.assertGreater(len(res.kmz_bytes), 50)

        # Test file writes
        kml_path = self.tmp / "test.kml"
        kmz_path = self.tmp / "test.kmz"
        res.save_kml(kml_path)
        res.save_kmz(kmz_path)

        self.assertTrue(kml_path.exists())
        self.assertTrue(kmz_path.exists())

    def test_topological_validator_clean(self) -> None:
        report = validate_cadastral_topology([self.clean_entity])
        self.assertIsInstance(report, TopologyValidationReport)
        self.assertTrue(report.is_topologically_valid)
        self.assertEqual(len(report.issues), 0)

    def test_topological_validator_errors(self) -> None:
        # Self-intersecting bowtie polygon (0,0 -> 10,10 -> 0,10 -> 10,0 -> 0,0)
        bowtie_coords = [
            NetcadCoordinate(0.0, 0.0),
            NetcadCoordinate(10.0, 10.0),
            NetcadCoordinate(0.0, 10.0),
            NetcadCoordinate(10.0, 0.0),
            NetcadCoordinate(0.0, 0.0),
        ]
        bowtie_ent = NetcadEntity(
            geometry_kind="POLYGON",
            layer_name="ERROR_PARCEL",
            layer_code=2,
            is_closed=True,
            coordinates=bowtie_coords,
        )

        report = validate_cadastral_topology([bowtie_ent])
        self.assertFalse(report.is_topologically_valid)
        self.assertGreater(report.self_intersections_count, 0)
        self.assertTrue(any(i.issue_type == "SELF_INTERSECTION" for i in report.issues))

        d = report.to_dict()
        self.assertIn("total_issues", d)
        self.assertFalse(d["is_valid"])
