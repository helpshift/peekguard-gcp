from pydantic import BaseModel, Field


class UnmaskRequest(BaseModel):
    masked_data: str = Field(
        ...,
        description="The text containing placeholders to be unmasked.",
        examples=["My name is <PERSON_1> and my email is <EMAIL_ADDRESS_1>"],
    )
    mappings: dict[str, str] = Field(
        ...,
        description="A dictionary where keys are placeholders and values are the original PII.",
        examples=[
            {"<PERSON_1>": "John Doe", "<EMAIL_ADDRESS_1>": "john.doe@example.com"}
        ],
    )


class UnmaskResponse(BaseModel):
    unmasked_data: str = Field(
        ...,
        description="The text with PII restored.",
        examples=["My name is John Doe and my email is john.doe@example.com"],
    )
