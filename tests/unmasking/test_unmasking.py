import pytest
from fastapi.testclient import TestClient

from peekguard.api.unmasking.router import _unmask_sentence
from peekguard.api.unmasking.schema import UnmaskRequest, UnmaskResponse
from peekguard.main import app

client = TestClient(app)


# Test cases for _unmask_sentence function
@pytest.mark.parametrize(
    "masked_data, mappings, expected_output",
    [
        ("", {}, ""),
        ("Hello <PERSON_1>", {}, "Hello <PERSON_1>"),
        ("", {"<PERSON_1>": "World"}, ""),
        (
            "User: <PERSON_1>, Email: <EMAIL_ADDRESS_1>",
            {"<PERSON_1>": "John Doe", "<EMAIL_ADDRESS_1>": "john.doe@example.com"},
            "User: John Doe, Email: john.doe@example.com",
        ),
        (
            "Card: <CREDIT_CARD_1>, Phone: <PHONE_NUMBER_1>",
            {"<CREDIT_CARD_1>": "1234-5678-9012-3456", "<PHONE_NUMBER_1>": "555-0100"},
            "Card: 1234-5678-9012-3456, Phone: 555-0100",
        ),
        (
            "SSN: <US_SSN_1>, IP: <IP_ADDRESS_1>",
            {"<US_SSN_1>": "000-00-0000", "<IP_ADDRESS_1>": "192.168.1.1"},
            "SSN: 000-00-0000, IP: 192.168.1.1",
        ),
        (
            "Visit <URL_1> at <ADDRESS_1>",
            {"<URL_1>": "https://example.com", "<ADDRESS_1>": "123 Main St, Anytown"},
            "Visit https://example.com at 123 Main St, Anytown",
        ),
        (
            "Name: <PERSON_1>, SSN: <US_SSN_1>, Card: <CREDIT_CARD_1>. Call <PHONE_NUMBER_1> or email <EMAIL_ADDRESS_1>. Website: <URL_1>, IP: <IP_ADDRESS_1>, Lives at <ADDRESS_1>",
            {
                "<PERSON_1>": "Jane Roe",
                "<US_SSN_1>": "111-22-3333",
                "<CREDIT_CARD_1>": "9876-5432-1098-7654",
                "<PHONE_NUMBER_1>": "555-0200",
                "<EMAIL_ADDRESS_1>": "jane.roe@example.org",
                "<URL_1>": "https://jane.example.org",
                "<IP_ADDRESS_1>": "10.0.0.42",
                "<ADDRESS_1>": "456 Oak Ave, Otherville",
            },
            "Name: Jane Roe, SSN: 111-22-3333, Card: 9876-5432-1098-7654. Call 555-0200 or email jane.roe@example.org. Website: https://jane.example.org, IP: 10.0.0.42, Lives at 456 Oak Ave, Otherville",
        ),
    ],
)
def test_unmask_sentence(masked_data, mappings, expected_output):
    assert _unmask_sentence(masked_data, mappings) == expected_output


# Test cases for /unmask API endpoint
def test_unmask_api_success():
    request_payload = UnmaskRequest(
        masked_data="My email is <EMAIL_ADDRESS_1> and name is <PERSON_1>. My IP is <IP_ADDRESS_1>",
        mappings={
            "<EMAIL_ADDRESS_1>": "test@example.com",
            "<PERSON_1>": "Test User",
            "<IP_ADDRESS_1>": "127.0.0.1",
        },
    )
    response = client.post("/unmask", json=request_payload.model_dump())
    assert response.status_code == 200
    response_data = UnmaskResponse(**response.json())
    assert (
        response_data.unmasked_data
        == "My email is test@example.com and name is Test User. My IP is 127.0.0.1"
    )


def test_unmask_api_empty_masked_data():
    request_payload = UnmaskRequest(masked_data="", mappings={"<NAME>": "Test"})
    response = client.post("/unmask", json=request_payload.model_dump())
    assert response.status_code == 200
    response_data = UnmaskResponse(**response.json())
    assert response_data.unmasked_data == ""


def test_unmask_api_empty_mappings():
    request_payload = UnmaskRequest(masked_data="Hello <NAME>", mappings={})
    response = client.post("/unmask", json=request_payload.model_dump())
    assert response.status_code == 200
    response_data = UnmaskResponse(**response.json())
    assert response_data.unmasked_data == "Hello <NAME>"


def test_unmask_api_no_placeholders_in_data():
    request_payload = UnmaskRequest(
        masked_data="Hello World", mappings={"<NAME>": "Test"}
    )
    response = client.post("/unmask", json=request_payload.model_dump())
    assert response.status_code == 200
    response_data = UnmaskResponse(**response.json())
    assert response_data.unmasked_data == "Hello World"


def test_unmask_api_placeholder_not_in_mappings():
    request_payload = UnmaskRequest(
        masked_data="Hello <UNKNOWN>", mappings={"<NAME>": "Test"}
    )
    response = client.post("/unmask", json=request_payload.model_dump())
    assert response.status_code == 200
    response_data = UnmaskResponse(**response.json())
    assert response_data.unmasked_data == "Hello <UNKNOWN>"
