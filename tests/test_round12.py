# -*- coding: utf-8 -*-
"""Edge-case and error-path tests for the public NCZ2Geo API."""

from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from ncz2geo import (
    AnonymizationReport,
    BuildingFloorStrataProfile,
    NetcadParseResult,
    NetcadReader,
    RTreeBoundingBoxFilter,
    calculate_zoning_capacity,
    classify_layer,
    classify_layers,
    create_geozip_spatial_archive,
    detect_plan_type,
    entities_to_feature_collection,
    export_entities_to_flatgeobuf,
    export_entities_to_geobuff,
    export_entities_to_geopackage,
    export_entities_to_geoparquet,
    export_to_kml_kmz,
    generate_easement_corridor_slices,
    mask_pii_value,
    normalize_layer_name,
    optimize_geopackage_spatial_rtree,
    resolve_cadastral_boundary_disputes,
    simplify_cadastral_boundaries,
    slice_condominium_strata_units,
    subdivide_cadastral_parcel,
    validate_cadastral_topology,
    validate_plan,
)
from ncz2geo.ncz_engine.model import NetcadCoordinate, NetcadEntity
from tests import ncz_fixtures as fx


def _point(x: float, y: float, z: float = 0.0) -> NetcadCoordinate:
    return NetcadCoordinate(x, y, z)


def _polygon(layer: int = 1, name: str = "PARCEL") -> NetcadEntity:
    return NetcadEntity(
        geometry_kind="POLYGON",
        layer_code=layer,
        layer_name=name,
        is_closed=True,
        coordinates=[
            _point(0.0, 0.0),
            _point(10.0, 0.0),
            _point(10.0, 10.0),
            _point(0.0, 10.0),
            _point(0.0, 0.0),
        ],
    )


class TestClassificationAndAnonymization(unittest.TestCase):
    def test_mask_pii_value_is_stable_and_salt_dependent(self) -> None:
        self.assertEqual(mask_pii_value(""), "")

        first = mask_pii_value("Ahmet Yilmaz", salt="salt-a")
        self.assertTrue(first.startswith("ANON_"))
        self.assertEqual(len(first), len("ANON_") + 8)
        self.assertEqual(first, mask_pii_value("Ahmet Yilmaz", salt="salt-a"))
        self.assertNotEqual(first, mask_pii_value("Ahmet Yilmaz", salt="salt-b"))

    def test_anonymization_report_to_dict(self) -> None:
        report = AnonymizationReport(
            total_tables=2,
            total_rows=5,
            total_pii_fields_scrubbed=3,
            scrubbed_columns=["TC_KIMLIK", "MALIK"],
        )
        payload = report.to_dict()

        self.assertEqual(payload["total_tables"], 2)
        self.assertEqual(payload["total_rows"], 5)
        self.assertEqual(payload["total_pii_fields_scrubbed"], 3)
        self.assertEqual(payload["scrubbed_columns"], ["TC_KIMLIK", "MALIK"])

    def test_detect_and_normalize_plan_type(self) -> None:
        self.assertIsNone(detect_plan_type(None))
        self.assertIsNone(detect_plan_type(""))
        self.assertEqual(detect_plan_type("UIP_PLAN_500"), "UIP")
        self.assertEqual(detect_plan_type("PLAN_25000"), "CDP")
        self.assertEqual(detect_plan_type("NAZIM_IMAR_5000"), "NIP")
        self.assertIsNone(detect_plan_type("PARCEL_1"))

        self.assertEqual(normalize_layer_name(None), "")
        self.assertEqual(normalize_layer_name("  PL_GELISME_KONUT  "), "GELISME_KONUT")
        self.assertEqual(
            normalize_layer_name("PL_GELISME_KONUT", strip_known_prefixes=False), "PL_GELISME_KONUT"
        )

    def test_classify_layers_deduplicates_and_handles_unknown(self) -> None:
        classified = classify_layers(["PL_GELISME_KONUT", "PL_GELISME_KONUT"])
        self.assertEqual(list(classified), ["PL_GELISME_KONUT"])
        self.assertTrue(classified["PL_GELISME_KONUT"].matched)

        unknown = classify_layer("NO_SUCH_LAYER_XYZ", plan_type=None)
        self.assertFalse(unknown.matched)
        self.assertEqual(unknown.plan_type, "UIP")
        self.assertIsNone(unknown.identity)
        self.assertIsNone(unknown.style)
        self.assertFalse(unknown.to_dict()["matched"])


class TestGeoJsonEdgeCases(unittest.TestCase):
    def test_entities_to_feature_collection_geometry_branches(self) -> None:
        text = NetcadEntity(
            geometry_kind="TEXT",
            layer_code=1,
            layer_name="TEXT",
            label_text="HELLO",
            coordinates=[_point(1.0, 2.0, 3.0)],
        )
        short_ring = NetcadEntity(
            geometry_kind="POLYGON",
            layer_code=2,
            layer_name="SHORT",
            is_closed=True,
            coordinates=[_point(0.0, 0.0), _point(1.0, 0.0)],
        )
        open_line = NetcadEntity(
            geometry_kind="POLYLINE",
            layer_code=3,
            layer_name="LINE",
            coordinates=[_point(0.0, 0.0), _point(1.0, 1.0)],
        )
        empty = NetcadEntity(geometry_kind="LINE", layer_code=4, layer_name="EMPTY")

        collection = entities_to_feature_collection(
            [text, short_ring, open_line, empty], plan_type="UIP"
        )

        self.assertEqual(len(collection["features"]), 3)
        geometries = [feature["geometry"]["type"] for feature in collection["features"]]
        self.assertEqual(geometries, ["Point", "LineString", "LineString"])
        self.assertEqual(collection["features"][0]["geometry"]["coordinates"], [1.0, 2.0, 3.0])

    def test_entities_to_feature_collection_empty(self) -> None:
        collection = entities_to_feature_collection([], plan_type="UIP")
        self.assertEqual(collection, {"type": "FeatureCollection", "features": []})


class TestValidationEdgeCases(unittest.TestCase):
    def test_validate_plan_rejects_unsupported_source(self) -> None:
        with self.assertRaises(TypeError):
            validate_plan(object())

    def test_validate_plan_empty_result_reports_missing_mandatory_layers(self) -> None:
        report = validate_plan(NetcadParseResult())

        self.assertEqual(report.plan_type, "UIP")
        self.assertFalse(report.is_valid)
        self.assertEqual(report.total_layers, 0)
        self.assertIn("ONAMA_SINIRI", report.mandatory_layers_missing)
        self.assertGreaterEqual(report.quality_score, 0.0)
        self.assertLessEqual(report.quality_score, 100.0)
        self.assertIn("# PlanGML & e-Plan Compliance Report (UIP)", report.to_markdown())
        self.assertFalse(report.to_dict()["is_valid"])

    def test_validate_plan_accepts_reader_instance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "fixture.ncz"
            source.write_bytes(_planning_drawing())
            reader = NetcadReader(source).index()

            report = validate_plan(reader)

            self.assertEqual(report.plan_type, "UIP")
            self.assertEqual(report.total_layers, 3)
            self.assertEqual(report.matched_layers, 2)
            self.assertEqual(report.unmatched_layers, ["TEXT"])


class TestCadastralEdgeCases(unittest.TestCase):
    def test_simplify_boundaries_short_input_and_closed_ring(self) -> None:
        short = simplify_cadastral_boundaries([(0.0, 0.0), (1.0, 1.0)])
        self.assertEqual(short.original_vertex_count, 2)
        self.assertEqual(short.simplified_vertex_count, 2)
        self.assertEqual(short.compression_ratio_pct, 0.0)

        ring = [(0, 0), (10, 0), (20, 0), (20, 20), (0, 20), (0, 0)]
        result = simplify_cadastral_boundaries(ring, min_effective_area_threshold_m2=5.0)
        self.assertLess(result.simplified_vertex_count, result.original_vertex_count)
        self.assertEqual(result.simplified_coordinates[0], result.simplified_coordinates[-1])
        self.assertGreater(result.compression_ratio_pct, 0.0)

    def test_subdivide_parcel_short_input_and_undersized_parent(self) -> None:
        short = subdivide_cadastral_parcel([(0.0, 0.0), (1.0, 1.0)])
        self.assertEqual(short.subdivided_lots_count, 0)
        self.assertEqual(short.lots, [])

        tiny = subdivide_cadastral_parcel(
            [(0.0, 0.0), (10.0, 0.0), (0.0, 10.0)], target_lot_min_area_m2=500.0
        )
        self.assertEqual(tiny.subdivided_lots_count, 1)
        self.assertEqual(tiny.lots[0].lot_id, "LOT_1")
        self.assertAlmostEqual(tiny.parent_area_m2, 50.0)
        self.assertEqual(tiny.efficiency_ratio_pct, 100.0)

    def test_zoning_capacity_ignores_degenerate_input(self) -> None:
        report = calculate_zoning_capacity([], plan_type="UIP")
        self.assertEqual(report.total_plan_area_m2, 0.0)
        self.assertEqual(report.total_estimated_residents, 0)
        self.assertEqual(report.parcels, [])

        two_points = NetcadEntity(
            geometry_kind="POLYLINE",
            layer_code=1,
            layer_name="ROAD",
            coordinates=[_point(0.0, 0.0), _point(1.0, 1.0)],
        )
        self.assertEqual(calculate_zoning_capacity([two_points]).parcels, [])

    def test_topology_detects_duplicate_and_unclosed(self) -> None:
        entity = NetcadEntity(
            geometry_kind="POLYGON",
            layer_code=1,
            layer_name="PARCEL",
            is_closed=True,
            coordinates=[
                _point(0.0, 0.0),
                _point(0.0, 0.0),
                _point(10.0, 0.0),
                _point(10.0, 10.0),
            ],
        )
        report = validate_cadastral_topology([entity])

        self.assertEqual(report.total_entities_checked, 1)
        self.assertEqual(report.duplicate_vertices_count, 1)
        self.assertEqual(report.unclosed_polygons_count, 1)
        self.assertFalse(report.is_topologically_valid)
        self.assertEqual(report.to_dict()["duplicate_vertices"], 1)

    def test_dispute_resolver_accepts_entities(self) -> None:
        report = resolve_cadastral_boundary_disputes([_polygon(1, "A"), _polygon(2, "B")])

        self.assertEqual(report.total_parcels_evaluated, 2)
        self.assertEqual(report.disputed_slivers_found_count, 1)
        self.assertEqual(report.resolved_disputes[0].allocation_method, "MEDIAN_SPLIT")
        self.assertIn(
            report.resolved_disputes[0].allocated_to_parcel_id,
            {report.resolved_disputes[0].parcel_a_id, report.resolved_disputes[0].parcel_b_id},
        )

    def test_easement_short_centerline_and_severe_restriction(self) -> None:
        empty = generate_easement_corridor_slices([(0.0, 0.0)], [])
        self.assertEqual(empty.corridor_length_m, 0.0)
        self.assertEqual(empty.impacted_parcels_count, 0)

        result = generate_easement_corridor_slices(
            [(0.0, 0.0), (100.0, 0.0)],
            [{"id": "P1", "area_m2": 1000.0, "center": (50.0, 0.0)}],
            corridor_half_width_m=15.0,
        )
        self.assertEqual(result.impacted_parcels_count, 1)
        self.assertEqual(result.severely_restricted_parcels_count, 1)
        self.assertTrue(result.parcel_impacts[0].is_severely_restricted)
        self.assertEqual(result.to_dict()["width_m"], 30.0)

    def test_strata_slicer_zero_units(self) -> None:
        profile = BuildingFloorStrataProfile(
            building_id="B0", number_of_floors=0, units_per_floor=0
        )
        result = slice_condominium_strata_units([(0.0, 0.0), (10.0, 0.0)], profile=profile)

        self.assertEqual(result.total_strata_units_count, 0)
        self.assertEqual(result.strata_units_list, [])
        self.assertEqual(result.unit_land_share_ratio, 0.0)


class TestExportEdgeCases(unittest.TestCase):
    def test_spatial_index_empty_and_query(self) -> None:
        empty = optimize_geopackage_spatial_rtree([])
        self.assertEqual(empty.total_entities_indexed, 0)
        self.assertEqual(empty.matching_entities_in_query, 0)

        entities = [_polygon(1), _polygon(2)]
        query = RTreeBoundingBoxFilter(min_x=5.0, max_x=15.0, min_y=5.0, max_y=15.0)
        report = optimize_geopackage_spatial_rtree(entities, test_query_bbox=query)
        self.assertEqual(report.total_entities_indexed, 2)
        self.assertEqual(report.matching_entities_in_query, 2)
        self.assertGreater(report.index_storage_estimate_bytes, 0)

    def test_kml_export_point_line_polygon_and_save(self) -> None:
        point = NetcadEntity(
            geometry_kind="POINT",
            layer_code=1,
            layer_name="P",
            coordinates=[_point(1.0, 2.0, 3.0)],
        )
        line = NetcadEntity(
            geometry_kind="LINE",
            layer_code=2,
            layer_name="L",
            coordinates=[_point(0.0, 0.0), _point(5.0, 5.0)],
        )
        result = export_to_kml_kmz([point, line, _polygon(), NetcadEntity("LINE", 9, "E")])

        self.assertEqual(result.feature_count, 3)
        self.assertIn("<Point>", result.kml_string)
        self.assertIn("<LineString>", result.kml_string)
        self.assertIn("<Polygon>", result.kml_string)

        with tempfile.TemporaryDirectory() as tmp:
            kml_path = result.save_kml(Path(tmp) / "nested" / "doc.kml")
            kmz_path = result.save_kmz(Path(tmp) / "doc.kmz")
            self.assertEqual(kml_path.read_text(encoding="utf-8"), result.kml_string)
            self.assertTrue(zipfile.is_zipfile(kmz_path))

    def test_empty_exports_produce_zero_features(self) -> None:
        empty = [NetcadEntity(geometry_kind="LINE", layer_code=1)]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            flat = export_entities_to_flatgeobuf(empty, root / "out.fgb")
            buff = export_entities_to_geobuff(empty, root / "out.gbuf")
            parquet = export_entities_to_geoparquet(empty, root / "out.parquet")
            gpkg = export_entities_to_geopackage(empty, root / "out.gpkg")

            self.assertEqual(flat.feature_count, 0)
            self.assertEqual(flat.to_dict()["bbox"], [0.0, 0.0, 0.0, 0.0])
            self.assertEqual(buff.feature_count, 0)
            self.assertEqual(parquet.feature_count, 0)
            self.assertEqual(parquet.bounding_box, [0.0, 0.0, 0.0, 0.0])
            self.assertEqual(gpkg.total_features_written, 0)
            self.assertTrue((root / "out.gpkg").exists())

    def test_geozip_without_payloads_is_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "archive.zip"
            result = create_geozip_spatial_archive(
                [],
                out,
                include_geojson=False,
                include_metadata_json=False,
            )

            self.assertEqual(result.total_files_count, 0)
            self.assertEqual(result.entries, [])
            self.assertEqual(result.uncompressed_size_bytes, 0)
            self.assertTrue(out.exists())


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


if __name__ == "__main__":
    unittest.main()
