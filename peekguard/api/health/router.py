import logging

from fastapi import APIRouter, Request

from .schema import HealthResponse

logger = logging.getLogger("peekguard")
health_router = APIRouter(tags=["Health"])


@health_router.get("/health", response_model=HealthResponse)
async def detailed_health_check(request: Request):
    """Detailed health check, including PII AnalyzerEngine and core service initialization status."""
    logger.debug("Detailed /health check requested.")

    service_initialized_successfully = getattr(
        request.app.state, "service_initialized_successfully", False
    )
    analyzer_engine = getattr(request.app.state, "analyzer_engine", None)

    if service_initialized_successfully and analyzer_engine:
        return HealthResponse(
            status="healthy",
            message="Service and AnalyzerEngine are initialized and ready.",
        )
    elif not service_initialized_successfully:
        return HealthResponse(
            status="unhealthy",
            message="Core service initialization failed. Check logs for errors.",
        )
    else:  # Service init was ok, but analyzer_engine is None
        return HealthResponse(
            status="unhealthy",
            message="AnalyzerEngine is not initialized. Check logs for errors.",
        )
