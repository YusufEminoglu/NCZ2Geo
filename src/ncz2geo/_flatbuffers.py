# -*- coding: utf-8 -*-
"""Minimal FlatBuffers encoder for the FlatGeobuf writer.

Only what FlatGeobuf needs: tables with scalar, string, scalar-vector,
table and table-vector fields. Objects are laid out front to back (vtable,
table, then children), so every ``uoffset`` points forward as the format
requires, and every scalar is aligned to its own size relative to the buffer
start, which is what the FlatBuffers verifier in GDAL checks.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Any

# Scalar field kinds: struct format and size.
SCALARS = {
    "bool": ("<B", 1),
    "u8": ("<B", 1),
    "u16": ("<H", 2),
    "i32": ("<i", 4),
    "u32": ("<I", 4),
    "u64": ("<Q", 8),
    "f64": ("<d", 8),
}


@dataclass
class Table:
    """A FlatBuffers table: ``fields`` maps field index to a typed value.

    A value is ``(kind, data)``: a scalar kind from :data:`SCALARS`, ``"str"``,
    ``"vec:<scalar kind>"`` (sequence of numbers), ``"bytes"`` (ubyte vector
    from a ``bytes`` object), ``"table"`` (a :class:`Table`) or ``"tables"``
    (sequence of :class:`Table`).
    """

    fields: dict[int, tuple[str, Any]]


class _Writer:
    """Front-to-back FlatBuffers byte writer with deferred child placement."""

    def __init__(self) -> None:
        self.buf = bytearray()

    def pad_to(self, alignment: int, extra: int = 0) -> None:
        """Pad so that ``len(buf) + extra`` is a multiple of ``alignment``."""
        while (len(self.buf) + extra) % alignment:
            self.buf.append(0)

    def patch_uoffset(self, at: int, target: int) -> None:
        """Store a forward uoffset at ``at`` that points to ``target``."""
        assert target > at, "FlatBuffers uoffsets must point forward"
        struct.pack_into("<I", self.buf, at, target - at)

    def write_table(self, table: Table) -> int:
        """Write a table (and, after it, its children); return the table position."""
        fields = sorted(table.fields.items())
        max_index = max((index for index, _ in fields), default=-1)
        vtable_size = 4 + 2 * (max_index + 1)

        # Inline layout: soffset first, then fields in descending size for compactness.
        def inline_size(kind: str) -> int:
            return SCALARS[kind][1] if kind in SCALARS else 4

        order = sorted(fields, key=lambda item: -inline_size(item[1][0]))
        table_align = max([4] + [inline_size(kind) for _, (kind, _) in fields])

        self.pad_to(2)
        vtable_pos = len(self.buf)
        self.buf.extend(b"\0" * vtable_size)
        self.pad_to(table_align)
        table_pos = len(self.buf)
        self.buf.extend(b"\0" * 4)  # soffset to vtable, patched below

        field_offsets: dict[int, int] = {}
        deferred: list[tuple[int, str, Any]] = []
        for index, (kind, value) in order:
            size = inline_size(kind)
            self.pad_to(size)
            field_offsets[index] = len(self.buf) - table_pos
            if kind in SCALARS:
                self.buf.extend(struct.pack(SCALARS[kind][0], value))
            else:
                deferred.append((len(self.buf), kind, value))
                self.buf.extend(b"\0" * 4)
        table_size = len(self.buf) - table_pos

        struct.pack_into("<i", self.buf, table_pos, table_pos - vtable_pos)
        struct.pack_into("<HH", self.buf, vtable_pos, vtable_size, table_size)
        for index, offset in field_offsets.items():
            struct.pack_into("<H", self.buf, vtable_pos + 4 + 2 * index, offset)

        for at, kind, value in deferred:
            self.patch_uoffset(at, self.write_child(kind, value))
        return table_pos

    def write_child(self, kind: str, value: Any) -> int:
        """Write a non-inline value and return the position its uoffset must target."""
        if kind == "table":
            return self.write_table(value)
        if kind == "str":
            data = value.encode("utf-8")
            self.pad_to(4)
            pos = len(self.buf)
            self.buf.extend(struct.pack("<I", len(data)) + data + b"\0")
            return pos
        if kind == "bytes":
            self.pad_to(4)
            pos = len(self.buf)
            self.buf.extend(struct.pack("<I", len(value)) + bytes(value))
            return pos
        if kind.startswith("vec:"):
            fmt, size = SCALARS[kind[4:]]
            self.pad_to(max(4, size), extra=4)  # element data aligned after the length
            pos = len(self.buf)
            self.buf.extend(struct.pack("<I", len(value)))
            for item in value:
                self.buf.extend(struct.pack(fmt, item))
            return pos
        if kind == "tables":
            self.pad_to(4)
            pos = len(self.buf)
            self.buf.extend(struct.pack("<I", len(value)))
            slots = []
            for _ in value:
                slots.append(len(self.buf))
                self.buf.extend(b"\0" * 4)
            for slot, child in zip(slots, value):
                self.patch_uoffset(slot, self.write_table(child))
            return pos
        raise ValueError(f"unsupported FlatBuffers field kind: {kind}")


def encode(root: Table) -> bytes:
    """Serialise ``root`` as a complete FlatBuffer (root uoffset first)."""
    writer = _Writer()
    writer.buf.extend(b"\0" * 4)
    writer.patch_uoffset(0, writer.write_table(root))
    writer.pad_to(8)
    return bytes(writer.buf)
