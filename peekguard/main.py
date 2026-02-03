from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from presidio_analyzer import AnalyzerEngine

from peekguard.api.health.router import health_router
from peekguard.api.masking.router import masking_router
from peekguard.api.unmasking.router import unmasking_router
from peekguard.utils.alerts import send_alert
from peekguard.utils.analyzer import initialize_analyzer_engine
from peekguard.utils.config import Environment, current_environment, init_vault_client
from peekguard.utils.logger import get_logger
from peekguard.utils.metrics import init_statsd

logger = get_logger(__name__)


def init_service():
    """
    Initializes the service at start-up

    Raises:
        RuntimeError: If function faileds to load the creds and
    """
    try:
        environment = current_environment()
        match environment:
            case Environment.PRODUCTION:
                init_vault_client()
                logger.info("Initialized Vault successfully.")

            case Environment.PRODUCTION | Environment.SANDBOX:
                init_statsd()

            case _:
                logger.info("Skipping statsd initialization for '%s'", environment)
        logger.info("Loaded settings successfully.")
    except Exception as e:
        logger.critical(f"init_service failed {str(e)}")
        raise RuntimeError(f"Error while initializing service: {str(e)}")


# --- Lifespan Management ---
@asynccontextmanager
async def lifespan(
    app_instance: FastAPI,
):
    """Initializes services on startup and handles cleanup on shutdown."""
    logger.info("FastAPI application startup: Initializing services...")
    analyzer_instance: AnalyzerEngine | None = None
    initialization_successful = False

    try:
        init_service()
        analyzer_instance, initialization_successful = initialize_analyzer_engine()
        logger.info("Application context initialized successfully.")
    except RuntimeError as e:
        logger.critical(
            f"Core service initialization failed in app_context.init_service(): {e}",
            exc_info=True,
        )
    except Exception as e:
        logger.critical(
            f"Unexpected critical error during service lifespan startup: {e}",
            exc_info=True,
        )
        send_alert(
            "critical",
            f"Peekguard service initialization failed with error: {str(e)}",
        )

    app_instance.state.analyzer_engine = analyzer_instance
    app_instance.state.service_initialized_successfully = initialization_successful

    yield

    logger.info("FastAPI application shutdown: Cleaning up resources...")
    app_instance.state.analyzer_engine = None
    app_instance.state.service_initialized_successfully = False
    logger.info("AnalyzerEngine resources cleaned up.")


app = FastAPI(lifespan=lifespan)

# Load Routers
app.include_router(health_router)
app.include_router(masking_router)
app.include_router(unmasking_router)


@app.get("/")
async def read_root():
    return {"message": "Welcome to PeekGuard FastAPI!"}


if __name__ == "__main__":
    port = 8045
    should_reload = False
    match current_environment():
        case Environment.PRODUCTION:
            port = 8044

        case Environment.LOCALHOST:
            should_reload = True

        case _:
            pass

    logger.info("Starting peekguard api on port %d with reload=%s", port, should_reload)
    uvicorn.run(
        app="peekguard.main:app",
        host="0.0.0.0",
        port=port,
        reload=should_reload,
        workers=3,
        log_level="error"
    )
