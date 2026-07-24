import pandas as pd
import yaml

from taxonomy.propose import (
    propose_department_function,
    propose_doctype_gaps,
    render_proposed_rules_yaml,
)


def _df(rows):
    return pd.DataFrame(rows)


def test_propose_department_function_ranks_by_real_frequency():
    df = _df(
        [
            {"level_0": "Finance", "level_1": "AP"},
            {"level_0": "Finance", "level_1": "AP"},
            {"level_0": "Finance", "level_1": "AR"},
            {"level_0": "HR", "level_1": "Payroll"},
        ]
    )
    proposal = propose_department_function(df, top_n=10)

    dept_labels = [c["label"] for c in proposal["department_candidates"]]
    assert dept_labels[0] == "Finance"  # most frequent first
    assert dept_labels[1] == "HR"

    func_counts = {c["label"]: c["count"] for c in proposal["function_candidates"]}
    assert func_counts["AP"] == 2
    assert func_counts["AR"] == 1


def test_propose_department_function_handles_missing_level_columns():
    df = _df([{"resolved_filename": "x.pdf"}])  # no level_0/level_1 at all
    proposal = propose_department_function(df)
    assert proposal["department_candidates"] == []
    assert proposal["function_candidates"] == []


def test_render_proposed_rules_yaml_includes_counts_and_is_valid_yaml():
    proposal = {
        "department_candidates": [{"label": "Finance", "count": 3}],
        "function_candidates": [{"label": "AP", "count": 2}],
    }
    text = render_proposed_rules_yaml(proposal)

    assert "3 files" in text
    assert "Finance" in text

    parsed = yaml.safe_load(text)
    assert parsed["department"]["Finance"] == ["finance"]
    assert parsed["function"]["AP"] == ["ap"]


def test_render_proposed_rules_yaml_escapes_apostrophes_safely():
    """Regression guard: a naive f"['{pattern}']" breaks YAML when the folder
    name contains an apostrophe (e.g. "Gater's Mill") since re.escape() doesn't
    escape apostrophes and the hand-built single-quoted string becomes invalid."""
    proposal = {
        "department_candidates": [{"label": "Gater's Mill", "count": 5}],
        "function_candidates": [],
    }
    text = render_proposed_rules_yaml(proposal)

    parsed = yaml.safe_load(text)  # must not raise
    patterns = list(parsed["department"].values())[0]
    assert any("gater" in p.lower() for p in patterns)


def test_propose_doctype_gaps_ranks_tokens_and_excludes_classified_files():
    df = _df(
        [
            {"doc_type": "unclassified (document)", "resolved_filename": "HTR-POR-001-Rev1.docx"},
            {"doc_type": "unclassified (document)", "resolved_filename": "HTR-POR-002-Rev2.docx"},
            {"doc_type": "invoice", "resolved_filename": "Invoice_1.pdf"},
            {"doc_type": "unclassified", "resolved_filename": "Random.txt"},
        ]
    )
    gaps = propose_doctype_gaps(df, top_n=10, min_token_len=3)
    tokens = {g["token"]: g for g in gaps}

    assert "HTR" in tokens and tokens["HTR"]["count"] == 2
    assert "POR" in tokens and tokens["POR"]["count"] == 2
    assert "REV" in tokens and tokens["REV"]["count"] == 2
    assert "INVOICE" not in tokens  # classified file must be excluded
    assert len(tokens["HTR"]["examples"]) <= 3
