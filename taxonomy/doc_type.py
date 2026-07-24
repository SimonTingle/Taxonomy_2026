"""Rule engine: infer a document type + confidence from name and path."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List

from .parse_path import ParsedPath


@dataclass
class Classification:
    doc_type: str
    confidence: float          # 0.0 - 1.0
    method: str                # which signals fired, e.g. "name+path"
    format_class: str          # coarse class from extension (e.g. "document")


class DocTypeClassifier:
    """Compile rules once, then classify many files cheaply."""

    def __init__(self, rules: Dict):
        self._weights = rules.get("weights", {})
        self._w_name = float(self._weights.get("name_match", 0.6))
        self._w_path = float(self._weights.get("path_match", 0.3))
        self._w_ext = float(self._weights.get("extension_only", 0.15))

        # Pre-compile every regex for speed over 120k rows.
        self._doc_types: Dict[str, Dict[str, List[re.Pattern]]] = {}
        for name, spec in (rules.get("doc_types") or {}).items():
            self._doc_types[name] = {
                "name": [re.compile(p, re.IGNORECASE) for p in (spec.get("name") or [])],
                "path": [re.compile(p, re.IGNORECASE) for p in (spec.get("path") or [])],
            }

        # extension -> format class lookup
        self._ext_class: Dict[str, str] = {}
        for cls, exts in (rules.get("extension_class") or {}).items():
            for ext in exts:
                self._ext_class[ext.lower()] = cls

    def _format_class(self, extension: str) -> str:
        return self._ext_class.get(extension.lower(), "other")

    def classify(self, parsed: ParsedPath) -> Classification:
        name_text = parsed.stem or parsed.filename
        path_text = "/".join(parsed.levels)
        fmt = self._format_class(parsed.extension)

        best_type = "unclassified"
        best_score = 0.0
        best_method = "none"

        for doc_type, pats in self._doc_types.items():
            name_hit = any(p.search(name_text) for p in pats["name"])
            path_hit = any(p.search(path_text) for p in pats["path"])
            if not (name_hit or path_hit):
                continue

            # Blend independent signals; agreement of both raises confidence.
            score = 0.0
            methods = []
            if name_hit:
                score += self._w_name
                methods.append("name")
            if path_hit:
                score += self._w_path
                methods.append("path")
            score = min(score, 1.0)

            if score > best_score:
                best_score = score
                best_type = doc_type
                best_method = "+".join(methods)

        # No keyword match: fall back to the coarse format class at low confidence.
        if best_type == "unclassified" and fmt != "other":
            return Classification(
                doc_type=f"unclassified ({fmt})",
                confidence=round(self._w_ext, 3),
                method="extension_only",
                format_class=fmt,
            )

        return Classification(
            doc_type=best_type,
            confidence=round(best_score, 3),
            method=best_method,
            format_class=fmt,
        )
