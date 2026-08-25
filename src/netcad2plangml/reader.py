"""High-level Netcad readers for netcad2plangml."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from .ncz_engine.model import (
    NetcadAttributeRow,
    NetcadAttributeTable,
    NetcadCoordinate,
    NetcadEntity,
    NetcadParseResult,
)
from .ncz_engine.v2 import PARSER_BACKEND_V2, NczCatalog
from .ncz_engine.v2 import cache as ncz_cache
from .ncz_engine.v2.parser import parse_file


class Netcad2PlanGmlError(RuntimeError):
    """Raised when a Netcad source cannot be read or classified."""


@dataclass(frozen=True)
class LayerSummary:
    """Cheap layer summary produced without fully decoding every geometry."""

    layer_code: int
    layer_name: str
    record_count: int = 0
    families: set[str] = field(default_factory=set)

    def to_dict(self) -> dict:
        return {
            "layer_code": self.layer_code,
            "layer_name": self.layer_name,
            "record_count": self.record_count,
            "families": sorted(self.families),
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "LayerSummary":
        return cls(
            layer_code=int(payload.get("layer_code", 0)),
            layer_name=str(payload.get("layer_name", "")),
            record_count=int(payload.get("record_count", 0)),
            families=set(payload.get("families", [])),
        )


class NetcadReader:
    """Catalog-backed reader for selective, layer-by-layer NCZ/NCA decoding."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.backend = ""
        self.from_cache = False
        self._catalog: NczCatalog | None = None
        self._metadata = None
        self._summaries: list[LayerSummary] = []
        self._attribute_tables: list[dict] = []

    def index(self) -> "NetcadReader":
        """Scan metadata and layer summaries without decoding full geometry."""
        if not self.path.exists():
            raise FileNotFoundError(str(self.path))
        cached = ncz_cache.load(str(self.path))
        if cached is not None:
            self._metadata = cached["metadata"]
            self._summaries = [LayerSummary.from_dict(item) for item in cached["summaries"]]
            self._attribute_tables = list(cached.get("attribute_tables", []))
            self.backend = PARSER_BACKEND_V2
            self.from_cache = True
            return self

        data = self.path.read_bytes()
        catalog = NczCatalog(data).index()
        self._catalog = catalog
        self._metadata = catalog.metadata
        self._summaries = [
            LayerSummary(
                layer_code=summary.layer_code,
                layer_name=summary.layer_name,
                record_count=summary.record_count,
                families=set(summary.families),
            )
            for summary in catalog.layer_catalog()
        ]
        self._attribute_tables = catalog.decode_attribute_tables()
        self.backend = PARSER_BACKEND_V2
        ncz_cache.save(
            str(self.path),
            catalog.metadata,
            [summary.to_dict() for summary in self._summaries],
            self._attribute_tables,
        )
        return self

    @property
    def version_name(self) -> str:
        self._ensure_indexed()
        return str(getattr(self._metadata, "version_name", ""))

    @property
    def epsg(self) -> str:
        self._ensure_indexed()
        return str(getattr(self._metadata, "epsg", ""))

    @property
    def projection_text(self) -> str:
        self._ensure_indexed()
        return str(getattr(self._metadata, "projection_text", ""))

    def layer_summaries(self) -> list[LayerSummary]:
        self._ensure_indexed()
        return list(self._summaries)

    def attribute_tables(self) -> list[NetcadAttributeTable]:
        self._ensure_indexed()
        return [_attribute_table_from_dict(item) for item in self._attribute_tables]

    def decode_layers(self, layer_codes: Iterable[int]) -> list[NetcadEntity]:
        self._ensure_indexed()
        codes = [int(code) for code in layer_codes]
        if not codes:
            return []
        if self._catalog is None:
            self._catalog = NczCatalog(self.path.read_bytes()).index()
        return [_entity_from_dict(item) for item in self._catalog.decode_layers(codes)]

    def parse(self) -> NetcadParseResult:
        """Fully decode the source drawing."""
        return _result_from_payload(parse_file(str(self.path)))

    def _ensure_indexed(self) -> None:
        if not self.backend:
            self.index()


def inspect_source(path: str | Path) -> list[LayerSummary]:
    """Return a lightweight NCZ/NCA layer catalog for *path*."""
    return NetcadReader(path).index().layer_summaries()


def parse_netcad(path: str | Path) -> NetcadParseResult:
    """Fully parse a Netcad NCZ/NCA drawing into stable dataclasses."""
    return NetcadReader(path).parse()


def _result_from_payload(payload: dict) -> NetcadParseResult:
    return NetcadParseResult(
        entities=[_entity_from_dict(item) for item in payload.get("entities", [])],
        attribute_tables=[
            _attribute_table_from_dict(item)
            for item in payload.get("attribute_tables", [])
        ],
        layer_names=list(payload.get("layer_names", [])),
        layer_colors=list(payload.get("layer_colors", [])),
        parser_backend=str(payload.get("parser_backend", "")),
        version_name=str(payload.get("version_name", "")),
        epsg=str(payload.get("epsg", "")),
        projection_text=str(payload.get("projection_text", "")),
        unsupported_geometry_types={
            int(key): int(value)
            for key, value in dict(payload.get("unsupported_geometry_types", {})).items()
        },
    )


def _entity_from_dict(payload: dict) -> NetcadEntity:
    return NetcadEntity(
        geometry_kind=str(payload.get("geometry_kind", "")),
        layer_code=int(payload.get("layer_code", 0)),
        layer_name=str(payload.get("layer_name", "")),
        color_argb=payload.get("color_argb"),
        name=str(payload.get("name", "")),
        label_text=str(payload.get("label_text", "")),
        text_height=float(payload.get("text_height", 0.0)),
        rotation_degrees=float(payload.get("rotation_degrees", 0.0)),
        box_width=float(payload.get("box_width", 0.0)),
        box_height=float(payload.get("box_height", 0.0)),
        scale=float(payload.get("scale", 0.0)),
        grid_x=float(payload.get("grid_x", 0.0)),
        grid_y=float(payload.get("grid_y", 0.0)),
        radius=float(payload.get("radius", 0.0)),
        start_angle=float(payload.get("start_angle", 0.0)),
        end_angle=float(payload.get("end_angle", 0.0)),
        is_closed=bool(payload.get("is_closed", False)),
        coordinates=[
            NetcadCoordinate(
                x=float(coord.get("x", 0.0)),
                y=float(coord.get("y", 0.0)),
                z=float(coord.get("z", 0.0)),
            )
            for coord in payload.get("coordinates", [])
        ],
    )


def _attribute_table_from_dict(payload: dict) -> NetcadAttributeTable:
    return NetcadAttributeTable(
        table_ref=str(payload.get("table_ref", "")),
        rows=[
            NetcadAttributeRow(
                row_index=int(item.get("row_index", 0)),
                columns=dict(item.get("columns", {})),
            )
            for item in payload.get("rows", [])
        ],
    )
