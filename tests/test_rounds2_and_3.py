# -*- coding: utf-8 -*-
"""Unit tests for NCZ2Geo Rounds 2 and 3 features (GML, Transformer, PlanDiff, Anonymizer)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ncz2geo import (
    Helmert7Params,
    affine_transform_2d,
    anonymize_ncz_attributes,
    compare_plans,
    export_citygml_lods,
    export_plangml_gml,
    helmert_7parameter_transform,
    parse_netcad,
    transform_entities,
)
from ncz2geo.ncz_engine.model import (
    NetcadAttributeRow,
    NetcadAttributeTable,
)
from tests import ncz_fixtures as fx


def _planning_drawing() -> bytes:
    return b"".join(
        [
            fx.version_block(),
            fx.layer_table_block([b"PL_GELISME_KONUT", b"HAT_OTOYOL", b"TEXT"]),
            fx.color_table_block([(255, 0, 0), (0, 128, 0), (0, 0, 255)]),
            fx.projection_block(),
            fx.epsg_block(),
            fx.polyline_block(layer=0, closed=True),
            fx.line_block(layer=1),
            fx.text_block(layer=2),
        ]
    )


class TestRounds2And3(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.temp_dir.name)
        self.source = self.tmp / "fixture.ncz"
        self.source.write_bytes(_planning_drawing())

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_gml_and_citygml_export(self) -> None:
        res = parse_netcad(self.source)
        gml_xml = export_plangml_gml(res.entities, plan_type="UIP")

        self.assertIn("<plangml:PlanFeatureCollection", gml_xml)
        self.assertIn("<plangml:PlanNesnesi", gml_xml)
        self.assertIn("<gml:Polygon", gml_xml)

        citygml_file = self.tmp / "citygml.xml"
        export_citygml_lods(res.entities, citygml_file)
        self.assertTrue(citygml_file.exists())
        self.assertIn("<core:CityModel", citygml_file.read_text(encoding="utf-8"))

    def test_helmert_and_affine_transformations(self) -> None:
        p = Helmert7Params(dx=10.0, dy=-5.0, dz=2.0, rx_arcsec=0.1, ry_arcsec=0.1, rz_arcsec=0.2, scale_ppm=1.0)
        nx, ny, nz = helmert_7parameter_transform(500000.0, 4500000.0, 100.0, p)
        self.assertNotEqual(nx, 500000.0)
        self.assertAlmostEqual(nz, 102.0, delta=5.0)

        ax, ay = affine_transform_2d(10.0, 20.0, a=2.0, b=0.0, c=0.0, d=2.0, tx=5.0, ty=5.0)
        self.assertEqual(ax, 25.0)
        self.assertEqual(ay, 45.0)

        res = parse_netcad(self.source)
        transformed = transform_entities(res.entities, transformation_type="helmert", helmert_params=p)
        self.assertEqual(len(transformed), len(res.entities))

    def test_compare_plans_difference(self) -> None:
        res = parse_netcad(self.source)
        diff = compare_plans(res.entities, res.entities, plan_type="UIP")

        self.assertEqual(diff.plan_type, "UIP")
        self.assertEqual(diff.added_features_count, 0)
        self.assertEqual(diff.removed_features_count, 0)

        d = diff.to_dict()
        self.assertIn("total_features_v1", d)

    def test_anonymize_ncz_attributes(self) -> None:
        table = NetcadAttributeTable(
            table_ref="@PARCEL",
            rows=[
                NetcadAttributeRow(row_index=1, columns={"ADA": "101", "PARSEL": "5", "MALIK_ADI_SOYADI": "Ahmet Yilmaz", "TC_KIMLIK": "12345678901"}),
                NetcadAttributeRow(row_index=2, columns={"ADA": "101", "PARSEL": "6", "MALIK_ADI_SOYADI": "Ayse Demir", "TC_KIMLIK": "98765432109"}),
            ],
        )

        scrubbed, report = anonymize_ncz_attributes([table])
        self.assertEqual(report.total_rows, 2)
        self.assertEqual(report.total_pii_fields_scrubbed, 4)

        first_row = scrubbed[0].rows[0].columns
        self.assertEqual(first_row["ADA"], "101")
        self.assertTrue(first_row["MALIK_ADI_SOYADI"].startswith("ANON_"))
        self.assertTrue(first_row["TC_KIMLIK"].startswith("ANON_"))
