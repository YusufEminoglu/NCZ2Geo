# -*- coding: utf-8 -*-
# Copyright (C) 2026 Yusuf Eminoğlu
# SPDX-License-Identifier: GPL-2.0-or-later
"""Edge cases and regressions for the NCZ Engine v2 blocks, attributes and cache."""

from __future__ import annotations

import json
import os
import struct
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ncz2geo.ncz_engine.v2 import cache
from ncz2geo.ncz_engine.v2.attributes import (
    decode_attribute_row,
    decode_attribute_tables,
    find_attribute_markers,
)
from ncz2geo.ncz_engine.v2.binary import Cursor
from ncz2geo.ncz_engine.v2.blocks import DrawingMetadata
from ncz2geo.ncz_engine.v2.geometry import (
    GeometryRecord,
    decode_compressed_curve,
    decode_map_sheet,
    decode_symbol,
    decode_text,
    decode_triangle,
)
from ncz2geo.ncz_engine.v2.parser import NczCatalog, parse_bytes
from tests import ncz_fixtures as fx


def _polyline(offsets: list[tuple[float, float]]) -> bytes:
    """A kind-21 polyline block whose vertices are offsets from the base point."""
    size = 113 + len(offsets) * 24
    body = bytearray(size - 4)
    body[1] = 7  # geometry type (absolute offset 6)
    body[2] = 1  # layer code
    for index, (dx, dy) in enumerate(offsets):
        struct.pack_into("<ddd", body, 113 + index * 24 - 5, fx.BASE_X + dx, fx.BASE_Y + dy, 0.0)
    return fx.block(21, bytes(body))


class TestBinaryCursor(unittest.TestCase):
    def test_out_of_range_reads_return_neutral_values(self) -> None:
        cursor = Cursor(b"\x01\x02\x03")
        self.assertEqual(cursor.u8(-1), 0)
        self.assertEqual(cursor.u8(3), 0)
        self.assertEqual(cursor.u16(2), 0)
        self.assertEqual(cursor.u32(0), 0)
        self.assertEqual(cursor.f32(0), 0.0)
        self.assertEqual(cursor.f64(0), 0.0)
        self.assertEqual(cursor.raw(5, 2), b"")
        self.assertEqual(cursor.raw(1, 0), b"")
        self.assertEqual(cursor.raw(1, 10), b"\x02\x03")

    def test_length_prefixed_text_bounds(self) -> None:
        cursor = Cursor(b"\x05AB")
        self.assertEqual(cursor.length_prefixed_text(0, 1), "")  # runs past the buffer
        self.assertEqual(cursor.length_prefixed_text(9, 1), "")
        self.assertEqual(Cursor(b"\x00AB").length_prefixed_text(0, 1), "")
        self.assertEqual(Cursor(b"\x02AB").length_prefixed_text(0, 1), "AB")

    def test_positive_f32_rejects_out_of_band_values(self) -> None:
        self.assertIsNone(Cursor(struct.pack("<f", -1.0)).positive_f32(0))
        self.assertIsNone(Cursor(struct.pack("<f", 2e5)).positive_f32(0))
        self.assertIsNone(Cursor(b"\x00").positive_f32(0))
        self.assertEqual(Cursor(struct.pack("<f", 2.5)).positive_f32(0), 2.5)


class TestBlocksAndMetadata(unittest.TestCase):
    def test_layer_lookup_is_zero_and_one_based_tolerant(self) -> None:
        metadata = DrawingMetadata(layer_names=["A", "B"], layer_colors=[0xFF000001, 0xFF102030])
        self.assertEqual(metadata.layer_name(0), "A")
        self.assertEqual(metadata.layer_name(2), "B")
        self.assertEqual(metadata.layer_name(9), "")
        # Near-black-blue producer quirk normalizes to pure black.
        self.assertEqual(metadata.layer_color(0), 0xFF000000)
        self.assertIsNone(metadata.layer_color(9))
        self.assertEqual(metadata.resolve_color(0, 1), 0xFF0000FF)
        self.assertEqual(metadata.resolve_color(0, 255), 0xFFFF0000)
        self.assertIsNone(metadata.resolve_color(0, 7))
        self.assertEqual(metadata.resolve_color(1, 0), 0xFF102030)

    def test_metadata_round_trips_through_dict(self) -> None:
        metadata = DrawingMetadata(["A"], [1], "v", "p", "EPSG:1")
        self.assertEqual(DrawingMetadata.from_dict(metadata.to_dict()), metadata)

    def test_embedded_record_ending_at_container_end_is_indexed(self) -> None:
        # Regression: a nested record that fills the container exactly to its
        # last byte used to be skipped by an off-by-one bound.
        inner = bytearray(fx.point_block(layer=2, name=b"NESTED"))
        inner[5] = inner[6]
        container = fx.block(0, bytes(5) + bytes(inner))
        catalog = NczCatalog(container).index()
        self.assertEqual(len(catalog.records), 1)
        entities = catalog.decode_all()
        self.assertEqual(entities[0]["name"], "NESTED")

    def test_unterminated_epsg_value_stays_inside_its_block(self) -> None:
        # Regression: without a closing ">" the EPSG reader ran on to the end
        # of the file, returning NUL padding and the next blocks' bytes.
        body = bytearray(64)
        body[0] = 9
        body[1:10] = b"TILED_XML"
        marker = b'SRS:"EPSG:5254"'
        body[19 : 19 + len(marker)] = marker
        data = fx.block(28, bytes(body)) + fx.version_block(b"VERSION-X")
        payload = parse_bytes(data)
        self.assertEqual(payload["epsg"], "EPSG:5254")
        self.assertEqual(payload["version_name"], "VERSION-X")

    def test_terminated_epsg_value(self) -> None:
        self.assertEqual(parse_bytes(fx.epsg_block())["epsg"], "EPSG:5254")


class TestAttributes(unittest.TestCase):
    def test_tab_without_digits_is_not_a_marker(self) -> None:
        # Regression: "@TAB" not followed by digits (e.g. text "@TABLE")
        # created a bogus table and truncated the preceding real record.
        record = fx.attribute_table_block()
        data = record + b"see @TABLE notes" + bytes(40)
        markers = find_attribute_markers(Cursor(data))
        self.assertEqual([marker.table_ref for marker in markers], ["@TAB1"])
        tables = decode_attribute_tables(Cursor(data))
        self.assertEqual([table["table_ref"] for table in tables], ["@TAB1"])
        self.assertEqual(tables[0]["rows"][0]["columns"]["record_length"], len(data))

    def test_segment_row_variant(self) -> None:
        chunk = bytearray(130)
        for offset in (17, 45, 87):
            struct.pack_into("<dd", chunk, offset, fx.BASE_X, fx.BASE_Y)
        row = decode_attribute_row(bytes(chunk), "@TAB2", 1)
        self.assertEqual(row["columns"]["row_variant"], "segment")
        self.assertEqual(row["columns"]["coord_1_x"], fx.BASE_X)

    def test_unknown_row_variant_exposes_ascii_fields(self) -> None:
        chunk = b"\x05@TAB3" + bytes(30) + b"\x04ABCD\x05@TAB3\x04ABCD"
        row = decode_attribute_row(chunk, "@TAB3", 1)
        self.assertEqual(row["columns"]["row_variant"], "unknown")
        self.assertEqual(row["columns"]["ascii_values"], "ABCD")

    def test_no_markers(self) -> None:
        self.assertEqual(decode_attribute_tables(Cursor(b"nothing here")), [])


class TestGeometryEdges(unittest.TestCase):
    def test_open_polyline_has_no_rectangle_metrics(self) -> None:
        # Regression: an open "U" whose cyclic vertex list reduces to four
        # corners was reported with box width/height and a rotation.
        entity = parse_bytes(_polyline([(0, 0), (10, 0), (10, 5), (0, 5), (0, 2)]))["entities"][0]
        self.assertEqual(entity["geometry_kind"], "Polyline")
        self.assertEqual(
            (entity["box_width"], entity["box_height"], entity["rotation_degrees"]),
            (0.0, 0.0, 0.0),
        )

    def test_closed_rectangle_keeps_metrics(self) -> None:
        entity = parse_bytes(_polyline([(0, 0), (10, 0), (10, 5), (0, 5), (0, 0)]))["entities"][0]
        self.assertEqual(entity["geometry_kind"], "Polygon")
        self.assertAlmostEqual(entity["box_width"], 10.0)
        self.assertAlmostEqual(entity["box_height"], 5.0)

    def test_ring_closed_by_small_gap_and_collinear_vertices(self) -> None:
        offsets = [(0, 0), (5, 0), (10, 0), (10, 5), (0, 5), (0, 0.01)]
        entity = parse_bytes(_polyline(offsets))["entities"][0]
        self.assertTrue(entity["is_closed"])
        self.assertEqual(entity["coordinates"][0], entity["coordinates"][-1])
        self.assertAlmostEqual(entity["box_width"], 10.0, places=1)

    def test_degenerate_records_yield_nothing(self) -> None:
        empty = GeometryRecord(Cursor(bytes(200)), 0, 199, 0)
        self.assertIsNone(decode_map_sheet(empty))
        self.assertIsNone(decode_triangle(empty))
        # Text needs a payload: a valid origin alone is not enough.
        buffer = bytearray(200)
        struct.pack_into("<dd", buffer, 8, fx.BASE_Y, fx.BASE_X)
        self.assertIsNone(decode_text(GeometryRecord(Cursor(bytes(buffer)), 0, 199, 0)))

    def test_symbol_defaults_size_when_missing(self) -> None:
        buffer = bytearray(200)
        struct.pack_into("<dd", buffer, 8, fx.BASE_Y, fx.BASE_X)
        buffer[94] = 3
        entity = decode_symbol(GeometryRecord(Cursor(bytes(buffer)), 0, 199, 0))
        assert entity is not None
        self.assertEqual(entity["text_height"], 5.0)
        self.assertEqual(entity["label_text"], "S3")

    def test_compressed_curve_skips_repeated_vertices(self) -> None:
        buffer = bytearray(122 + 2 * 18 + 8)  # exactly three delta slots
        struct.pack_into("<dd", buffer, 8, fx.BASE_Y, fx.BASE_X)
        for index, delta in enumerate([(0.0, 0.0), (0.0, 0.0), (5.0, 5.0)]):
            struct.pack_into("<ff", buffer, 122 + index * 18, *delta)
        record = GeometryRecord(Cursor(bytes(buffer)), 0, len(buffer) - 1, 0)
        entity = decode_compressed_curve(record)
        assert entity is not None
        self.assertEqual(len(entity["coordinates"]), 2)


class TestCache(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        env = {"LOCALAPPDATA": str(self.root / "cache")}
        self._env = mock.patch.dict(os.environ, env)
        self._env.start()
        os.environ.pop(cache._DISABLE_ENV, None)
        self.source = self.root / "drawing.ncz"
        self.source.write_bytes(fx.full_drawing())

    def tearDown(self) -> None:
        self._env.stop()
        self._tmp.cleanup()

    def _write_cache(self, payload: object) -> None:
        target = cache._cache_file(str(self.source))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload), encoding="utf-8")

    def _valid_payload(self) -> dict:
        return {
            "cache_version": cache.CACHE_VERSION,
            "fingerprint": cache.fingerprint(str(self.source)),
            "metadata": DrawingMetadata().to_dict(),
            "summaries": [],
            "attribute_tables": [],
        }

    def test_round_trip_and_clear(self) -> None:
        metadata = DrawingMetadata(layer_names=["A"])
        cache.save(str(self.source), metadata, [{"layer_code": 1}], [{"table_ref": "@TAB1"}])
        loaded = cache.load(str(self.source))
        assert loaded is not None
        self.assertEqual(loaded["metadata"], metadata)
        self.assertEqual(loaded["summaries"], [{"layer_code": 1}])
        self.assertEqual(cache.clear(), 1)
        self.assertIsNone(cache.load(str(self.source)))

    def test_disabled_and_missing_source(self) -> None:
        with mock.patch.dict(os.environ, {cache._DISABLE_ENV: "1"}):
            cache.save(str(self.source), DrawingMetadata(), [], [])
            self.assertIsNone(cache.load(str(self.source)))
        self.assertIsNone(cache.load(str(self.root / "missing.ncz")))
        cache.save(str(self.root / "missing.ncz"), DrawingMetadata(), [], [])
        self.assertEqual(cache.clear(), 0)

    def test_stale_fingerprint_is_a_miss(self) -> None:
        payload = self._valid_payload()
        payload["fingerprint"] = {"size": -1, "mtime_ns": 0}
        self._write_cache(payload)
        self.assertIsNone(cache.load(str(self.source)))

    def test_malformed_cache_files_are_misses_not_crashes(self) -> None:
        # Regression: a well-formed JSON document of the wrong shape raised
        # AttributeError (or reached the reader as non-dict summaries)
        # instead of being treated as a cache miss.
        bad_metadata = self._valid_payload()
        bad_metadata["metadata"] = [1]
        bad_summaries = self._valid_payload()
        bad_summaries["summaries"] = [1]
        bad_tables = self._valid_payload()
        bad_tables["attribute_tables"] = "x"
        for payload in ([1, 2], "text", bad_metadata, bad_summaries, bad_tables):
            with self.subTest(payload=payload):
                self._write_cache(payload)
                self.assertIsNone(cache.load(str(self.source)))
        self._write_cache(self._valid_payload())
        self.assertIsNotNone(cache.load(str(self.source)))

    def test_failed_save_leaves_no_temp_file(self) -> None:
        # Regression: a payload json could not serialize left an orphaned
        # *.json.tmp that clear() (which globs *.json) never removes.
        cache.save(str(self.source), DrawingMetadata(), [{"families": {"A"}}], [])
        leftovers = list(cache._cache_root().iterdir()) if cache._cache_root().exists() else []
        self.assertEqual(leftovers, [])
        self.assertIsNone(cache.load(str(self.source)))


if __name__ == "__main__":
    unittest.main()
