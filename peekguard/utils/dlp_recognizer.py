import json
import os
from typing import List, Optional

from google.cloud import dlp_v2
from google.oauth2 import service_account
from presidio_analyzer import AnalysisExplanation, EntityRecognizer, RecognizerResult
from presidio_analyzer.nlp_engine import NlpArtifacts

from peekguard.utils.entities import DLP_TO_PRESIDIO, PRESIDIO_TO_DLP
from peekguard.utils.logger import get_logger
from peekguard.utils.config import get_vault_client, get_secret_from_vault, get_config

logger = get_logger(__name__)


class GoogleDlpRecognizer(EntityRecognizer):
    def __init__(
        self,
        project_id: Optional[str] = None,
        supported_entities: Optional[List[str]] = None,
        supported_language: str = "en",
    ):
        if not supported_entities:
            supported_entities = list(PRESIDIO_TO_DLP.keys())

        super().__init__(
            supported_entities=supported_entities,
            supported_language=supported_language,
            name="Google Cloud DLP Recognizer",
        )

        # Authenticate to GCP
        credentials_json = get_gcp_credentials()
        self.project_id = None

        if credentials_json:
            try:
                credentials_info = json.loads(credentials_json)
                self.project_id = credentials_info.get("project_id")
                credentials = service_account.Credentials.from_service_account_info(
                    credentials_info
                )
                self.dlp_client = dlp_v2.DlpServiceClient(credentials=credentials)
                logger.info(
                    "Initialized Google Cloud DLP client using GCP_CREDENTIALS_JSON."
                )
            except Exception as e:
                logger.error(
                    f"Failed to initialize DLP client with GCP_CREDENTIALS_JSON: {e}. "
                    "Falling back to default credentials."
                )
                self.dlp_client = dlp_v2.DlpServiceClient()
        else:
            self.dlp_client = dlp_v2.DlpServiceClient()
        self.parent = f"projects/{self.project_id}"

    def analyze(
        self, text: str, entities: List[str], nlp_artifacts: Optional[NlpArtifacts] = None
    ) -> List[RecognizerResult]:
        """
        Analyze text using Google Cloud DLP.
        """
        results = []
        if not text:
            return results

        # Filter entities to those supported by DLP mapping
        dlp_info_types = []
        for entity in entities:
            for dlp_type in PRESIDIO_TO_DLP.get(entity, []):
                dlp_info_types.append({"name": dlp_type}) # supports mapping one presidio entity to multiple DLP entities

        if not dlp_info_types:
            logger.debug("No matching DLP infoTypes for requested entities.")
            return results

        try:
            item = {"value": text}
            # Set likelihood threshold. POSSIBLE (0.6) allows broadly matching.
            # Presidio's subsequent logic might filter by score_threshold (default usually 0.6).
            inspect_config = {
                "info_types": dlp_info_types,
                "include_quote": True,
                "min_likelihood": dlp_v2.Likelihood.POSSIBLE,
            }

            request = {
                "parent": self.parent,
                "inspect_config": inspect_config,
                "item": item,
            }

            response = self.dlp_client.inspect_content(request=request)
            # We need to handle byte-to-char offset conversion properly
            # since DLP returns byte offsets.
            utf8_text = text.encode("utf-8")

            for finding in response.result.findings:
                dlp_type = finding.info_type.name
                if dlp_type in DLP_TO_PRESIDIO:
                    presidio_entity = DLP_TO_PRESIDIO[dlp_type]

                    score = self._convert_likelihood_to_score(finding.likelihood)

                    start_byte = finding.location.byte_range.start
                    end_byte = finding.location.byte_range.end

                    # Convert byte offsets to character offsets
                    start_char = len(
                        utf8_text[:start_byte].decode("utf-8", errors="ignore")
                    )
                    end_char = len(
                        utf8_text[:end_byte].decode("utf-8", errors="ignore")
                    )

                    result = RecognizerResult(
                        entity_type=presidio_entity,
                        start=start_char,
                        end=end_char,
                        score=score,
                        analysis_explanation=AnalysisExplanation(
                            recognizer=self.name,
                            original_score=score,
                            textual_explanation=f"Identified as {dlp_type} by GCP DLP",
                        ),
                    )
                    results.append(result)

        except Exception as e:
            logger.error(f"Error calling GCP DLP: {e}", exc_info=True)
            # Depending on policy, we might want to raise or swallow.
            # Swallowing allows other recognizers to still work.

        return results

    def _convert_likelihood_to_score(self, likelihood) -> float:
        mapping = {
            dlp_v2.Likelihood.LIKELIHOOD_UNSPECIFIED: 0.0,
            dlp_v2.Likelihood.VERY_UNLIKELY: 0.2,
            dlp_v2.Likelihood.UNLIKELY: 0.4,
            dlp_v2.Likelihood.POSSIBLE: 0.6,
            dlp_v2.Likelihood.LIKELY: 0.8,
            dlp_v2.Likelihood.VERY_LIKELY: 1.0,
        }
        return mapping.get(likelihood, 0.0)


def get_gcp_credentials():
    """
    Fetch GCP credentials json from vault
    if not found then fetch it from env vars
    """
    try:
       if get_vault_client():
        return get_secret_from_vault(
            get_config("gcp", "key"),
            key="current",
            mount_point=get_config("vault", "mount_point"),
        )

    except Exception as e:
        logger.warning(f"Vault unavailable, falling back to ADC/env: {e}")

    return os.environ.get("GCP_CREDENTIALS_JSON")