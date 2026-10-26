# -*- coding: utf-8 -*-
# Copyright (C) 2026 Yusuf Eminoğlu
# SPDX-License-Identifier: GPL-2.0-or-later
"""Structural tests for the binary exporters (FlatGeobuf, GeoParquet, GeoPackage,
Shapefile, DXF, KML) and the bundled CRS / projection support.

The files are read back with small independent parsers (no GDAL needed), so the
tests check what other software will see. They were also validated against
GDAL 3.13 (ogrinfo/ogr2ogr, validate_gpkg.py), pyarrow and DuckDB.
"""

from __future__ import annotations

import json
import math
import sqlite3
import struct
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile
from contextlib import closing
from pathlib import Path

from ncz2geo import (
    export_entities_to_dxf,
    export_entities_to_flatgeobuf,
    export_entities_to_geopackage,
    export_entities_to_geoparquet,
    export_entities_to_shapefile,
    export_to_kml_kmz,
    supported_epsg_codes,
    write_geojson,
)
from ncz2geo._crs import esri_wkt, ogc_wkt, parse_epsg, projjson
from ncz2geo._feature_table import build_feature_table
from ncz2geo._projection import to_wgs84
from ncz2geo.cli import main as cli_main
from ncz2geo.ncz_engine.model import NetcadCoordinate as C
from ncz2geo.ncz_engine.model import NetcadEntity
from ncz2geo.shapefile_writer import dbf_field_names

from . import ncz_fixtures


def tricky_entities(n: int = 9) -> list[NetcadEntity]:
    """Points with Z, lines and polygons, Turkish names and nulls in several columns."""
    entities = []
    for i in range(n):
        kind = i % 3
        if kind == 0:
            coords = [C(500000 + i, 4500000 + i, 12.5 + i)]
        elif kind == 1:
            coords = [
                C(500000 + i, 4500000, 1.0),
                C(500010 + i, 4500005, 2.0),
                C(500020 + i, 4500000, 0.0),
            ]
        else:
            coords = [
                C(500000 + i, 4500000),
                C(500010 + i, 4500000),
                C(500010 + i, 4500010),
                C(500000 + i, 4500010),
            ]
        entities.append(
            NetcadEntity(
                geometry_kind=("Point", "Polyline", "Polygon")[kind],
                layer_code=i,
                layer_name=("YOL", "İMAR_ADASI", "ŞEVLİ ÇİZGİ")[kind],
                color_argb=None if i % 2 else 0xFF00FF00,
                label_text="Ğüşıöç" if i % 4 == 0 else "",
                is_closed=kind == 2,
                rotation_degrees=1.5 * i,
                coordinates=coords,
            )
        )
    return entities


class _FlatBuffer:
    """Tiny FlatBuffers table reader used to inspect FlatGeobuf output."""

    def __init__(self, buf: bytes, pos: int | None = None) -> None:
        self.buf = buf
        self.pos = struct.unpack_from("<I", buf, 0)[0] if pos is None else pos
        vtable = self.pos - struct.unpack_from("<i", buf, self.pos)[0]
        size = struct.unpack_from("<H", buf, vtable)[0]
        self.offsets = [
            struct.unpack_from("<H", buf, vtable + 4 + 2 * i)[0] for i in range((size - 4) // 2)
        ]

    def _at(self, field: int) -> int | None:
        if field >= len(self.offsets) or not self.offsets[field]:
            return None
        return self.pos + self.offsets[field]

    def scalar(self, field: int, fmt: str, default: object = None) -> object:
        at = self._at(field)
        assert at is None or at % struct.calcsize(fmt) == 0, "misaligned scalar"
        return default if at is None else struct.unpack_from(fmt, self.buf, at)[0]

    def _target(self, field: int) -> int | None:
        at = self._at(field)
        return None if at is None else at + struct.unpack_from("<I", self.buf, at)[0]

    def string(self, field: int) -> str | None:
        at = self._target(field)
        if at is None:
            return None
        length = struct.unpack_from("<I", self.buf, at)[0]
        return self.buf[at + 4 : at + 4 + length].decode("utf-8")

    def vector(self, field: int, fmt: str) -> list:
        at = self._target(field)
        if at is None:
            return []
        length = struct.unpack_from("<I", self.buf, at)[0]
        assert (at + 4) % struct.calcsize(fmt) == 0, "misaligned vector"
        return list(struct.unpack_from(f"<{length}{fmt}", self.buf, at + 4))

    def table(self, field: int) -> "_FlatBuffer | None":
        at = self._target(field)
        return None if at is None else _FlatBuffer(self.buf, at)

    def tables(self, field: int) -> list["_FlatBuffer"]:
        at = self._target(field)
        if at is None:
            return []
        length = struct.unpack_from("<I", self.buf, at)[0]
        out = []
        for i in range(length):
            slot = at + 4 + 4 * i
            out.append(_FlatBuffer(self.buf, slot + struct.unpack_from("<I", self.buf, slot)[0]))
        return out


def _rtree_nodes(num_items: int, node_size: int = 16) -> int:
    """Node count of a packed R-tree, as the FlatGeobuf reference computes it."""
    n, total = num_items, num_items
    while True:
        n = (n + node_size - 1) // node_size
        total += n
        if n == 1:
            return total


class ExportTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.entities = tricky_entities(9)
        self.table = build_feature_table(self.entities)

    def tearDown(self) -> None:
        self._tmp.cleanup()


class TestFlatGeobuf(ExportTestCase):
    def _read(self, path: Path) -> tuple[_FlatBuffer, list[_FlatBuffer], bytes]:
        data = path.read_bytes()
        self.assertEqual(data[:8], b"fgb\x03fgb\x00")
        header_len = struct.unpack_from("<I", data, 8)[0]
        header = _FlatBuffer(data[12 : 12 + header_len])
        pos = 12 + header_len
        node_size = header.scalar(9, "<H", 16)
        count = header.scalar(8, "<Q", 0)
        index = b""
        if node_size and count:
            index = data[pos : pos + 40 * _rtree_nodes(count, node_size)]
            pos += len(index)
        features = []
        while pos < len(data):
            size = struct.unpack_from("<I", data, pos)[0]
            features.append(_FlatBuffer(data[pos + 4 : pos + 4 + size]))
            pos += 4 + size
        self.assertEqual(pos, len(data))
        return header, features, index

    def test_header_columns_crs_and_features(self) -> None:
        path = self.tmp / "plan.fgb"
        result = export_entities_to_flatgeobuf(self.entities, path, srid=5254)
        header, features, index = self._read(path)
        self.assertEqual(result.feature_count, 9)
        self.assertEqual(header.scalar(8, "<Q"), 9)
        self.assertEqual(header.scalar(2, "<B"), 0)  # mixed geometry types -> Unknown
        self.assertEqual(header.scalar(3, "<B"), 1)  # has_z
        self.assertEqual(
            [c.string(0) for c in header.tables(7)], [n for n, _ in self.table.columns]
        )
        crs = header.table(10)
        assert crs is not None
        self.assertEqual((crs.string(0), crs.scalar(1, "<i")), ("EPSG", 5254))
        self.assertEqual(len(features), 9)
        self.assertEqual(len(index), 40 * _rtree_nodes(9))

        # Every leaf offset points at a feature, and the root covers the extent.
        leaves = [struct.unpack_from("<ddddQ", index, len(index) - 40 * (9 - i)) for i in range(9)]
        self.assertEqual(leaves[0][4], 0)
        root = struct.unpack_from("<dddd", index, 0)
        self.assertEqual(root, tuple(header.vector(1, "d")))

        types = sorted(f.table(0).scalar(6, "<B") for f in features)  # type: ignore[union-attr]
        self.assertEqual(types, [1, 1, 1, 2, 2, 2, 3, 3, 3])

    def test_single_feature_gets_root_node(self) -> None:
        path = self.tmp / "one.fgb"
        export_entities_to_flatgeobuf(self.entities[:1], path)
        _, features, index = self._read(path)
        self.assertEqual(len(features), 1)
        self.assertEqual(len(index), 2 * 40)  # leaf + root, as GDAL expects

    def test_without_index_and_invalid_node_size(self) -> None:
        path = self.tmp / "noindex.fgb"
        export_entities_to_flatgeobuf(self.entities, path, srid=None, index_node_size=0)
        header, features, index = self._read(path)
        self.assertEqual(header.scalar(9, "<H"), 0)
        self.assertIsNone(header.table(10))
        self.assertEqual((len(features), index), (9, b""))
        with self.assertRaises(ValueError):
            export_entities_to_flatgeobuf(self.entities, path, index_node_size=8)

    def test_empty_export(self) -> None:
        path = self.tmp / "empty.fgb"
        result = export_entities_to_flatgeobuf([], path)
        header, features, _ = self._read(path)
        self.assertEqual((result.feature_count, header.scalar(8, "<Q", 0), features), (0, 0, []))


class TestGeoParquet(ExportTestCase):
    def test_parquet_container_and_geo_metadata(self) -> None:
        path = self.tmp / "plan.parquet"
        result = export_entities_to_geoparquet(self.entities, path, srid=5254)
        data = path.read_bytes()
        self.assertEqual((data[:4], data[-4:]), (b"PAR1", b"PAR1"))
        footer_len = struct.unpack_from("<I", data, len(data) - 8)[0]
        footer = data[len(data) - 8 - footer_len : len(data) - 8]
        self.assertIn(b"geo", footer)
        self.assertEqual(result.feature_count, 9)
        self.assertEqual(result.geoparquet_version, "1.1.0")

    def test_read_back_with_pyarrow(self) -> None:
        try:
            import pyarrow.parquet as pq
        except ImportError:
            self.skipTest("pyarrow not installed")
        path = self.tmp / "plan.parquet"
        export_entities_to_geoparquet(self.entities, path, srid=5254)
        table = pq.read_table(path)
        geo = json.loads(pq.read_metadata(path).metadata[b"geo"])
        column = geo["columns"]["geometry"]
        self.assertEqual(column["encoding"], "WKB")
        self.assertEqual(column["geometry_types"], ["Point Z", "LineString Z", "Polygon Z"])
        self.assertEqual(column["crs"]["id"], {"authority": "EPSG", "code": 5254})
        rows = table.to_pylist()
        self.assertEqual(len(rows), 9)
        self.assertEqual(rows[1]["layer_name"], "İMAR_ADASI")
        self.assertIsNone(rows[1]["color_argb"])
        self.assertEqual(rows[0]["label_text"], "Ğüşıöç")
        x, y, z = struct.unpack_from("<3d", rows[0]["geometry"], 5)
        self.assertEqual((x, y, z), (500000.0, 4500000.0, 12.5))

    def test_crs_rules(self) -> None:
        try:
            import pyarrow.parquet as pq
        except ImportError:
            self.skipTest("pyarrow not installed")
        for srid, expected in ((4326, "absent"), (9999, None)):
            path = self.tmp / f"crs{srid}.parquet"
            export_entities_to_geoparquet(self.entities, path, srid=srid)
            column = json.loads(pq.read_metadata(path).metadata[b"geo"])["columns"]["geometry"]
            self.assertEqual(column.get("crs", "absent"), expected)


class TestGeoPackage(ExportTestCase):
    def test_conformance_essentials(self) -> None:
        path = self.tmp / "plan.gpkg"
        result = export_entities_to_geopackage(self.entities, path, table_name="plan", srs_id=5254)
        self.assertEqual(result.total_features_written, 9)
        self.assertEqual(path.read_bytes()[68:72], b"GPKG")
        with closing(sqlite3.connect(path)) as conn:
            self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], 10200)
            srs = {
                row[0]: row[1]
                for row in conn.execute("SELECT srs_id, definition FROM gpkg_spatial_ref_sys")
            }
            self.assertTrue({-1, 0, 4326, 5254} <= set(srs))
            self.assertIn('AUTHORITY["EPSG","5254"]', srs[5254])
            self.assertEqual(
                conn.execute("SELECT geometry_type_name, z FROM gpkg_geometry_columns").fetchone(),
                ("GEOMETRY", 1),
            )
            self.assertEqual(conn.execute("SELECT count(*) FROM rtree_plan_geom").fetchone()[0], 9)
            triggers = {
                r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='trigger'")
            }
            self.assertEqual(len(triggers), 6)
            blob, name, area = conn.execute(
                "SELECT geom, layer_name, area_m2 FROM plan WHERE geometry_kind='Polygon' LIMIT 1"
            ).fetchone()
            self.assertEqual(blob[:2], b"GP")
            self.assertEqual(name, "ŞEVLİ ÇİZGİ")
            self.assertAlmostEqual(area, 100.0)
            kinds = [r[0] for r in conn.execute("SELECT geometry_kind FROM plan ORDER BY id")]
            self.assertEqual(kinds[:3], ["Point", "Polyline", "Polygon"])

    def test_undefined_srs(self) -> None:
        result = export_entities_to_geopackage(self.entities, self.tmp / "u.gpkg", srs_id=None)
        self.assertEqual(result.srs_id, -1)


class TestShapefile(ExportTestCase):
    def test_one_shapefile_per_geometry_type(self) -> None:
        result = export_entities_to_shapefile(self.entities, self.tmp / "plan.shp", srid=5254)
        self.assertEqual(result.feature_counts, {"Point": 3, "LineString": 3, "Polygon": 3})
        self.assertTrue(result.prj_written)
        expected_types = {"Point": 11, "LineString": 13, "Polygon": 15}
        for gtype, shp in result.shapefiles.items():
            data = Path(shp).read_bytes()
            code, length = (
                struct.unpack_from(">i", data, 0)[0],
                struct.unpack_from(">i", data, 24)[0],
            )
            self.assertEqual((code, length * 2), (9994, len(data)))
            self.assertEqual(struct.unpack_from("<i", data, 32)[0], expected_types[gtype])
            shx = Path(shp).with_suffix(".shx").read_bytes()
            self.assertEqual((len(shx) - 100) // 8, 3)
            self.assertEqual(Path(shp).with_suffix(".cpg").read_text(), "UTF-8")
            self.assertIn("TUREF_TM30", Path(shp).with_suffix(".prj").read_text())

        polygon = Path(result.shapefiles["Polygon"]).read_bytes()
        n_points = struct.unpack_from("<i", polygon, 100 + 8 + 40)[0]
        ring = [
            struct.unpack_from("<2d", polygon, 100 + 8 + 44 + 4 + 16 * i) for i in range(n_points)
        ]
        area = sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(ring, ring[1:]))
        self.assertLess(area, 0)  # exterior ring clockwise

    def test_dbf_names_and_values(self) -> None:
        result = export_entities_to_shapefile(self.entities, self.tmp / "plan", srid=None)
        self.assertFalse(result.prj_written)
        names = result.field_names
        self.assertTrue(all(len(v) <= 10 for v in names.values()))
        self.assertEqual(len({n.lower() for n in names.values()}), len(names))
        self.assertEqual(names["plangml_fonksiyon_adi"], "pg_fn_adi")
        dbf = Path(result.shapefiles["LineString"]).with_suffix(".dbf").read_bytes()
        self.assertEqual(struct.unpack_from("<I", dbf, 4)[0], 3)
        self.assertIn("İMAR_ADASI".encode("utf-8"), dbf)
        self.assertEqual(dbf[-1], 0x1A)

    def test_field_name_collisions(self) -> None:
        mapping = dbf_field_names(["abcdefghijk_1", "abcdefghijk_2", "plangml_extra_value"])
        self.assertEqual(mapping["abcdefghijk_1"], "abcdefghij")
        self.assertEqual(mapping["abcdefghijk_2"], "abcdefgh_1")
        self.assertEqual(mapping["plangml_extra_value"], "pg_extra_v")


class TestDxf(ExportTestCase):
    def test_r12_structure(self) -> None:
        path = self.tmp / "plan.dxf"
        result = export_entities_to_dxf(self.entities, path)
        text = path.read_bytes().decode("cp1254")
        pairs = text.split("\r\n")
        self.assertIn("AC1009", pairs)
        self.assertIn("ANSI_1254", pairs)
        self.assertEqual(result.entity_counts, {"POINT": 3, "POLYLINE": 6})
        self.assertEqual(pairs.count("POLYLINE"), 6)
        self.assertEqual(pairs.count("VERTEX"), 3 * 3 + 3 * 4)
        self.assertEqual(pairs.count("SEQEND"), 6)
        self.assertIn("İMAR_ADASI", pairs)
        self.assertIn("ŞEVLİ_ÇİZGİ", pairs)  # space is not allowed in R12 layer names
        self.assertEqual(pairs[-2:], ["EOF", ""])

    def test_text_entities(self) -> None:
        fixture = self.tmp / "plan.ncz"
        fixture.write_bytes(ncz_fixtures.full_drawing())
        from ncz2geo import parse_netcad

        result = export_entities_to_dxf(parse_netcad(fixture).entities, self.tmp / "fixture.dxf")
        self.assertEqual(result.entity_counts.get("TEXT"), 1)


class TestKml(ExportTestCase):
    def test_projected_plan_is_converted_to_wgs84(self) -> None:
        result = export_to_kml_kmz(self.entities, srid=5254)
        root = ET.fromstring(result.kml_string)
        ns = {"k": "http://www.opengis.net/kml/2.2"}
        points = root.findall(".//k:Point/k:coordinates", ns)
        self.assertEqual(len(points), 3)
        lon, lat, _ = map(float, points[0].text.split(","))  # type: ignore[union-attr]
        self.assertAlmostEqual(lon, 30.0, places=7)
        self.assertAlmostEqual(lat, 40.6346406788, places=7)
        self.assertEqual(len(root.findall(".//k:Polygon", ns)), 3)
        self.assertEqual(len(root.findall(".//k:LineString", ns)), 3)
        with zipfile.ZipFile(__import__("io").BytesIO(result.kmz_bytes)) as kmz:
            self.assertEqual(kmz.read("doc.kml").decode("utf-8"), result.kml_string)

    def test_projected_coordinates_require_srid(self) -> None:
        with self.assertRaises(ValueError):
            export_to_kml_kmz(self.entities)


class TestCrsAndProjection(unittest.TestCase):
    # Reference values from PROJ 9 (cs2cs --only-best ... EPSG:4326).
    VECTORS = [
        (5254, 500000.0, 4500000.0, 30.0, 40.6346406788),
        (5254, 455000.0, 4430000.0, 29.4730079185, 40.0030435076),
        (2320, 500000.0, 4500000.0, 29.9995849561, 40.6329649685),
        (32636, 500000.0, 4500000.0, 33.0, 40.6508565156),
        (23036, 500000.0, 4500000.0, 32.9996621336, 40.6491938868),
        (3857, 3339584.72, 4865942.28, 29.9999999659, 40.0000000034),
    ]

    def test_matches_proj_to_a_millimetre(self) -> None:
        for srid, x, y, lon, lat in self.VECTORS:
            got_lon, got_lat = to_wgs84(x, y, srid)
            error_m = math.hypot(
                (got_lon - lon) * 111320 * math.cos(math.radians(lat)), (got_lat - lat) * 110540
            )
            self.assertLess(error_m, 0.002, f"EPSG:{srid}")

    def test_bundled_definitions(self) -> None:
        codes = supported_epsg_codes()
        self.assertTrue({4326, 5254, 2320, 32636, 3857} <= set(codes))
        for code in codes:
            self.assertEqual(projjson(code)["id"]["code"], code)  # type: ignore[index]
            self.assertTrue(ogc_wkt(code).startswith(("PROJCS[", "GEOGCS[")))  # type: ignore[union-attr]
            self.assertTrue(esri_wkt(code))
        self.assertIsNone(projjson(9999))
        self.assertEqual(parse_epsg("EPSG:5254"), 5254)
        self.assertIsNone(parse_epsg(""))
        with self.assertRaises(ValueError):
            to_wgs84(1.0, 2.0, 9999)


class TestGeoJsonCrs(ExportTestCase):
    def test_crs_member_only_when_projected(self) -> None:
        projected = write_geojson(self.entities, self.tmp / "p.geojson", srid=5254)
        self.assertEqual(projected["crs"]["properties"]["name"], "urn:ogc:def:crs:EPSG::5254")
        on_disk = json.loads((self.tmp / "p.geojson").read_text(encoding="utf-8"))
        self.assertEqual(on_disk["crs"], projected["crs"])
        self.assertNotIn("crs", write_geojson(self.entities, self.tmp / "w.geojson", srid=4326))
        self.assertNotIn("crs", write_geojson(self.entities, self.tmp / "n.geojson"))


class TestCliConvert(unittest.TestCase):
    def test_every_extension(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "plan.ncz"
            source.write_bytes(ncz_fixtures.full_drawing())
            reference = write_geojson([], Path(tmp) / "empty.geojson")
            self.assertEqual(reference["features"], [])
            for ext in (".geojson", ".gpkg", ".fgb", ".parquet", ".shp", ".dxf", ".kml", ".kmz"):
                out = Path(tmp) / f"plan{ext}"
                self.assertEqual(cli_main(["convert", str(source), str(out)]), 0, ext)
                written = out if ext != ".shp" else Path(tmp) / "plan_points.shp"
                self.assertTrue(written.exists(), ext)
            self.assertEqual(cli_main(["convert", str(source), str(Path(tmp) / "plan.txt")]), 2)


if __name__ == "__main__":
    unittest.main()
