import os

import pytest

from taxonomy.classify import load_rules
from taxonomy.doc_type import DocTypeClassifier
from taxonomy.parse_path import parse_path

RULES = os.path.join(os.path.dirname(__file__), "..", "taxonomy", "rules.yaml")


@pytest.fixture(scope="module")
def classifier():
    return DocTypeClassifier(load_rules(RULES))


@pytest.mark.parametrize(
    "path,name,expected",
    [
        ("/Finance/AP/Invoices/Invoice_1023.pdf", "Invoice_1023.pdf", "invoice"),
        ("/Legal/Contracts/MSA.pdf", "Master Services Agreement.pdf", "contract"),
        ("/Operations/Board/Minutes/Board_Minutes_Q1.docx", "Board_Minutes_Q1.docx", "minutes"),
        ("/HR/Policies/HR_Leave_Policy.pdf", "HR_Leave_Policy.pdf", "policy"),
        ("/HR/Recruitment/Candidates/CV_Jane_Doe.pdf", "CV_Jane_Doe.pdf", "cv"),
    ],
)
def test_known_types(classifier, path, name, expected):
    cls = classifier.classify(parse_path(path, name))
    assert cls.doc_type == expected
    assert cls.confidence > 0.0


def test_name_and_path_agreement_beats_name_only(classifier):
    both = classifier.classify(parse_path("/Finance/Invoices/Invoice_9.pdf", "Invoice_9.pdf"))
    name_only = classifier.classify(parse_path("/Misc/Stuff/Invoice_9.pdf", "Invoice_9.pdf"))
    assert both.confidence > name_only.confidence
    assert "path" in both.method


def test_unclassified_falls_back_to_format_class(classifier):
    cls = classifier.classify(parse_path("/Misc/random_photo.jpg", "random_photo.jpg"))
    assert cls.doc_type.startswith("unclassified")
    assert cls.format_class == "image"
