"""Command-line interface for NCZ2Geo."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .geojson import write_geojson
from .plangml import classify_layer
from .reader import NetcadReader, parse_netcad


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ncz2geo",
        description="Inspect Netcad NCZ/NCA files and export PlanGML-aware GeoJSON.",
    )
    parser.add_argument("--version", action="version", version=f"NCZ2Geo {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="List NCZ/NCA layers and PlanGML matches.")
    inspect_parser.add_argument("source", type=Path)
    inspect_parser.add_argument("--plan-type", default="UIP", choices=("UIP", "NIP", "CDP"))
    inspect_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")

    convert_parser = subparsers.add_parser("convert", help="Convert an NCZ/NCA file to styled GeoJSON.")
    convert_parser.add_argument("source", type=Path)
    convert_parser.add_argument("output", type=Path)
    convert_parser.add_argument("--plan-type", default="UIP", choices=("UIP", "NIP", "CDP"))
    convert_parser.add_argument(
        "--layers",
        help="Comma-separated layer codes to decode; defaults to all layers.",
    )

    val_parser = subparsers.add_parser("validate", help="Validate PlanGML and e-Plan compliance.")
    val_parser.add_argument("source", type=Path)
    val_parser.add_argument("--plan-type", choices=("UIP", "NIP", "CDP"))
    val_parser.add_argument("--json", action="store_true", help="Output validation report as JSON.")
    val_parser.add_argument("--markdown", action="store_true", help="Output validation report as Markdown.")

    style_parser = subparsers.add_parser("style", help="Generate OGC SLD, QGIS QML, or Mapbox GL styles.")
    style_parser.add_argument("source", type=Path)
    style_parser.add_argument("--format", choices=("sld", "qml", "mapbox", "all"), default="all")
    style_parser.add_argument("--out-dir", type=Path, default=Path("."))
    style_parser.add_argument("--plan-type", default="UIP", choices=("UIP", "NIP", "CDP"))
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
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


def _convert(args: argparse.Namespace) -> int:
    if args.layers:
        layer_codes = [int(part.strip()) for part in args.layers.split(",") if part.strip()]
        reader = NetcadReader(args.source).index()
        entities = reader.decode_layers(layer_codes)
    else:
        entities = parse_netcad(args.source).entities
    collection = write_geojson(entities, args.output, plan_type=args.plan_type)
    print(f"Wrote {len(collection['features'])} feature(s) to {args.output}")
    return 0


def _validate(args: argparse.Namespace) -> int:
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
        out = export_mapbox_style(layer_names, plan_type=args.plan_type)
        print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
