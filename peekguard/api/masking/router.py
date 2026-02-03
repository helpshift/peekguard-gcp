from fastapi import APIRouter, Depends, HTTPException, Request, status
from presidio_analyzer import AnalyzerEngine

from peekguard.utils.alerts import send_alert
from peekguard.utils.logger import get_logger
from peekguard.utils.metrics import incr, timing_to_statsd_async

from .handler import mask_sentence
from .schema import MaskRequest, MaskResponse

masking_router = APIRouter()
logger = get_logger(__name__)


async def get_analyzer_engine_dependency(request: Request) -> AnalyzerEngine:
    """Dependency to ensure core service and AnalyzerEngine are ready."""
    service_initialized_successfully = getattr(
        request.app.state, "service_initialized_successfully", False
    )
    if not service_initialized_successfully:
        logger.error("PII API: Core service components are not ready.")
        send_alert(
            status="critical",
            name="peekguard_analyzer_failed",
            message="PII API: Core service components are not ready.",
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Core service components are not ready. Check service logs.",
        )

    analyzer = getattr(request.app.state, "analyzer_engine", None)
    if not analyzer:
        logger.error("PII API: AnalyzerEngine not available in application state.")
        send_alert(
            status="critical",
            name="peekguard_analyzer_failed",
            message="PII API: AnalyzerEngine not available in application state.",
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AnalyzerEngine not available. Service might be initializing or encountered an error during startup.",
        )
    return analyzer


@timing_to_statsd_async("peekguard.api.masking")
@masking_router.post("/mask", response_model=MaskResponse, summary="Mask PII in Text")
async def mask_pii_data(
    request_data: MaskRequest,
    analyzer: AnalyzerEngine = Depends(get_analyzer_engine_dependency),
):
    """
    Masks PII in input text using pyap for addresses and Presidio for other entities.
    Supports continuous masking via `existing_mappings`.
    """
    logger.info(f"Received mask request: {request_data}.")
    try:
        masked_text, mappings = mask_sentence(
            sentence=request_data.text_data,
            analyzer=analyzer,
            language=request_data.language,
            presidio_entities=request_data.entities,
            existing_mappings=request_data.existing_mappings,
        )
        logger.info(f"mask request processed. Returning {len(mappings)} mappings.")
        incr("peekguard.api.masking.success")
        return MaskResponse(masked_data=masked_text, mappings=mappings)
    except Exception as e:
        logger.error(
            "Error during mask PII operation, re-raising for generic handler.",
            exc_info=True,
        )
        incr("peekguard.api.masking.failure")
        send_alert(
            status="critical",
            name="peekguard_mask_api_failed",
            message=f"Unexpected error while masking data: {str(e)}",
        )
        raise
