import os

import posix_ipc
from presidio_analyzer import AnalyzerEngine, RecognizerRegistry, RecognizerResult
from presidio_analyzer.nlp_engine import NlpEngine, NlpEngineProvider

from peekguard.utils.dlp_recognizer import GoogleDlpRecognizer
from peekguard.utils.logger import get_logger

logger = get_logger(__name__)

# Define a unique name for our system-wide semaphore
SEMAPHORE_NAME = "/peekguard-model-lock"


class CustomAnalyzer(AnalyzerEngine):
    """
    A custom AnalyzerEngine that filters out known false positives.
    """

    def __init__(self, *args, **kwargs):
        """
        Initializes the CustomAnalyzer with a predefined set of false positives.
        """
        super().__init__(*args, **kwargs)

        # Define a mapping of entity types to known false positivess
        self._false_positives_map = {
            "PERSON": {"email"},
        }

    def analyze(self, *args, **kwargs) -> list[RecognizerResult]:
        """
        Analyzes text and then filters out specific false positives,
        like "Email" being detected as a PERSON.
        """
        text_to_analyze = kwargs.get("text")

        if not text_to_analyze and args:
            text_to_analyze = args[0]

        original_results = super().analyze(*args, **kwargs)

        filtered_results = []
        for res in original_results:
            # Extract the recognized text using the start/end indices
            recognized_text = text_to_analyze[res.start : res.end]  # type: ignore

            if res.entity_type in self._false_positives_map:
                # Check if the recognized text (lowercase) is in the set for that entity type
                if (
                    recognized_text.lower()
                    in self._false_positives_map[res.entity_type]
                ):
                    # Skip the result if it's a known false positive
                    logger.debug(
                        f"Filtering out known false positive: type={res.entity_type}, text='{recognized_text}'"
                    )
                    continue

            filtered_results.append(res)

        return filtered_results


def _initialize_recognizer_registry() -> RecognizerRegistry:

    """Initializes RecognizerRegistry and loads predefined recognizers."""
    registry = RecognizerRegistry()
    registry.load_predefined_recognizers()
    logger.info("Loaded predefined recognizers.")
    return registry


def _add_google_dlp_recognizer(
    registry: RecognizerRegistry,
) -> None:

    """Adds Google DLP to the RecognizerRegistry."""
    try:
        dlp_recognizer = GoogleDlpRecognizer()
        registry.add_recognizer(dlp_recognizer)
        logger.info("Added Google Cloud DLP recognizer.")

    except Exception as e:
        logger.warning(f"Skipping Google Cloud DLP recognizer initialization: {e}")


def _initialize_nlp_engine_and_registry() -> tuple[
    NlpEngine | None, RecognizerRegistry | None
]:
    """Initializes the NlpEngineProvider for English and the RecognizerRegistry."""
    try:
        registry = _initialize_recognizer_registry()
        _add_google_dlp_recognizer(registry)

        nlp_configuration = {
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}],
        }
        nlp_engine = NlpEngineProvider(
            nlp_configuration=nlp_configuration
        ).create_engine()
        logger.info("NLP engine created successfully.")

        return nlp_engine, registry
    except ImportError:
        logger.error(
            "Model not found. "
            "Please run: pip install spacy && python -m spacy download en_core_web_sm"
        )
    except Exception as e:
        logger.error(f"Failed to create NLP engine or registry: {e}", exc_info=True)
    return None, None


def initialize_analyzer_engine() -> tuple[AnalyzerEngine | None, bool]:
    """
    Initializes the Presidio AnalyzerEngine sequentially across workers
    using a named semaphore to prevent simultaneous model loading.
    """
    pid = os.getpid()
    sem = None  # Initialize semaphore variable

    # O_CREAT flag creates the semaphore if it doesn't exist.
    # We initialize it with a value of 1, making it function like a mutex.
    try:
        sem = posix_ipc.Semaphore(SEMAPHORE_NAME, posix_ipc.O_CREAT, initial_value=1)

        logger.info(f"Worker [PID: {pid}] is waiting to acquire semaphore...")

        # This is a blocking call. The worker will pause here until the
        # semaphore is available.
        sem.acquire()

        logger.info(f"Worker [PID: {pid}] acquired semaphore. Loading model...")

        # --- CRITICAL SECTION: Original logic starts here ---
        analyzer_instance: AnalyzerEngine | None = None
        initialization_successful = False
        try:
            nlp_engine_instance, registry_instance = (
                _initialize_nlp_engine_and_registry()
            )

            if not nlp_engine_instance or not registry_instance:
                logger.error("NLP Engine or Registry initialization failed.")
                return None, False

            supported_langs = nlp_engine_instance.get_supported_languages()
            analyzer_instance = CustomAnalyzer(
                nlp_engine=nlp_engine_instance,
                registry=registry_instance,
                supported_languages=supported_langs,
            )
            initialization_successful = True
        except Exception as e:
            logger.critical(
                f"Critical error during AnalyzerEngine init: {e}", exc_info=True
            )
        # --- CRITICAL SECTION ENDS ---

        logger.info(f"Worker [PID: {pid}] has finished loading the model.")
        return analyzer_instance, initialization_successful

    except Exception as e:
        logger.error(
            f"An error occurred during semaphore-based model loading: {e}",
            exc_info=True,
        )
        return None, False

    finally:
        # This block ensures the semaphore is always released by the worker
        # that acquired it, even if an error occurred during loading.
        if sem:
            sem.release()
            logger.info(f"Worker [PID: {pid}] released semaphore.")
            sem.close()