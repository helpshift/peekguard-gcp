from fastapi import APIRouter, HTTPException

from peekguard.utils.alerts import send_alert
from peekguard.utils.logger import get_logger
from peekguard.utils.metrics import incr, timing_to_statsd_async

from .schema import (
    UnmaskRequest,
    UnmaskResponse,
)

unmasking_router = APIRouter()
logger = get_logger(__name__)


def _unmask_sentence(masked_data: str, mappings: dict[str, str]) -> str:
    """Replace placeholders in *masked_data* with their original PII values."""
    if not masked_data or not mappings:
        return masked_data

    result = masked_data
    for ph in sorted(mappings, key=len, reverse=True):
        result = result.replace(ph, mappings[ph])
    return result


@timing_to_statsd_async("peekguard.api.unmasking")
@unmasking_router.post(
    "/unmask", response_model=UnmaskResponse, summary="Unmask PII in Text"
)
async def unmask_pii_data(request_data: UnmaskRequest):
    """Unmasks previously masked text using the provided placeholder-to-PII mapping."""
    logger.info(f"Received unmask request: {request_data}.")
    try:
        unmasked_data = _unmask_sentence(
            masked_data=request_data.masked_data, mappings=request_data.mappings
        )
        logger.info("unmask request processed successfully.")
        incr("peekguard.api.unmasking.success")
        return UnmaskResponse(unmasked_data=unmasked_data)
    except Exception as e:
        logger.error(
            "Error during unmask PII operation, re-raising for generic handler.",
            exc_info=True,
        )
        incr("peekguard.api.unmasking.failure")
        send_alert(
            status="critical",
            name="peekguard_unmask_api_failed",
            message=f"An error occurred while unmasking the PII data: {str(e)}",
        )
        raise HTTPException(
            status_code=500,
            detail="An error occurred while unmasking the PII data.",
        )
