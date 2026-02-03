from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(
        ...,
        description='The health status, e.g., "healthy" or "unhealthy".',
        examples=["healthy", "unhealthy"],
    )
    message: str = Field(
        ...,
        description="A descriptive message about the health status.",
        examples=[
            "Service is operating normally.",
            "AnalyzerEngine is not initialized. Check logs for errors.",
        ],
    )
