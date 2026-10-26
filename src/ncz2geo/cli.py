"""Command-line interface for NCZ2Geo."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from ._crs import parse_epsg
from .dxf_writer import export_entities_to_dxf
from .flatgeobuf_writer import export_entities_to_flatgeobuf
from .geojson import write_geojson
from .geopackage_writer import export_entities_to_geopackage
from .geoparquet_writer import export_entities_to_geoparquet
from .kml_kmz_exporter import export_to_kml_kmz
from .plangml import classify_layer
from .reader import NetcadReader
from .shapefile_writer import export_entities_to_shapefile


def build_parser() -> argparse.ArgumentParser:
    """Build the argparse command-line parser with all subcommands."""
    parser = argparse.ArgumentParser(
        prog="ncz2geo",
        description="Inspect Netcad NCZ/NCA files and export PlanGML-aware GeoJSON.",
    )
    parser.add_argument("--version", action="version", version=f"NCZ2Geo {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser(
        "inspect", help="List NCZ/NCA layers and PlanGML matches."
    )
    inspect_parser.add_argument("source", type=Path)
    inspect_parser.add_argument("--plan-type", default="UIP", choices=("UIP", "NIP", "CDP"))
    inspect_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")

    convert_parser = subparsers.add_parser(
        "convert",
        help="Convert an NCZ/NCA file; the output extension picks the format "
        "(.geojson, .gpkg, .fgb, .parquet, .shp, .dxf, .kml, .kmz).",
    )
    convert_parser.add_argument("source", type=Path)
    convert_parser.add_argument("output", type=Path)
    convert_parser.add_argument("--plan-type", default="UIP", choices=("UIP", "NIP", "CDP"))
    convert_parser.add_argument(
        "--layers",
        help="Comma-separated layer codes to decode; defaults to all layers.",
    )
    convert_parser.add_argument(
        "--srid",
        type=int,
        help="EPSG code of the drawing coordinates; defaults to the code stored in the drawing.",
    )

    val_parser = subparsers.add_parser("validate", help="Validate PlanGML and e-Plan compliance.")
    val_parser.add_argument("source", type=Path)
    val_parser.add_argument("--plan-type", choices=("UIP", "NIP", "CDP"))
    val_parser.add_argument("--json", action="store_true", help="Output validation report as JSON.")
    val_parser.add_argument(
        "--markdown", action="store_true", help="Output validation report as Markdown."
    )

    style_parser = subparsers.add_parser(
        "style", help="Generate OGC SLD, QGIS QML, or Mapbox GL styles."
    )
    style_parser.add_argument("source", type=Path)
    style_parser.add_argument("--format", choices=("sld", "qml", "mapbox", "all"), default="all")
    style_parser.add_argument("--out-dir", type=Path, default=Path("."))
    style_parser.add_argument("--plan-type", default="UIP", choices=("UIP", "NIP", "CDP"))
    return parser


def main(argv: list[str] | None = None) -> int:
    """Dispatch the requested subcommand and return its exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    _tolerate_unencodable_output()
    if args.command == "inspect":
        return _inspect(args)
    if args.command == "convert":
        return _convert(args)
    if args.command == "validate":
        return _validate(args)
    if args.command == "style":
        return _style(args)
    parser.error(f"Unknown command: {args.command}")
    return 2


def _inspect(args: argparse.Namespace) -> int:
    """List a drawing's layers with their PlanGML classification."""
    reader = NetcadReader(args.source).index()
    summaries = reader.layer_summaries()
    classified = [
        {
            **summary.to_dict(),
            "plangml": classify_layer(summary.layer_name, args.plan_type).to_dict(),
        }
        for summary in summaries
    ]
    if args.json:
        print(
            json.dumps(
                {
                    "source": str(args.source),
                    "backend": reader.backend,
                    "from_cache": reader.from_cache,
                    "version_name": reader.version_name,
                    "epsg": reader.epsg,
                    "projection_text": reader.projection_text,
                    "plan_type": args.plan_type,
                    "layers": classified,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    print(f"Source: {args.source}")
    print(f"Backend: {reader.backend}")
    print(f"Plan type: {args.plan_type}")
    if reader.version_name:
        print(f"Version: {reader.version_name}")
    if reader.epsg:
        print(f"CRS: {reader.epsg}")
    if not classified:
        print("No supported Netcad geometry layers found.")
        return 0
    print("Layers:")
    for item in classified:
        families = ", ".join(item["families"]) or "-"
        plangml = item["plangml"]
        identity = plangml["identity"] or {}
        label = ""
        if plangml["style"]:
            label = plangml["style"].get("label", "")
        tabaka = identity.get("tabaka") or plangml["style_key"] or "unmatched"
        print(
            f"  {item['layer_code']:>3}  {item['layer_name'] or '(unnamed)'}  "
            f"{item['record_count']} record(s)  [{families}]  {tabaka}  {label}"
        )
    return 0


_CONVERT_FORMATS = {
    ".geojson": "GeoJSON",
    ".json": "GeoJSON",
    ".gpkg": "GeoPackage",
    ".fgb": "FlatGeobuf",
    ".parquet": "GeoParquet",
    ".geoparquet": "GeoParquet",
    ".shp": "Shapefile",
    ".dxf": "DXF",
    ".kml": "KML",
    ".kmz": "KMZ",
}


def _convert(args: argparse.Namespace) -> int:
    """Convert a drawing (or selected layers) to the format named by the output extension."""
    fmt = _CONVERT_FORMATS.get(args.output.suffix.lower())
    if fmt is None:
        supported = ", ".join(sorted(_CONVERT_FORMATS))
        print(
            f"Unsupported output extension '{args.output.suffix}'. Use one of: {supported}",
            file=sys.stderr,
        )
        return 2
    reader = NetcadReader(args.source).index()
    if args.layers:
        layer_codes = [int(part.strip()) for part in args.layers.split(",") if part.strip()]
        entities = reader.decode_layers(layer_codes)
    else:
        entities = reader.parse().entities
    srid = args.srid or parse_epsg(reader.epsg)
    count = _write_format(fmt, entities, args.output, srid, args.plan_type)
    crs = f" (EPSG:{srid})" if srid else ""
    print(f"Wrote {count} feature(s) to {args.output} as {fmt}{crs}")
    return 0


def _write_format(fmt: str, entities: list, output: Path, srid: int | None, plan_type: str) -> int:
    """Write ``entities`` with the exporter for ``fmt`` and return the feature count."""
    if fmt == "GeoJSON":
        return len(write_geojson(entities, output, plan_type=plan_type, srid=srid)["features"])
    if fmt == "GeoPackage":
        return export_entities_to_geopackage(
            entities, output, table_name=output.stem, srs_id=srid, plan_type=plan_type
        ).total_features_written
    if fmt == "FlatGeobuf":
        return export_entities_to_flatgeobuf(
            entities, output, srid=srid, plan_type=plan_type
        ).feature_count
    if fmt == "GeoParquet":
        return export_entities_to_geoparquet(
            entities, output, srid=srid, plan_type=plan_type
        ).feature_count
    if fmt == "Shapefile":
        return export_entities_to_shapefile(
            entities, output, srid=srid, plan_type=plan_type
        ).feature_count
    if fmt == "DXF":
        return export_entities_to_dxf(entities, output, srid=srid, plan_type=plan_type).entity_count
    result = export_to_kml_kmz(entities, document_name=output.stem, srid=srid, plan_type=plan_type)
    if fmt == "KMZ":
        result.save_kmz(output)
    else:
        result.save_kml(output)
    return result.feature_count


def _validate(args: argparse.Namespace) -> int:
    """Validate a drawing for PlanGML and e-Plan compliance."""
    from .validator import validate_plan

    report = validate_plan(args.source, plan_type=args.plan_type)
    if args.json:
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
        return 0 if report.is_valid else 1
    if args.markdown:
        print(report.to_markdown())
        return 0 if report.is_valid else 1

    status = "VALID" if report.is_valid else "INVALID (Errors Found)"
    print(f"PlanGML Compliance: {status} (Score: {report.quality_score:.1f}/100)")
    print(f"Layers: {report.matched_layers}/{report.total_layers} classified")
    print(f"Total Entities: {report.total_entities}")
    if report.mandatory_layers_missing:
        print(f"Missing Mandatory Concepts: {', '.join(report.mandatory_layers_missing)}")
    if report.issues:
        print(f"Issues Found ({len(report.issues)}):")
        for iss in report.issues:
            print(f"  [{iss.severity}] {iss.category} ({iss.layer_name}): {iss.message}")
    return 0 if report.is_valid else 1


def _style(args: argparse.Namespace) -> int:
    """Generate OGC SLD, QGIS QML, or Mapbox GL style documents."""
    from .styler import export_mapbox_style, export_plan_styles, export_qml, export_sld

    reader = NetcadReader(args.source).index()
    layer_names = [s.layer_name for s in reader.layer_summaries()]

    if args.format == "all":
        paths = export_plan_styles(args.out_dir, layer_names, plan_type=args.plan_type)
        print(f"Generated styles in {args.out_dir}:")
        for k, p in paths.items():
            print(f"  - {k.upper()}: {p}")
    elif args.format == "sld":
        out = export_sld(layer_names, plan_type=args.plan_type)
        print(out)
    elif args.format == "qml":
        out = export_qml(layer_names, plan_type=args.plan_type)
        print(out)
    elif args.format == "mapbox":
        mapbox_style = export_mapbox_style(layer_names, plan_type=args.plan_type)
        print(json.dumps(mapbox_style, indent=2, ensure_ascii=False))
    return 0


def _tolerate_unencodable_output() -> None:
    """Replace characters stdout cannot encode instead of crashing.

    Redirected output on Windows uses the ANSI code page (e.g. cp1254), which
    cannot represent every decoded layer name or report symbol.
    """
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(errors="replace")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
