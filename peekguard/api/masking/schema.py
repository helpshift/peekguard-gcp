from pydantic import BaseModel, Field


class MaskRequest(BaseModel):
    text_data: str = Field(
        ...,
        description="The input text containing PII to be masked.",
        examples=["My name is John Doe and my email is john.doe@example.com"],
    )
    language: str = Field(
        "en",
        description="The ISO 639-1 code of the language of the text_data (e.g., 'en', 'es'). Should be one of the configured languages.",
        examples=["en"],
    )
    entities: list[str] | None = Field(
        None,
        description="List of Presidio entity types to mask. Addresses are always auto-detected by pyap. If null or omitted, default entities are used.",
        examples=[["PHONE_NUMBER", "EMAIL_ADDRESS"]],
    )
    existing_mappings: dict[str, str] | None = Field(
        None,
        description="A dictionary of previously generated PII mappings (placeholder: original_PII). If provided, these are used to initialize entity counters and ensure consistent placeholder reuse.",
        examples=[{"<PHONE_NUMBER_1>": "555-123-4567"}],
    )


class MaskResponse(BaseModel):
    masked_data: str = Field(
        ...,
        description="The text with PII replaced by placeholders.",
        examples=["My name is <PERSON_1> and my email is <EMAIL_ADDRESS_1>"],
    )
    mappings: dict[str, str] = Field(
        ...,
        description="A comprehensive dictionary where keys are placeholders and values are the original PII.",
        examples=[
            {"<PERSON_1>": "John Doe", "<EMAIL_ADDRESS_1>": "john.doe@example.com"}
        ],
    )
