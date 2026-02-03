from unittest.mock import MagicMock, Mock, patch

import pytest
from fastapi.testclient import TestClient
from google.cloud import dlp_v2

from peekguard.api.masking.handler import (
    AddressMasker,
    PlaceholderManager,
    PresidioMasker,
    mask_sentence,
)

from peekguard.utils.dlp_recognizer import GoogleDlpRecognizer
from peekguard.main import app


def test_placeholder_manager_initialization_empty():
    pm = PlaceholderManager(None)
    assert pm.mappings == {}


def test_placeholder_manager_initialization_with_existing():
    existing_mappings = {"<PERSON_1>": "John Doe"}
    pm = PlaceholderManager(existing_mappings)
    assert pm.mappings == existing_mappings


def test_placeholder_manager_placeholder_for_new_entity():
    pm = PlaceholderManager(None)
    placeholder = pm.placeholder_for("PERSON", "Jane Doe")
    assert placeholder == "<PERSON_1>"
    assert pm.mappings == {"<PERSON_1>": "Jane Doe"}


def test_placeholder_manager_placeholder_for_existing_entity():
    pm = PlaceholderManager(None)
    pm.placeholder_for("PERSON", "Jane Doe")
    placeholder = pm.placeholder_for("PERSON", "Jane Doe")
    assert placeholder == "<PERSON_1>"


def test_placeholder_manager_placeholder_for_different_entity():
    pm = PlaceholderManager(None)
    pm.placeholder_for("PERSON", "Jane Doe")
    placeholder = pm.placeholder_for("LOCATION", "New York")
    assert placeholder == "<LOCATION_1>"


@patch("peekguard.api.masking.handler.pyap.parse")
def test_address_masker(mock_pyap_parse):
    mock_address = Mock()
    mock_address.full_address = "123 Main St, Anytown, USA"
    mock_address.match_start = 15
    mock_address.match_end = 42
    mock_pyap_parse.return_value = [mock_address]
    pm = PlaceholderManager(None)
    am = AddressMasker(pm)
    text = "The address is 123 Main St, Anytown, USA."
    masked_text, spans = am.mask(text)
    assert "<LOCATION_1>" in masked_text
    assert pm.mappings["<LOCATION_1>"] == "123 Main St, Anytown, USA"


@patch("peekguard.api.masking.handler.pyap.parse")
def test_address_masker_no_address(mock_pyap_parse):
    mock_pyap_parse.return_value = []
    pm = PlaceholderManager(None)
    am = AddressMasker(pm)
    text = "There is no address here."
    masked_text, spans = am.mask(text)
    assert masked_text == text
    assert spans == []


def test_presidio_masker():
    analyzer = MagicMock()
    recognizer_result = MagicMock()
    recognizer_result.entity_type = "PERSON"
    recognizer_result.start = 11
    recognizer_result.end = 19
    recognizer_result.score = 0.85
    analyzer.analyze.return_value = [recognizer_result]

    pm = PlaceholderManager(None)
    presidio_masker = PresidioMasker(analyzer, pm, "en")
    text = "My name is John Doe."
    masked_text = presidio_masker.mask(text, ["PERSON"], [])
    assert "<PERSON_1>" in masked_text
    assert pm.mappings["<PERSON_1>"] == "John Doe"


def test_presidio_masker_no_entities():
    analyzer = MagicMock()
    pm = PlaceholderManager(None)
    presidio_masker = PresidioMasker(analyzer, pm, "en")
    text = "My name is John Doe."
    masked_text = presidio_masker.mask(text, [], [])
    assert masked_text == text


def make_dlp_finding(
    *,
    info_type: str,
    text: str,
    start_char: int,
    end_char: int,
    likelihood=dlp_v2.Likelihood.VERY_LIKELY,
):
    """
    Create a mock DLP finding with correct byte offsets.
    """
    # Convert char offsets → byte offsets (what DLP returns)
    start_byte = len(text[:start_char].encode("utf-8"))
    end_byte = len(text[:end_char].encode("utf-8"))

    finding = MagicMock()
    finding.info_type.name = info_type
    finding.likelihood = likelihood
    finding.location.byte_range.start = start_byte
    finding.location.byte_range.end = end_byte

    return finding


@patch("peekguard.utils.dlp_recognizer.dlp_v2.DlpServiceClient")
def test_dlp_recognizer_passport_identification(mock_dlp_client_cls):
    mock_dlp_client = MagicMock()
    mock_dlp_client_cls.return_value = mock_dlp_client

    recognizer = GoogleDlpRecognizer(project_id="test-project")

    text = "Passport number A1234567"

    finding = make_dlp_finding(
        info_type="PASSPORT",
        text=text,
        start_char=16,
        end_char=24,
    )

    mock_dlp_client.inspect_content.return_value = Mock(
        result=Mock(findings=[finding])
    )

    results = recognizer.analyze(text, ["GOVERNMENT_ID"])

    assert len(results) == 1
    assert results[0].entity_type == "GOVERNMENT_ID"
    assert text[results[0].start:results[0].end] == "A1234567"


@patch("peekguard.api.masking.handler.pyap.parse")
def test_mask_sentence(mock_pyap_parse):
    mock_address = Mock()
    mock_address.full_address = "123 Main St, Anytown, USA"
    mock_address.match_start = 35
    mock_address.match_end = 62
    mock_pyap_parse.return_value = [mock_address]

    analyzer = MagicMock()
    recognizer_result = MagicMock()
    recognizer_result.entity_type = "PERSON"
    recognizer_result.start = 11
    recognizer_result.end = 19
    recognizer_result.score = 0.85
    analyzer.analyze.return_value = [recognizer_result]

    text = "My name is John Doe and I live at 123 Main St, Anytown, USA."
    masked_text, mappings = mask_sentence(text, analyzer, "en", ["PERSON", "LOCATION"], None)
    assert "<PERSON_1>" in masked_text
    assert "<LOCATION_1>" in masked_text
    assert mappings["<PERSON_1>"] == "John Doe"
    assert mappings["<LOCATION_1>"] == "123 Main St, Anytown, USA"


@patch("peekguard.api.masking.handler.pyap.parse")
def test_mask_sentence_no_analyzer(mock_pyap_parse):
    mock_address = Mock()
    mock_address.full_address = "123 Main St, Anytown, USA"
    mock_address.match_start = 35
    mock_address.match_end = 62
    mock_pyap_parse.return_value = [mock_address]
    text = "My name is John Doe and I live at 123 Main St, Anytown, USA."
    masked_text, mappings = mask_sentence(text, None, "en", ["PERSON", "LOCATION"], None)
    assert "<LOCATION_1>" in masked_text
    assert mappings["<LOCATION_1>"] == "123 Main St, Anytown, USA"


def test_mask_sentence_empty_sentence():
    masked_text, mappings = mask_sentence("", None, "en", [], None)
    assert masked_text == ""
    assert mappings == {}


def test_mask_sentence_invalid_entities():
    with pytest.raises(Exception):
        mask_sentence("some text", None, "en", ["INVALID_ENTITY"], None)



@pytest.fixture
def client():
    with TestClient(app) as c:
        app.state.analyzer_engine = MagicMock()
        app.state.service_initialized_successfully = True
        yield c

def test_get_analyzer_engine_dependency_success(client):
    response = client.post("/mask", json={"text_data": "test"})
    assert response.status_code != 503

def test_get_analyzer_engine_dependency_not_ready(client):
    app.state.service_initialized_successfully = False
    response = client.post("/mask", json={"text_data": "test"})
    assert response.status_code == 503
    assert "Core service components are not ready" in response.text
    app.state.service_initialized_successfully = True

def test_get_analyzer_engine_dependency_no_analyzer(client):
    original_analyzer = app.state.analyzer_engine
    app.state.analyzer_engine = None
    response = client.post("/mask", json={"text_data": "test"})
    assert response.status_code == 503
    assert "AnalyzerEngine not available" in response.text
    app.state.analyzer_engine = original_analyzer

@patch("peekguard.api.masking.router.mask_sentence")
def test_mask_pii_data_success(mock_mask_sentence, client):
    mock_mask_sentence.return_value = ("masked text", {"<PERSON_1>": "John Doe"})
    response = client.post(
        "/mask",
        json={
            "text_data": "My name is John Doe",
            "language": "en",
            "entities": ["PERSON"],
        },
    )
    assert response.status_code == 200
    assert response.json() == {
        "masked_data": "masked text",
        "mappings": {"<PERSON_1>": "John Doe"},
    }