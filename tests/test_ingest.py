import pytest

from taxonomy.ingest import load_export


def test_semicolon_delimited_is_detected(tmp_path):
    p = tmp_path / "semicolon.csv"
    p.write_text("FileLeafRef;FileRef\nInvoice_1.pdf;/Finance/Invoices/Invoice_1.pdf\n")

    df = load_export(str(p))

    assert len(df) == 1
    colmap = df.attrs["column_map"]
    assert colmap["filename"] == "FileLeafRef"
    assert colmap["path"] == "FileRef"


def test_unrecognized_header_is_not_treated_as_data(tmp_path):
    p = tmp_path / "unknown_headers.csv"
    p.write_text("DocName,Location\nInvoice_1.pdf,/Finance/Invoices\nHandbook.docx,/HR/Policies\n")

    # Header exists but neither column name is recognised -> must raise, not
    # silently swallow the header row as a bogus data record.
    with pytest.raises(ValueError, match="Could not detect"):
        load_export(str(p))


def test_single_column_named_header_still_detected(tmp_path):
    """Regression guard: csv.Sniffer.has_header() is unreliable on single-column,
    all-text data, so a recognised column name must still force header detection."""
    p = tmp_path / "path_only.csv"
    p.write_text("Path\n/Finance/Invoices/Invoice_1.pdf\n/HR/Policies/Handbook.docx\n")

    df = load_export(str(p))

    assert len(df) == 2
    assert df.attrs["column_map"]["path"] == "Path"


def test_headerless_two_column_export(tmp_path):
    p = tmp_path / "headerless.csv"
    p.write_text(
        "Invoice_1.pdf,sites/Finance/Invoices\n"
        "Handbook.docx,sites/HR/Policies\n"
    )

    df = load_export(str(p))

    assert len(df) == 2
    colmap = df.attrs["column_map"]
    assert colmap["filename"] == "col_0"
    assert colmap["path"] == "col_1"
