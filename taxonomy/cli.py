"""Command-line entry point.

Usage:
    python -m taxonomy.cli --input data/sample_export.csv --out out/
    python -m taxonomy.cli --input export.csv --out out/ \
        --filename-col FileLeafRef --path-col FileRef
"""

from __future__ import annotations

import argparse
import os
import sys

from .classify import run

_DEFAULT_RULES = os.path.join(os.path.dirname(__file__), "rules.yaml")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Classify a SharePoint export into a Department/Function/DocType taxonomy."
    )
    parser.add_argument("--input", "-i", required=True, help="Path to the export CSV.")
    parser.add_argument("--out", "-o", default="out", help="Output directory (default: out/).")
    parser.add_argument("--rules", "-r", default=_DEFAULT_RULES, help="Path to rules.yaml.")
    parser.add_argument("--filename-col", default=None, help="Override the filename column name.")
    parser.add_argument("--path-col", default=None, help="Override the path column name.")
    parser.add_argument(
        "--propose",
        action="store_true",
        help=(
            "Also write out/proposed_rules.yaml (data-driven department/function "
            "candidates) and out/doc_type_gap_report.json (recurring filename tokens "
            "among unclassified files), for manual review — never auto-merged."
        ),
    )
    args = parser.parse_args(argv)

    try:
        summary = run(
            input_path=args.input,
            out_dir=args.out,
            rules_path=args.rules,
            filename_col=args.filename_col,
            path_col=args.path_col,
            propose=args.propose,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    cols = summary["_columns_detected"]
    print(f"Detected columns  -> filename: {cols['filename']!r}, path: {cols['path']!r}")
    print(f"Total files       : {summary['total_files']:,}")
    print(f"Classified        : {summary['classified_pct']}%")
    print(f"Distinct types    : {summary['distinct_doc_types']}")
    print(f"Low confidence    : {summary['low_confidence_count']:,}")
    print("Top doc types     :")
    for name, count in list(summary["doc_type_counts"].items())[:10]:
        print(f"    {name:<28} {count:,}")
    print(f"\nWrote {summary['_outputs']['classified_csv']}")
    print(f"Wrote {summary['_outputs']['summary_json']}")
    if "proposed_rules_yaml" in summary["_outputs"]:
        print(f"Wrote {summary['_outputs']['proposed_rules_yaml']}")
        print(f"Wrote {summary['_outputs']['doc_type_gap_report_json']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
