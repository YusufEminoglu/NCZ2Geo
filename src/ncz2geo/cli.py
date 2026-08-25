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
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "inspect":
        return _inspect(args)
    if args.command == "convert":
        return _convert(args)
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


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
