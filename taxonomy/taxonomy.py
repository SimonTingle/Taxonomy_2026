"""Map folder levels into a Department -> Function hierarchy."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional

from .parse_path import ParsedPath


@dataclass
class TaxonomyNode:
    department: str
    function: str


class TaxonomyMapper:
    def __init__(self, rules: Dict):
        mappings = (rules.get("folder_mappings") or {})
        self._dept = self._compile(mappings.get("department") or {})
        self._func = self._compile(mappings.get("function") or {})

    @staticmethod
    def _compile(mapping: Dict[str, List[str]]) -> Dict[str, List[re.Pattern]]:
        return {
            label: [re.compile(p, re.IGNORECASE) for p in patterns]
            for label, patterns in mapping.items()
        }

    @staticmethod
    def _match(text: str, compiled: Dict[str, List[re.Pattern]]) -> Optional[str]:
        for label, patterns in compiled.items():
            if any(p.search(text) for p in patterns):
                return label
        return None

    def map(self, parsed: ParsedPath) -> TaxonomyNode:
        levels = parsed.levels
        top = levels[0] if len(levels) > 0 else ""
        second = levels[1] if len(levels) > 1 else ""

        # Department: try the whole path (top levels), fall back to raw top folder.
        dept = self._match(top, self._dept) or self._match("/".join(levels[:2]), self._dept)
        if not dept:
            dept = top or "Unknown"

        # Function: try level_1, then anywhere in the path, fall back to raw second folder.
        func = self._match(second, self._func) or self._match("/".join(levels), self._func)
        if not func:
            func = second or "General"

        return TaxonomyNode(department=dept, function=func)


def common_path_structures(all_levels: List[List[str]], top_n: int = 15) -> Dict:
    """Summarise the most common path shapes to help propose a taxonomy."""
    from collections import Counter

    depth_counter: Counter = Counter()
    top_counter: Counter = Counter()
    template_counter: Counter = Counter()

    for levels in all_levels:
        depth_counter[len(levels)] += 1
        if levels:
            top_counter[levels[0]] += 1
        template_counter["/".join(levels[:3])] += 1

    return {
        "depth_distribution": dict(sorted(depth_counter.items())),
        "top_folders": top_counter.most_common(top_n),
        "common_templates": template_counter.most_common(top_n),
    }
