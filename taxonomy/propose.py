"""Data-driven taxonomy proposal + doc-type gap report.

Operates on the already-classified result DataFrame (has level_0..level_n,
doc_type, resolved_filename columns) — no re-ingesting needed. Everything here
is frequency counting over the real data, not ML/clustering: it surfaces what's
actually in the export so a human can approve/relabel it, rather than guessing
generic category names up front.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Dict, List

import pandas as pd
import yaml

TOKEN_RE = re.compile(r"[A-Za-z]+")
STOPWORD_TOKENS = {
    "the", "and", "for", "of", "in", "on", "a", "an",
    # Unambiguous URL-protocol artifacts — some filenames are full pasted URLs
    # rather than document names; these fragments carry no doc-type signal.
    "https", "http", "www", "sharepoint", "com",
}


def _level_col(df: pd.DataFrame, i: int) -> pd.Series:
    col = f"level_{i}"
    if col in df.columns:
        return df[col]
    return pd.Series([""] * len(df), index=df.index)


def _first_varying_level(df: pd.DataFrame, start: int = 0, max_search: int = 12) -> int:
    """Return the first level index >= start with more than one distinct value.

    SharePoint exports often have constant leading levels (the site name, the
    document library — e.g. every file under /sites/pr19/WAR/Shared Documents/...),
    which carry zero discriminating information for a taxonomy. Skip past those
    instead of hard-coding level_0/level_1, or the proposal degenerates to a
    single candidate. Falls back to `start` if nothing varies within the search
    window (e.g. a dataset with no folders at all).
    """
    for i in range(start, start + max_search):
        col = _level_col(df, i)
        non_empty = col[col != ""]
        if non_empty.nunique() > 1:
            return i
    return start


def propose_department_function(result_df: pd.DataFrame, top_n: int = 25) -> Dict:
    """Rank real folder names as department/function candidates, using the first
    folder levels that actually vary across the dataset — labels come straight
    from the data, not a hard-coded level_0/level_1 assumption.
    """
    dept_level = _first_varying_level(result_df, start=0)
    func_level = _first_varying_level(result_df, start=dept_level + 1)

    dept_counts = Counter(v for v in _level_col(result_df, dept_level) if v)
    func_counts = Counter(v for v in _level_col(result_df, func_level) if v)

    return {
        "department_candidates": [
            {"label": name, "count": count} for name, count in dept_counts.most_common(top_n)
        ],
        "function_candidates": [
            {"label": name, "count": count} for name, count in func_counts.most_common(top_n)
        ],
        "levels_used": {"department": dept_level, "function": func_level},
    }


def _safe_label(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9 ]", "", name).strip()
    return cleaned or name


def _yaml_scalar(value) -> str:
    """Render a value as a correctly-escaped YAML flow scalar (e.g. a key or a
    ['pattern'] list), not a hand-built string. Folder names can contain
    apostrophes, colons, or other characters that break naive single-quoting
    (e.g. "Gater's Mill") — let PyYAML decide how to quote it safely."""
    text = yaml.safe_dump(value, default_flow_style=True).strip()
    if text.endswith("..."):
        text = text[:-3].rstrip()
    return text


def render_proposed_rules_yaml(proposal: Dict) -> str:
    """Render candidates in the same shape as rules.yaml's folder_mappings, with
    counts as comments — for human review before merging into taxonomy/rules.yaml.
    """
    levels_used = proposal.get("levels_used", {})
    lines = [
        "# Proposed folder_mappings, derived from the real data (not hand-guessed).",
        "# Review the labels below, then copy the ones you want into taxonomy/rules.yaml's",
        "# folder_mappings section. Counts show how many files fall under each folder.",
        "#",
        f"# department candidates come from folder level {levels_used.get('department', 0)};",
        f"# function candidates come from folder level {levels_used.get('function', 1)}.",
        "# (Leading levels that were constant across every file — e.g. a SharePoint site",
        "# name or document library shared by the whole export — are skipped automatically",
        "# since they carry no discriminating information.)",
        "#",
        "# NOTE: frequency alone has no semantic understanding — a common folder may rank",
        "# highly without being a real business department. Relabel/drop as needed.",
        "",
        "department:",
    ]
    for cand in proposal["department_candidates"]:
        label = cand["label"]
        key = _yaml_scalar(_safe_label(label))
        patterns = _yaml_scalar([re.escape(label.lower())])
        lines.append(f"  {key}: {patterns}  # {cand['count']:,} files (folder: \"{label}\")")

    lines.append("")
    lines.append("function:")
    for cand in proposal["function_candidates"]:
        label = cand["label"]
        key = _yaml_scalar(_safe_label(label))
        patterns = _yaml_scalar([re.escape(label.lower())])
        lines.append(f"  {key}: {patterns}  # {cand['count']:,} files (folder: \"{label}\")")

    return "\n".join(lines) + "\n"


def propose_doctype_gaps(
    result_df: pd.DataFrame, top_n: int = 30, min_token_len: int = 3
) -> List[Dict]:
    """Rank recurring filename tokens among currently-unclassified files, with a
    couple of example filenames per token — a frequency-based assist for writing
    new doc_type keyword rules in rules.yaml. Not automatic classification.
    """
    mask = result_df["doc_type"].astype(str).str.startswith("unclassified")
    unclassified = result_df.loc[mask, "resolved_filename"].fillna("")

    token_counts: Counter = Counter()
    token_examples: Dict[str, List[str]] = {}

    for filename in unclassified:
        stem = filename.rsplit(".", 1)[0] if "." in filename else filename
        tokens = {t.upper() for t in TOKEN_RE.findall(stem) if len(t) >= min_token_len}
        for tok in tokens:
            if tok.lower() in STOPWORD_TOKENS:
                continue
            token_counts[tok] += 1
            examples = token_examples.setdefault(tok, [])
            if len(examples) < 3:
                examples.append(filename)

    return [
        {"token": tok, "count": count, "examples": token_examples[tok]}
        for tok, count in token_counts.most_common(top_n)
    ]
