"""Load a SharePoint export CSV and auto-detect the key columns."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from typing import Dict, List, Optional

import pandas as pd

# Candidate header names (lower-cased) for each logical column, in priority order.
FILENAME_CANDIDATES = ["file name", "filename", "fileleafref", "name", "title"]
PATH_CANDIDATES = ["file path", "filepath", "fileref", "folder path", "path", "serverurl", "url"]

# Preferred encoding strips a leading BOM; fall back if the file isn't valid UTF-8.
ENCODINGS_TO_TRY = ["utf-8-sig", "latin-1"]

SNIFF_SAMPLE_BYTES = 65536


@dataclass
class ColumnMap:
    filename: Optional[str]
    path: Optional[str]


def _read_sample_text(input_path: str) -> tuple[str, str]:
    """Read a text sample for sniffing, trying each encoding until one decodes."""
    last_err: Optional[Exception] = None
    for enc in ENCODINGS_TO_TRY:
        try:
            with open(input_path, "r", encoding=enc, newline="") as fh:
                return fh.read(SNIFF_SAMPLE_BYTES), enc
        except UnicodeDecodeError as exc:
            last_err = exc
    raise ValueError(f"Could not decode {input_path} with any of {ENCODINGS_TO_TRY}") from last_err


def _sniff_dialect_and_header(sample: str) -> tuple[str, bool]:
    """Detect the delimiter and whether row 0 is a header, using csv.Sniffer.

    Falls back to comma + candidate-name matching when the sample is too small
    or ambiguous for the Sniffer to reach a verdict (e.g. a single column).
    """
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ","

    first_line = sample.splitlines()[0] if sample else ""
    first_row = next(csv.reader([first_line], delimiter=delimiter), [])

    try:
        has_header = csv.Sniffer().has_header(sample)
    except csv.Error:
        has_header = False

    # Sniffer's has_header relies on comparing data-type patterns across columns
    # and rows; it's unreliable on single-column or all-text data (e.g. a lone
    # "Path" header column). A candidate-name match is a strong independent
    # signal, so OR it in rather than replacing the statistical check.
    has_header = has_header or _looks_like_header(first_row)

    return delimiter, has_header


def _looks_like_header(first_row: List[str]) -> bool:
    """Fallback heuristic: a row is a header if any cell matches a known column name."""
    known = set(FILENAME_CANDIDATES) | set(PATH_CANDIDATES)
    return any(str(cell).lower().strip() in known for cell in first_row)


def _guess_positional(sample: pd.DataFrame) -> ColumnMap:
    """Headerless file: pick the path column (most '/'-containing) and filename
    column (most extension-like) by inspecting sample values."""
    path_scores, name_scores = {}, {}
    for col in sample.columns:
        vals = sample[col].astype(str)
        path_scores[col] = vals.str.contains(r"[\\/]").mean()
        name_scores[col] = vals.str.contains(r"\.[A-Za-z0-9]{1,5}$").mean()
    path_col = max(path_scores, key=path_scores.get) if path_scores else None
    # filename = best extension-scoring column that isn't the path column
    name_candidates = {c: s for c, s in name_scores.items() if c != path_col}
    name_col = max(name_candidates, key=name_candidates.get) if name_candidates else None
    return ColumnMap(filename=name_col, path=path_col)


def detect_columns(
    columns: List[str],
    filename_col: Optional[str] = None,
    path_col: Optional[str] = None,
) -> ColumnMap:
    """Resolve which CSV columns hold the filename and the path.

    Explicit overrides win; otherwise match case-insensitively against known
    SharePoint export headers.
    """
    lower = {c.lower().strip(): c for c in columns}

    def pick(candidates: List[str], override: Optional[str]) -> Optional[str]:
        if override:
            if override in columns:
                return override
            if override.lower().strip() in lower:
                return lower[override.lower().strip()]
            raise ValueError(f"Column '{override}' not found. Available: {list(columns)}")
        for cand in candidates:
            if cand in lower:
                return lower[cand]
        return None

    return ColumnMap(
        filename=pick(FILENAME_CANDIDATES, filename_col),
        path=pick(PATH_CANDIDATES, path_col),
    )


def load_export(
    input_path: str,
    filename_col: Optional[str] = None,
    path_col: Optional[str] = None,
    chunksize: Optional[int] = None,
) -> "pd.DataFrame | pd.io.parsers.TextFileReader":
    """Load the CSV. Returns a DataFrame, or a chunk iterator if chunksize is set.

    The detected column names are attached to the returned object via
    `.attrs['column_map']` (DataFrame only) for downstream use.

    Handles headered exports and headerless files, auto-detects the delimiter
    (comma/semicolon/tab/pipe) and falls back from utf-8 to latin-1 if needed.
    """
    sample, encoding = _read_sample_text(input_path)
    delimiter, has_header = _sniff_dialect_and_header(sample)

    read_kwargs = dict(dtype=str, keep_default_na=False, encoding=encoding, sep=delimiter)

    # Sniff the first few rows with NO header assumption to size the positional guess.
    sniff = pd.read_csv(input_path, header=None, nrows=25, **read_kwargs)

    if has_header:
        header = pd.read_csv(input_path, nrows=0, encoding=encoding, sep=delimiter)
        colmap = detect_columns(list(header.columns), filename_col, path_col)
        header_arg = "infer"
        names_arg = None
    else:
        # Headerless: name columns positionally and infer roles from content.
        ncols = sniff.shape[1]
        names_arg = [f"col_{i}" for i in range(ncols)]
        sniff.columns = names_arg
        colmap = _guess_positional(sniff)
        # Explicit overrides may reference positional names.
        if filename_col:
            colmap.filename = filename_col
        if path_col:
            colmap.path = path_col
        header_arg = None

    if not colmap.path and not colmap.filename:
        cols = names_arg if names_arg else list(
            pd.read_csv(input_path, nrows=0, encoding=encoding, sep=delimiter).columns
        )
        raise ValueError(
            "Could not detect a filename or path column. "
            f"Columns seen: {cols}. Pass --filename-col / --path-col to override."
        )

    if chunksize:
        reader = pd.read_csv(
            input_path, chunksize=chunksize, header=header_arg, names=names_arg, **read_kwargs
        )
        return reader

    df = pd.read_csv(input_path, header=header_arg, names=names_arg, **read_kwargs)
    df.attrs["column_map"] = {"filename": colmap.filename, "path": colmap.path}
    return df
