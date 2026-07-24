from taxonomy.parse_path import parse_path


def test_splits_levels_and_strips_host():
    p = parse_path(
        "https://contoso.sharepoint.com/sites/Finance/AP/Invoices/Invoice_1.pdf",
        "Invoice_1.pdf",
    )
    assert p.levels == ["Finance", "AP", "Invoices"]
    assert p.filename == "Invoice_1.pdf"
    assert p.stem == "Invoice_1"
    assert p.extension == ".pdf"
    assert p.depth == 3


def test_backslash_separators():
    p = parse_path("Legal\\Contracts\\MSA.docx", "MSA.docx")
    assert p.levels == ["Legal", "Contracts"]
    assert p.extension == ".docx"


def test_filename_inferred_from_path_when_absent():
    p = parse_path("/HR/Policies/Handbook.pdf")
    assert p.filename == "Handbook.pdf"
    assert p.levels == ["HR", "Policies"]


def test_no_duplicate_leaf_when_path_ends_with_name():
    p = parse_path("/Sales/Reports/KPI.xlsx", "KPI.xlsx")
    assert p.levels == ["Sales", "Reports"]
    assert p.filename == "KPI.xlsx"
