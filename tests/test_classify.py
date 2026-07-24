import os

import pandas as pd

from taxonomy.classify import run

RULES = os.path.join(os.path.dirname(__file__), "..", "taxonomy", "rules.yaml")


def test_level_columns_size_to_real_max_depth(tmp_path):
    csv_path = tmp_path / "mixed_depth.csv"
    csv_path.write_text(
        "FileLeafRef,FileRef\n"
        "Shallow.pdf,/Finance/Shallow.pdf\n"
        "Deep.pdf,/Finance/AP/Invoices/2024/Q1/Deep.pdf\n"
    )
    out_dir = tmp_path / "out"

    run(str(csv_path), str(out_dir), RULES)

    df = pd.read_csv(out_dir / "classified.csv", dtype=str, keep_default_na=False)
    level_cols = [c for c in df.columns if c.startswith("level_")]
    # Deep.pdf has 5 folder levels: Finance/AP/Invoices/2024/Q1 -> level_0..level_4
    assert level_cols == [f"level_{i}" for i in range(5)]


def test_no_level_columns_when_no_folders(tmp_path):
    csv_path = tmp_path / "flat.csv"
    csv_path.write_text("FileLeafRef,FileRef\nRoot.pdf,Root.pdf\n")
    out_dir = tmp_path / "out"

    run(str(csv_path), str(out_dir), RULES)

    df = pd.read_csv(out_dir / "classified.csv", dtype=str, keep_default_na=False)
    level_cols = [c for c in df.columns if c.startswith("level_")]
    assert level_cols == []


def test_level_column_ceiling_caps_pathological_depth(tmp_path):
    csv_path = tmp_path / "very_deep.csv"
    deep_path = "/" + "/".join(f"L{i}" for i in range(30)) + "/File.pdf"
    csv_path.write_text(f"FileLeafRef,FileRef\nFile.pdf,{deep_path}\n")
    out_dir = tmp_path / "out"

    run(str(csv_path), str(out_dir), RULES)

    df = pd.read_csv(out_dir / "classified.csv", dtype=str, keep_default_na=False)
    level_cols = [c for c in df.columns if c.startswith("level_")]
    assert len(level_cols) == 20  # MAX_LEVEL_COLUMNS_CEILING
