# -*- coding: utf-8 -*-
"""Minimal pure-Python Apache Parquet writer for the GeoParquet exporter.

Writes one row group with one uncompressed, PLAIN-encoded data page (v1) per
column. Nullable columns carry RLE/bit-packed definition levels. File and
page metadata use the Thrift compact protocol, as the Parquet format requires.
This is enough for any Parquet reader (Arrow, GDAL, DuckDB, pandas) to open
the file; it deliberately skips compression, dictionaries and statistics.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Any, Optional, Sequence

# Parquet physical types.
BOOLEAN, INT64, DOUBLE, BYTE_ARRAY = 0, 2, 5, 6
_REQUIRED, _OPTIONAL = 0, 1
_PLAIN, _RLE = 0, 3

# Thrift compact protocol type ids.
_T_TRUE, _T_FALSE, _T_I32, _T_I64, _T_BINARY, _T_LIST, _T_STRUCT = 1, 2, 5, 6, 8, 9, 12


class _Thrift:
    """Thrift compact-protocol encoder for nested structs."""

    def __init__(self) -> None:
        self.out = bytearray()
        self._last: list[int] = [0]

    def _varint(self, value: int) -> None:
        while True:
            byte = value & 0x7F
            value >>= 7
            if value:
                self.out.append(byte | 0x80)
            else:
                self.out.append(byte)
                return

    def _zigzag(self, value: int) -> None:
        self._varint((value << 1) ^ (value >> 63))

    def _field(self, field_id: int, type_id: int) -> None:
        delta = field_id - self._last[-1]
        if 0 < delta <= 15:
            self.out.append((delta << 4) | type_id)
        else:
            self.out.append(type_id)
            self._zigzag(field_id)
        self._last[-1] = field_id

    def i32(self, field_id: int, value: int) -> None:
        """Write an i32 field."""
        self._field(field_id, _T_I32)
        self._zigzag(value)

    def i64(self, field_id: int, value: int) -> None:
        """Write an i64 field."""
        self._field(field_id, _T_I64)
        self._zigzag(value)

    def boolean(self, field_id: int, value: bool) -> None:
        """Write a bool field (the value lives in the field header)."""
        self._field(field_id, _T_TRUE if value else _T_FALSE)

    def binary(self, field_id: int, value: bytes) -> None:
        """Write a binary/string field."""
        self._field(field_id, _T_BINARY)
        self._varint(len(value))
        self.out.extend(value)

    def string(self, field_id: int, value: str) -> None:
        """Write a UTF-8 string field."""
        self.binary(field_id, value.encode("utf-8"))

    def begin_struct(self, field_id: Optional[int] = None) -> None:
        """Open a nested struct (as a field, or as a list element when ``field_id`` is None)."""
        if field_id is not None:
            self._field(field_id, _T_STRUCT)
        self._last.append(0)

    def end_struct(self) -> None:
        """Close the innermost struct with a stop byte."""
        self.out.append(0)
        self._last.pop()

    def list_header(self, field_id: int, elem_type: int, size: int) -> None:
        """Write a list field header; the caller then writes ``size`` elements."""
        self._field(field_id, _T_LIST)
        if size < 15:
            self.out.append((size << 4) | elem_type)
        else:
            self.out.append(0xF0 | elem_type)
            self._varint(size)

    def list_i32(self, field_id: int, values: Sequence[int]) -> None:
        """Write a list<i32> field."""
        self.list_header(field_id, _T_I32, len(values))
        for value in values:
            self._zigzag(value)

    def list_string(self, field_id: int, values: Sequence[str]) -> None:
        """Write a list<string> field."""
        self.list_header(field_id, _T_BINARY, len(values))
        for value in values:
            data = value.encode("utf-8")
            self._varint(len(data))
            self.out.extend(data)


@dataclass
class Column:
    """One Parquet column: name, physical type, nullability, values and UTF-8 flag."""

    name: str
    physical_type: int
    values: Sequence[Any]
    nullable: bool = True
    utf8: bool = False


def _definition_levels(values: Sequence[Any]) -> bytes:
    """RLE/bit-packed hybrid encoding of 1-bit definition levels, length-prefixed."""
    bits = [0 if v is None else 1 for v in values]
    groups = (len(bits) + 7) // 8
    body = bytearray()
    header = (groups << 1) | 1  # bit-packed run of `groups` groups of 8 values
    while True:
        byte = header & 0x7F
        header >>= 7
        body.append(byte | (0x80 if header else 0))
        if not header:
            break
    for g in range(groups):
        byte = 0
        for i, bit in enumerate(bits[g * 8 : g * 8 + 8]):
            byte |= bit << i
        body.append(byte)
    return struct.pack("<I", len(body)) + bytes(body)


def _plain(column: Column) -> bytes:
    """PLAIN-encode the non-null values of a column."""
    present = [v for v in column.values if v is not None]
    if column.physical_type == INT64:
        return struct.pack(f"<{len(present)}q", *present)
    if column.physical_type == DOUBLE:
        return struct.pack(f"<{len(present)}d", *present)
    if column.physical_type == BOOLEAN:
        out = bytearray((len(present) + 7) // 8)
        for i, value in enumerate(present):
            if value:
                out[i // 8] |= 1 << (i % 8)
        return bytes(out)
    out = bytearray()
    for value in present:
        data = value.encode("utf-8") if isinstance(value, str) else bytes(value)
        out.extend(struct.pack("<I", len(data)) + data)
    return bytes(out)


def _page_header(num_values: int, size: int) -> bytes:
    """Thrift-encode a DATA_PAGE header for an uncompressed page of ``size`` bytes."""
    t = _Thrift()
    t.i32(1, 0)  # type = DATA_PAGE
    t.i32(2, size)  # uncompressed_page_size
    t.i32(3, size)  # compressed_page_size
    t.begin_struct(5)  # data_page_header
    t.i32(1, num_values)
    t.i32(2, _PLAIN)
    t.i32(3, _RLE)  # definition levels
    t.i32(4, _RLE)  # repetition levels
    t.end_struct()
    t.out.append(0)  # end PageHeader
    return bytes(t.out)


def write_parquet(path: str, columns: Sequence[Column], key_value_metadata: dict[str, str]) -> None:
    """Write ``columns`` (equal length) as a single-row-group Parquet file."""
    num_rows = len(columns[0].values) if columns else 0
    if any(len(c.values) != num_rows for c in columns):
        raise ValueError("all Parquet columns must have the same number of rows")

    body = bytearray(b"PAR1")
    chunks: list[tuple[Column, int, int]] = []  # column, page offset, total size
    for column in columns:
        page = (_definition_levels(column.values) if column.nullable else b"") + _plain(column)
        header = _page_header(num_rows, len(page))
        offset = len(body)
        body.extend(header + page)
        chunks.append((column, offset, len(header) + len(page)))

    t = _Thrift()
    t.i32(1, 1)  # version
    t.list_header(2, _T_STRUCT, len(columns) + 1)  # schema
    t.begin_struct()
    t.string(4, "schema")
    t.i32(5, len(columns))
    t.end_struct()
    for column in columns:
        t.begin_struct()
        t.i32(1, column.physical_type)
        t.i32(3, _OPTIONAL if column.nullable else _REQUIRED)
        t.string(4, column.name)
        if column.utf8:
            t.i32(6, 0)  # converted_type = UTF8
            t.begin_struct(10)  # logicalType (union)
            t.begin_struct(1)  # STRING
            t.end_struct()
            t.end_struct()
        t.end_struct()
    t.i64(3, num_rows)
    t.list_header(4, _T_STRUCT, 1)  # row_groups
    t.begin_struct()
    t.list_header(1, _T_STRUCT, len(chunks))  # columns
    for column, offset, size in chunks:
        t.begin_struct()
        t.i64(2, offset)  # file_offset
        t.begin_struct(3)  # meta_data
        t.i32(1, column.physical_type)
        t.list_i32(2, [_PLAIN, _RLE])
        t.list_string(3, [column.name])
        t.i32(4, 0)  # codec = UNCOMPRESSED
        t.i64(5, num_rows)
        t.i64(6, size)
        t.i64(7, size)
        t.i64(9, offset)  # data_page_offset
        t.end_struct()
        t.end_struct()
    t.i64(2, sum(size for _, _, size in chunks))
    t.i64(3, num_rows)
    t.end_struct()
    t.list_header(5, _T_STRUCT, len(key_value_metadata))
    for key, value in key_value_metadata.items():
        t.begin_struct()
        t.string(1, key)
        t.string(2, value)
        t.end_struct()
    t.string(6, "ncz2geo")  # created_by
    t.out.append(0)  # end FileMetaData

    footer = bytes(t.out)
    with open(path, "wb") as handle:
        handle.write(bytes(body))
        handle.write(footer)
        handle.write(struct.pack("<I", len(footer)))
        handle.write(b"PAR1")
