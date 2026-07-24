"""Orchestrate ingest -> parse -> classify -> write outputs."""

from __future__ import annotations

import json
import os
from collections import Counter
from typing import Dict, Optional

import pandas as pd
import yaml

from .doc_type import DocTypeClassifier
from .ingest import detect_columns, load_export
from .parse_path import parse_path
from .propose import (
    propose_department_function,
    propose_doctype_gaps,
    render_proposed_rules_yaml,
)
from .taxonomy import TaxonomyMapper, common_path_structures

LOW_CONFIDENCE_THRESHOLD = 0.4
MAX_LEVEL_COLUMNS_CEILING = 20  # safety cap; real depth is used if smaller


def load_rules(rules_path: str) -> Dict:
    with open(rules_path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def classify_dataframe(
    df: pd.DataFrame,
    colmap: Dict[str, Optional[str]],
    classifier: DocTypeClassifier,
    mapper: TaxonomyMapper,
) -> pd.DataFrame:
    """Return a new frame with taxonomy + doc-type columns appended."""
    filename_col = colmap.get("filename")
    path_col = colmap.get("path")

    records = []
    all_levels = []
    for _, row in df.iterrows():
        raw_path = row[path_col] if path_col else ""
        raw_name = row[filename_col] if filename_col else ""
        parsed = parse_path(raw_path, raw_name)
        all_levels.append(parsed.levels)

        cls = classifier.classify(parsed)
        node = mapper.map(parsed)

        rec = {
            "resolved_filename": parsed.filename,
            "extension": parsed.extension,
            "depth": parsed.depth,
            "department": node.department,
            "function": node.function,
            "doc_type": cls.doc_type,
            "confidence": cls.confidence,
            "method": cls.method,
            "format_class": cls.format_class,
            "_levels": parsed.levels,  # filled into level_N columns below, then dropped
        }
        records.append(rec)

    # Size the level_N columns to the real max depth in this dataset (capped for
    # safety), instead of a fixed guess — so deep paths aren't silently truncated.
    max_depth = min(max((len(lv) for lv in all_levels), default=0), MAX_LEVEL_COLUMNS_CEILING)
    for rec in records:
        levels = rec.pop("_levels")
        for i in range(max_depth):
            rec[f"level_{i}"] = levels[i] if i < len(levels) else ""

    enriched = pd.DataFrame(records, index=df.index)
    result = pd.concat([df.reset_index(drop=True), enriched.reset_index(drop=True)], axis=1)
    result.attrs["all_levels"] = all_levels
    return result


def build_summary(result: pd.DataFrame) -> Dict:
    all_levels = result.attrs.get("all_levels", [])
    low = result[result["confidence"] < LOW_CONFIDENCE_THRESHOLD]
    return {
        "total_files": int(len(result)),
        "distinct_doc_types": int(result["doc_type"].nunique()),
        "classified_pct": round(
            100.0 * (~result["doc_type"].str.startswith("unclassified")).mean(), 1
        ) if len(result) else 0.0,
        "low_confidence_count": int(len(low)),
        "doc_type_counts": _counts(result["doc_type"]),
        "department_counts": _counts(result["department"]),
        "function_counts": _counts(result["function"]),
        "path_structures": common_path_structures(all_levels),
    }


def _counts(series: pd.Series) -> Dict[str, int]:
    return {str(k): int(v) for k, v in series.value_counts().items()}


def run(
    input_path: str,
    out_dir: str,
    rules_path: str,
    filename_col: Optional[str] = None,
    path_col: Optional[str] = None,
    propose: bool = False,
) -> Dict:
    """Full pipeline. Writes classified.csv + summary.json, returns the summary.

    When propose=True, also writes out/proposed_rules.yaml (data-driven
    department/function candidates) and out/doc_type_gap_report.json (recurring
    filename tokens among unclassified files) — both for human review, never
    auto-merged into taxonomy/rules.yaml.
    """
    rules = load_rules(rules_path)
    classifier = DocTypeClassifier(rules)
    mapper = TaxonomyMapper(rules)

    df = load_export(input_path, filename_col, path_col)
    colmap = df.attrs.get("column_map") or vars(
        detect_columns(list(df.columns), filename_col, path_col)
    )

    result = classify_dataframe(df, colmap, classifier, mapper)
    summary = build_summary(result)

    os.makedirs(out_dir, exist_ok=True)
    csv_path = os.path.join(out_dir, "classified.csv")
    json_path = os.path.join(out_dir, "summary.json")
    result.to_csv(csv_path, index=False)
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)

    summary["_outputs"] = {"classified_csv": csv_path, "summary_json": json_path}
    summary["_columns_detected"] = colmap

    if propose:
        rules_out_path = os.path.join(out_dir, "proposed_rules.yaml")
        gaps_out_path = os.path.join(out_dir, "doc_type_gap_report.json")

        dept_func_proposal = propose_department_function(result)
        with open(rules_out_path, "w", encoding="utf-8") as fh:
            fh.write(render_proposed_rules_yaml(dept_func_proposal))

        gap_report = propose_doctype_gaps(result)
        with open(gaps_out_path, "w", encoding="utf-8") as fh:
            json.dump(gap_report, fh, indent=2)

        summary["_outputs"]["proposed_rules_yaml"] = rules_out_path
        summary["_outputs"]["doc_type_gap_report_json"] = gaps_out_path

    return summary
